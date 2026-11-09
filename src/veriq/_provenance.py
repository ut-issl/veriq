"""Per-field metadata and provenance for root-model input values.

Two complementary sources describe *why an input value is what it is*:

1. **Code side** (`Meta`): properties of the field definition (unit, governing
   document, owner, ...). Declared with ``Annotated[T, vq.Meta({...})]`` on a
   root-model field. Definition-level, so it is carried in the IR as
   ``NodeSpec.field_metadata``.
2. **Input-TOML side** (``provenance`` table): rationale for the concrete value
   written next to the value. Input data, so it is loaded separately from the
   model data as a mapping keyed by leaf ``ProjectPath``.

Both sources may be attached to non-leaf paths (nested model, whole ``Table``).
Leaves see a shallow merge along the path from the root model to the leaf, the
nearest path winning per key.
"""

from __future__ import annotations

from annotationlib import ForwardRef
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from inspect import isclass
from itertools import product
from typing import TYPE_CHECKING, Annotated, Any, get_args, get_origin

from pydantic import BaseModel

from ._external_data import ExternalData
from ._path import AttributePart, ItemPart, ModelPath, PartBase, ProjectPath, iter_leaf_path_parts
from ._table import Table

if TYPE_CHECKING:
    from ._models import Project

PROVENANCE_KEY = "provenance"
"""Reserved key of the per-scope TOML table that holds input provenance (sibling of ``model``)."""


@dataclass(frozen=True, slots=True, init=False)
class Meta:
    """User-defined metadata attached to a root-model field definition.

    Usage::

        class Design(BaseModel):
            battery_capacity: Annotated[float, vq.Meta({"source_doc": "EPS-ICD-001", "unit": "Wh"})]
            battery: Annotated[Battery, vq.Meta(owner="power-team")]  # inherited by battery.* leaves

    veriq does not interpret the contents. A shallow copy is stored.
    """

    data: dict[str, Any] = field(default_factory=dict)

    def __init__(self, data: Mapping[str, Any] | None = None, /, **kwargs: Any) -> None:
        merged = dict(data) if data is not None else {}
        merged.update(kwargs)
        object.__setattr__(self, "data", merged)


class ProvenanceError(ValueError):
    """Raised when the ``provenance`` table of an input TOML file does not match the root model."""


# =============================================================================
# Shared helpers
# =============================================================================


def _merge_along_path(
    declared: Mapping[tuple[PartBase, ...], Mapping[str, Any]],
    parts: tuple[PartBase, ...],
) -> dict[str, Any]:
    """Shallow-merge declared metadata over all prefixes of ``parts``; the nearest prefix wins."""
    merged: dict[str, Any] = {}
    for n in range(len(parts) + 1):
        prefix = parts[:n]
        if prefix in declared:
            merged.update(declared[prefix])
    return merged


def _resolve_type(type_: Any) -> Any:
    if isinstance(type_, ForwardRef):
        type_ = type_.evaluate()
    if get_origin(type_) is Annotated:
        type_ = get_args(type_)[0]
    return type_


def _table_key_strings(table_type: Any) -> list[str] | None:
    """Return the TOML key strings of a ``Table[K, V]`` type, or None if it is not a Table."""
    origin = get_origin(table_type)
    if not (origin is Table or (isclass(origin) and issubclass(origin, Table))):
        return None
    type_args = get_args(table_type)
    if len(type_args) != 2:
        return []
    key_type_arg = type_args[0]
    enum_types = get_args(key_type_arg) or (key_type_arg,)
    if not all(isclass(et) and issubclass(et, StrEnum) for et in enum_types):
        return []
    if len(enum_types) == 1:
        return [member.value for member in enum_types[0]]
    return [",".join(member.value for member in combo) for combo in product(*(list(et) for et in enum_types))]


def _table_value_type(table_type: Any) -> Any:
    type_args = get_args(table_type)
    return type_args[1] if len(type_args) == 2 else Any


def _item_part_for_key(key: str) -> ItemPart:
    return ItemPart(key=tuple(k.strip() for k in key.split(","))) if "," in key else ItemPart(key=key)


# =============================================================================
# Code side: vq.Meta on fields
# =============================================================================


def _meta_from_annotations(items: Any) -> dict[str, Any] | None:
    """Collect ``Meta`` objects from an iterable of annotation metadata, later ones winning."""
    found: dict[str, Any] | None = None
    for item in items:
        if isinstance(item, Meta):
            found = {**(found or {}), **item.data}
    return found


def _collect_declared_meta(
    type_: Any,
    parts: tuple[PartBase, ...],
    declared: dict[tuple[PartBase, ...], dict[str, Any]],
) -> None:
    type_ = _resolve_type(type_)

    table_keys = _table_key_strings(type_)
    if table_keys is not None:
        # Table[K, V]: Meta on an Annotated value type applies to every item -> declare at the table path
        value_type = _table_value_type(type_)
        raw_value_type = value_type.evaluate() if isinstance(value_type, ForwardRef) else value_type
        if get_origin(raw_value_type) is Annotated:
            meta = _meta_from_annotations(get_args(raw_value_type)[1:])
            if meta:
                declared[parts] = {**declared.get(parts, {}), **meta}
        for key in table_keys:
            _collect_declared_meta(value_type, (*parts, _item_part_for_key(key)), declared)
        return

    if not isclass(type_) or issubclass(type_, (Table, ExternalData)) or not issubclass(type_, BaseModel):
        return

    for field_name, field_info in type_.model_fields.items():
        field_parts = (*parts, AttributePart(name=field_name))
        meta = _meta_from_annotations(field_info.metadata)
        if meta:
            declared[field_parts] = meta
        if field_info.annotation is not None:
            _collect_declared_meta(field_info.annotation, field_parts, declared)


def collect_field_metadata(root_model: type[BaseModel]) -> dict[tuple[PartBase, ...], dict[str, Any]]:
    """Resolve ``vq.Meta`` declarations of a root model into per-leaf metadata.

    Returns a mapping from leaf path parts (as produced by ``iter_leaf_path_parts``)
    to the merged metadata dict. Leaves without any metadata are omitted.
    """
    declared: dict[tuple[PartBase, ...], dict[str, Any]] = {}
    _collect_declared_meta(root_model, (), declared)
    if not declared:
        return {}
    result: dict[tuple[PartBase, ...], dict[str, Any]] = {}
    for leaf_parts in iter_leaf_path_parts(root_model):
        merged = _merge_along_path(declared, leaf_parts)
        if merged:
            result[leaf_parts] = merged
    return result


# =============================================================================
# Input-TOML side: the `provenance` table
# =============================================================================


def _format_path(scope_name: str, parts: tuple[PartBase, ...]) -> str:
    return f"{scope_name}::{ModelPath(root='$', parts=parts)}"


def _child_names(type_: Any) -> list[str]:
    """Names of the child entries a provenance table may have at this type (model fields or table keys)."""
    type_ = _resolve_type(type_)
    table_keys = _table_key_strings(type_)
    if table_keys is not None:
        return table_keys
    if isclass(type_) and issubclass(type_, BaseModel) and not issubclass(type_, ExternalData):
        return list(type_.model_fields)
    return []


def _child_type(type_: Any, name: str) -> Any:
    type_ = _resolve_type(type_)
    if _table_key_strings(type_) is not None:
        return _table_value_type(type_)
    return type_.model_fields[name].annotation


def _child_part(type_: Any, name: str) -> PartBase:
    if _table_key_strings(_resolve_type(type_)) is not None:
        return _item_part_for_key(name)
    return AttributePart(name=name)


def _walk_provenance_table(
    scope_name: str,
    type_: Any,
    table: Mapping[str, Any],
    parts: tuple[PartBase, ...],
    declared: dict[tuple[PartBase, ...], dict[str, Any]],
) -> None:
    children = _child_names(type_)
    for key, value in table.items():
        if key in children:
            if not isinstance(value, Mapping):
                msg = (
                    f"Provenance entry '{key}' at '{_format_path(scope_name, parts)}' names a model path, "
                    f"so it must be a table, got {type(value).__name__}."
                )
                raise ProvenanceError(msg)
            _walk_provenance_table(
                scope_name,
                _child_type(type_, key),
                value,
                (*parts, _child_part(type_, key)),
                declared,
            )
        elif isinstance(value, Mapping):
            msg = (
                f"Provenance path '{_format_path(scope_name, (*parts, AttributePart(name=key)))}' "
                "does not exist in the root model."
            )
            raise ProvenanceError(msg)
        else:
            declared.setdefault(parts, {})[key] = value


def toml_to_provenance(project: Project, toml_contents: Mapping[str, Any]) -> dict[ProjectPath, dict[str, Any]]:
    """Extract input provenance from parsed TOML contents.

    For each scope, the reserved ``provenance`` table (sibling of ``model``) mirrors the
    root model's structure. Keys that name a model field or ``Table`` key are sub-tables
    for that path; all other keys are metadata for the current path. A sub-table whose
    key is not a model path raises ``ProvenanceError``.

    Returns a mapping from leaf ``ProjectPath`` to the metadata merged along the path
    (nearest path wins). Leaves without provenance are omitted.
    """
    result: dict[ProjectPath, dict[str, Any]] = {}
    for scope_name, scope in project.scopes.items():
        scope_table = toml_contents.get(scope_name)
        if not isinstance(scope_table, Mapping) or PROVENANCE_KEY not in scope_table:
            continue
        provenance_table = scope_table[PROVENANCE_KEY]
        if not isinstance(provenance_table, Mapping):
            msg = f"'{scope_name}.{PROVENANCE_KEY}' must be a table, got {type(provenance_table).__name__}."
            raise ProvenanceError(msg)

        root_model = scope.get_root_model()
        declared: dict[tuple[PartBase, ...], dict[str, Any]] = {}
        _walk_provenance_table(scope_name, root_model, provenance_table, (), declared)
        if not declared:
            continue
        for leaf_parts in iter_leaf_path_parts(root_model):
            merged = _merge_along_path(declared, leaf_parts)
            if merged:
                result[ProjectPath(scope=scope_name, path=ModelPath(root="$", parts=leaf_parts))] = merged
    return result


def strip_provenance(toml_contents: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of TOML contents without any per-scope ``provenance`` table."""
    return {
        scope_name: (
            {k: v for k, v in scope_table.items() if k != PROVENANCE_KEY}
            if isinstance(scope_table, Mapping)
            else scope_table
        )
        for scope_name, scope_table in toml_contents.items()
    }


# =============================================================================
# JSON schema support
# =============================================================================


def build_provenance_model(root_model: type[BaseModel], name: str) -> type[BaseModel]:
    """Build a Pydantic model describing the ``provenance`` table of a root model.

    The model mirrors the root model's structure: every field / ``Table`` key becomes an
    optional sub-model, and every level accepts arbitrary extra keys (the metadata).
    Used only for JSON schema generation.
    """
    from pydantic import ConfigDict, create_model  # noqa: PLC0415

    def build(type_: Any, model_name: str) -> Any:
        children = _child_names(type_)
        if not children:
            return dict[str, Any]
        fields: dict[str, Any] = {}
        for child in children:
            child_model = build(_child_type(type_, child), f"{model_name}_{child.replace(',', '_')}")
            fields[child] = (child_model | None, None)
        return create_model(model_name, __config__=ConfigDict(extra="allow"), **fields)

    return build(root_model, name)
