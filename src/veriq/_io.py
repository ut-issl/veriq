import logging
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomli_w
from pydantic import ValidationError

from ._atomic import atomic_write_bytes
from ._context import (  # noqa: F401 - get_input_base_dir re-exported
    get_input_base_dir,
    reset_input_base_dir,
    set_input_base_dir,
)
from ._path import AttributePart, CalcPath, ItemPart, ModelPath, PartBase, VerificationPath
from ._table import Table

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from pydantic import BaseModel

    from ._eval_engine import EvaluationResult
    from ._models import Project, Scope

logger = logging.getLogger(__name__)


# =============================================================================
# Base Directory Context for Path Resolution
# =============================================================================


@contextmanager
def input_base_dir(base_dir: Path) -> Iterator[None]:
    """Context manager to set the base directory for resolving relative paths.

    When loading input files (e.g., TOML), use this context to resolve relative
    paths (e.g., FileRef.path) relative to a base directory (typically the
    input file's parent directory).

    Example:
        with input_base_dir(toml_path.parent):
            model_data = load_model_data(...)

    """
    token = set_input_base_dir(base_dir)
    try:
        yield
    finally:
        reset_input_base_dir(token)


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a value for TOML export, handling special types.

    Handles:
    - Pydantic BaseModel: Converts to dict via model_dump()
    - Table: Converts enum keys to strings and recursively serializes values
    - dict: Recursively serializes values
    - list/tuple: Recursively serializes items
    - Primitives and TOML-native types: Returns as-is
    """
    # Import BaseModel locally to avoid potential circular imports
    from pydantic import BaseModel  # noqa: PLC0415

    # Handle Pydantic BaseModel - convert to dict and recursively serialize
    if isinstance(value, BaseModel):
        # Use mode='python' to preserve Python types (datetime, Decimal, etc.)
        # which are TOML-compatible, rather than converting to JSON types
        return _serialize_value(value.model_dump(mode="python"))

    # Handle Table (dict with enum keys) - convert keys to strings and serialize values
    if isinstance(value, Table):
        result = {}
        for k, v in value.items():
            if isinstance(k, tuple):
                # Tuple of enums - join their values
                key_str = ",".join(item.value if hasattr(item, "value") else str(item) for item in k)
            elif hasattr(k, "value"):
                # Single enum
                key_str = k.value
            else:
                # Other types
                key_str = str(k)
            # Recursively serialize the value
            result[key_str] = _serialize_value(v)
        return result

    # Handle dict - recursively serialize values, excluding None (TOML doesn't support None)
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items() if v is not None}

    # Handle list/tuple - recursively serialize items
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]

    # Handle Path objects - convert to string
    if isinstance(value, Path):
        return str(value)

    # Primitives and TOML-native types (str, int, float, bool, datetime, etc.)
    return value


def _set_nested_value(data: dict[str, Any], keys: list[str], value: Any, *, skip_none: bool = True) -> None:
    """Set a value in a nested dictionary using a list of keys."""
    current = data
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    serialized = _serialize_value(value)
    # TOML does not support None/null values, so skip them
    if serialized is not None or not skip_none:
        current[keys[-1]] = serialized


def _parts_to_keys(parts: tuple[PartBase, ...]) -> list[str]:
    """Convert path parts to a list of keys for nested dictionary access."""
    keys: list[str] = []
    for part in parts:
        match part:
            case AttributePart(name):
                keys.append(name)
            case ItemPart(key):
                # For Table items, use the key directly as a dictionary key
                if isinstance(key, tuple):
                    # Multi-key access (though not common in this context)
                    keys.append(",".join(key))
                else:
                    keys.append(key)
            case _:
                msg = f"Unknown part type: {type(part)}"
                raise TypeError(msg)
    return keys


def results_to_dict(
    result: EvaluationResult,
    exclude_calcs: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Convert evaluation results to a nested dictionary structure.

    This is a pure function that converts the tree-based evaluation result
    into a nested dictionary suitable for TOML export.

    Args:
        result: The EvaluationResult from evaluate_project
        exclude_calcs: Optional set of ``(scope_name, calc_name)`` pairs whose
            calculation outputs are omitted from the result (e.g. transient
            calculations that should not be written to TOML).

    Returns:
        A nested dictionary with the structure:
        {
            "ScopeName": {
                "model": {...},
                "calc": {...},
                "verification": {...}
            }
        }

    """
    excluded = exclude_calcs or set()
    toml_data: dict[str, Any] = {}

    # Process all leaf values from the tree
    for ppath, value in result.iter_leaf_values():
        scope_name = ppath.scope
        path = ppath.path

        # Build the section name based on the path type
        if isinstance(path, ModelPath):
            # Model paths: {scope}.model.{field_path}
            section_keys = [scope_name, "model"]
            field_keys = _parts_to_keys(path.parts)
        elif isinstance(path, CalcPath):
            # Calculation paths: {scope}.calc.{calc_name}.{field_path}
            if (scope_name, path.calc_name) in excluded:
                continue
            section_keys = [scope_name, "calc", path.calc_name]
            field_keys = _parts_to_keys(path.parts)
        elif isinstance(path, VerificationPath):
            # Verification paths: {scope}.verification.{verification_name} or
            # {scope}.verification.{verification_name}.{field_path} for Table[K, bool]
            if path.parts:
                # Table[K, bool] verification - has parts for table indexing
                section_keys = [scope_name, "verification", path.verification_name]
                field_keys = _parts_to_keys(path.parts)
            else:
                # Plain bool verification - no parts
                section_keys = [scope_name, "verification"]
                field_keys = [path.verification_name]
        else:
            msg = f"Unknown path type: {type(path)}"
            raise TypeError(msg)

        # Combine section and field keys
        all_keys = section_keys + field_keys

        # Set the value in the nested dictionary
        _set_nested_value(toml_data, all_keys, value)

    return toml_data


def export_to_toml(
    project: Project,
    _model_data: Mapping[str, BaseModel],
    result: EvaluationResult,
    output_path: Path | str,
) -> None:
    """Export model data and evaluation results to a TOML file.

    Calculations marked ``transient=True`` are excluded from the output; they
    are still computed and passed to dependent calculations in memory.

    Args:
        project: The project containing scope definitions
        model_data: The input model data for each scope
        result: The EvaluationResult from evaluate_project
        output_path: Path to the output TOML file

    """
    exclude_calcs = {
        (scope_name, calc_name)
        for scope_name, scope in project.scopes.items()
        for calc_name, calc in scope.calculations.items()
        if calc.transient
    }
    toml_data = results_to_dict(result, exclude_calcs=exclude_calcs)

    # Write atomically so a crash mid-write never corrupts the output file.
    output_path = Path(output_path)
    atomic_write_bytes(output_path, tomli_w.dumps(toml_data).encode())

    logger.debug(f"Exported results to {output_path}")


def toml_to_model_data(
    project: Project,
    toml_contents: dict[str, Any],
) -> dict[str, BaseModel]:
    """Convert TOML dictionary contents to validated model data.

    This is a pure function that validates and converts TOML contents
    into Pydantic model instances for each scope in the project.

    Args:
        project: The project containing scope definitions
        toml_contents: The parsed TOML dictionary

    Returns:
        A dictionary mapping scope names to their validated root model instances

    """
    from pydantic import BaseModel as PydanticBaseModel  # noqa: PLC0415

    model_data: dict[str, PydanticBaseModel] = {}
    for scope_name, scope in project.scopes.items():
        if scope_name in toml_contents and "model" in toml_contents[scope_name]:
            root_model = scope.get_root_model()
            model_data[scope_name] = root_model.model_validate(toml_contents[scope_name]["model"])
            logger.debug(f"Loaded model data for scope '{scope_name}'")
        else:
            logger.debug(f"No model data found for scope '{scope_name}'")

    return model_data


def _load_combined(input: Path | str | None) -> tuple[dict[str, Any], Path | None]:  # noqa: A002
    """Load the optional combined input TOML, returning (contents, base dir)."""
    if input is None:
        return {}, None
    combined_path = Path(input).resolve()
    with combined_path.open("rb") as f:
        return tomllib.load(f), combined_path


def _resolve_scope_raw(
    scope: Scope,
    scope_name: str,
    combined: dict[str, Any],
    combined_path: Path | None,
) -> tuple[dict[str, Any], Path, Path] | None:
    """Resolve a scope's raw input dict, FileRef base dir, and source file.

    A scope's own ``input`` file is authoritative (it holds the root model
    directly); otherwise the combined input's ``[scope.model]`` section is used.
    Returns None when neither provides data for the scope.
    """
    scope_file = scope.input_path
    if scope_file is not None:
        with scope_file.open("rb") as f:
            return tomllib.load(f), scope_file.parent, scope_file
    if combined_path is not None and scope_name in combined and "model" in combined[scope_name]:
        return combined[scope_name]["model"], combined_path.parent, combined_path
    return None


def load_model_data(
    project: Project,
    input: Path | str | None = None,  # noqa: A002 - mirrors CLI -i/--input
) -> dict[str, BaseModel]:
    """Load model data for each scope, composing per-scope input files.

    Each scope may declare its own input TOML via ``Scope(input=...)``. That
    file holds the scope's root model directly (no ``[Scope.model]`` prefix)
    and is authoritative. The optional project-level ``input`` is a combined
    TOML (``[Scope.model]`` sections) that fills only the scopes that do not
    declare their own file.

    FileRef paths resolve relative to the directory of the file they appear in
    (a scope's own file, or the combined input file), keeping projects portable.

    Args:
        project: The project containing scope definitions
        input: Optional combined input TOML filling scopes without their own file

    Returns:
        A dictionary mapping scope names to their validated root model instances

    """
    combined, combined_path = _load_combined(input)

    model_data: dict[str, BaseModel] = {}
    for scope_name, scope in project.scopes.items():
        resolved = _resolve_scope_raw(scope, scope_name, combined, combined_path)
        if resolved is None:
            logger.debug("No model data found for scope '%s'", scope_name)
            continue
        raw, base, _source = resolved
        root_model = scope.get_root_model()
        # FileRef resolves relative to the file that contained the data.
        with input_base_dir(base):
            model_data[scope_name] = root_model.model_validate(raw)
        logger.debug("Loaded model data for scope '%s'", scope_name)

    return model_data


def load_model_data_from_toml(
    project: Project,
    input_path: Path | str,
) -> dict[str, BaseModel]:
    """Load model data from a single combined TOML file.

    Backward-compatible wrapper over :func:`load_model_data`. FileRef paths in
    the TOML are resolved relative to the TOML file's directory.

    Args:
        project: The project containing scope definitions
        input_path: Path to the input TOML file containing model data

    Returns:
        A dictionary mapping scope names to their validated root model instances

    """
    return load_model_data(project, input=input_path)


@dataclass(frozen=True, slots=True)
class ScopeValidation:
    """Validation outcome for a single scope's input data."""

    scope: str
    ok: bool
    source: Path | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Per-scope input validation results (no graph evaluation)."""

    results: tuple[ScopeValidation, ...]

    @property
    def ok(self) -> bool:
        """True if every scope with input data validated successfully."""
        return all(r.ok for r in self.results)


def validate_model_data(
    project: Project,
    input: Path | str | None = None,  # noqa: A002 - mirrors CLI -i/--input
) -> ValidationReport:
    """Validate each scope's input against its root model, without evaluating.

    Resolves each scope's data the same way as :func:`load_model_data`
    (per-scope ``Scope.input`` file first, then the combined ``input``), then
    runs Pydantic validation only. Scopes with no input data are skipped.

    Args:
        project: The project containing scope definitions
        input: Optional combined input TOML filling scopes without their own file

    Returns:
        A ValidationReport with one entry per scope that had input data.

    """
    combined, combined_path = _load_combined(input)

    results: list[ScopeValidation] = []
    for scope_name, scope in project.scopes.items():
        resolved = _resolve_scope_raw(scope, scope_name, combined, combined_path)
        if resolved is None:
            continue
        raw, base, source = resolved
        root_model = scope.get_root_model()
        try:
            with input_base_dir(base):
                root_model.model_validate(raw)
        except ValidationError as e:
            results.append(ScopeValidation(scope=scope_name, ok=False, source=source, error=str(e)))
        else:
            results.append(ScopeValidation(scope=scope_name, ok=True, source=source))

    return ValidationReport(results=tuple(results))
