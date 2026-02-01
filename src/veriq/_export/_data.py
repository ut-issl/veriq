"""Data grouping logic for export — no HTML rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from veriq._path import CalcPath, ModelPath, VerificationPath

from ._components import format_part

if TYPE_CHECKING:
    from pydantic import BaseModel

    from veriq._eval_engine import EvaluationResult
    from veriq._models import Project


class ScopeData:
    """Container for scope-level data extracted from evaluation results."""

    def __init__(self) -> None:
        self.model_values: dict[str, Any] = {}
        self.model_descriptions: dict[str, str] = {}
        self.calc_values: dict[str, dict[str, Any]] = {}
        self.calc_descriptions: dict[str, dict[str, str]] = {}
        self.verification_values: dict[str, bool | dict[str, bool]] = {}


def _extract_field_descriptions(model: BaseModel, prefix: str = "$") -> dict[str, str]:
    """Extract field descriptions from a Pydantic model recursively.

    Args:
        model: The Pydantic model instance.
        prefix: The path prefix (e.g., "$" for root model).

    Returns:
        Dictionary mapping field paths to their descriptions.

    """
    descriptions: dict[str, str] = {}
    model_class = type(model)

    for field_name, field_info in model_class.model_fields.items():
        path = f"{prefix}.{field_name}"

        if field_info.description:
            descriptions[path] = field_info.description

        field_value = getattr(model, field_name, None)
        if field_value is not None and hasattr(field_value, "model_fields"):
            nested_descriptions = _extract_field_descriptions(field_value, path)
            descriptions.update(nested_descriptions)

    return descriptions


def group_results_by_scope(  # noqa: C901, PLR0912
    project: Project,
    model_data: dict[str, BaseModel],
    result: EvaluationResult,
) -> dict[str, ScopeData]:
    """Group evaluation results by scope and type."""
    scope_data: dict[str, ScopeData] = {}

    for scope_name in project.scopes:
        scope_data[scope_name] = ScopeData()

    for scope_name, model in model_data.items():
        if scope_name in scope_data:
            scope_data[scope_name].model_descriptions = _extract_field_descriptions(model)

    for scope_name, scope_tree in result.scopes.items():
        if scope_name not in scope_data:
            scope_data[scope_name] = ScopeData()

        data = scope_data[scope_name]

        for node in scope_tree.iter_all_nodes():
            for leaf in node.iter_leaves():
                ppath = leaf.path
                value = leaf.value

                if isinstance(ppath.path, ModelPath):
                    path_str = str(ppath.path)
                    data.model_values[path_str] = value

                elif isinstance(ppath.path, CalcPath):
                    calc_name = ppath.path.calc_name
                    if calc_name not in data.calc_values:
                        data.calc_values[calc_name] = {}

                    if ppath.path.parts:
                        parts_str = "".join(format_part(p) for p in ppath.path.parts)
                        data.calc_values[calc_name][parts_str] = value
                    else:
                        data.calc_values[calc_name]["(output)"] = value

                elif isinstance(ppath.path, VerificationPath):
                    verif_name = ppath.path.verification_name
                    if ppath.path.parts:
                        if verif_name not in data.verification_values:
                            data.verification_values[verif_name] = {}
                        key_str = "".join(format_part(p) for p in ppath.path.parts)
                        data.verification_values[verif_name][key_str] = value  # type: ignore[index]
                    else:
                        data.verification_values[verif_name] = value

    return scope_data
