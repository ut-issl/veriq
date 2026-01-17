"""Data model for TUI table editing."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from itertools import product
from typing import TYPE_CHECKING, Any, ForwardRef, get_args, get_origin

from pydantic import BaseModel

from veriq._table import Table

if TYPE_CHECKING:
    from enum import StrEnum

    from veriq._models import Project


@dataclass(slots=True)
class TableData:
    """Bridge between flat TOML dict and 2D grid view.

    Handles multi-dimensional Tables by allowing fixed dimensions for slicing.
    The last two dimensions are displayed as rows and columns.

    For 2D tables: rows = enum1, columns = enum2
    For 3D tables: fixed = enum1, rows = enum2, columns = enum3
    """

    field_name: str
    key_types: tuple[type[StrEnum], ...]
    value_type: type
    flat_data: dict[str, Any]
    modified: bool = field(default=False)

    @property
    def dimensions(self) -> int:
        """Return the number of dimensions in the table."""
        return len(self.key_types)

    def _parse_key(self, key_str: str) -> tuple[StrEnum, ...]:
        """Parse a comma-separated key string into a tuple of enum values."""
        if self.dimensions == 1:
            return (self.key_types[0](key_str),)
        parts = key_str.split(",")
        return tuple(
            enum_type(part) for enum_type, part in zip(self.key_types, parts, strict=True)
        )

    def _serialize_key(self, key: tuple[StrEnum, ...]) -> str:
        """Serialize a tuple of enum values to a comma-separated string."""
        return ",".join(k.value for k in key)

    def get_slice_keys(self, fixed_dims: dict[int, StrEnum]) -> list[tuple[StrEnum, ...]]:
        """Get all keys matching the fixed dimensions.

        Args:
            fixed_dims: Mapping from dimension index to fixed enum value.
                        For a 3D table with fixed_dims={0: Mode.NOMINAL},
                        returns all keys where the first element is Mode.NOMINAL.

        Returns:
            List of full keys (tuples) that match the fixed dimensions.

        """
        # Determine which dimensions are free (not fixed)
        free_dims = [i for i in range(self.dimensions) if i not in fixed_dims]

        # Get all possible values for free dimensions
        free_values = [list(self.key_types[i]) for i in free_dims]

        # Generate all combinations for free dimensions
        if not free_values:
            # All dimensions are fixed
            full_key = tuple(fixed_dims[i] for i in range(self.dimensions))
            return [full_key]

        result = []
        for combo in product(*free_values):
            # Build full key by inserting fixed values at their positions
            full_key: list[StrEnum] = []
            combo_idx = 0
            for i in range(self.dimensions):
                if i in fixed_dims:
                    full_key.append(fixed_dims[i])
                else:
                    full_key.append(combo[combo_idx])
                    combo_idx += 1
            result.append(tuple(full_key))

        return result

    def row_labels(self, fixed_dims: dict[int, StrEnum]) -> list[str]:
        """Get row labels for the grid view.

        For 2D: first dimension values
        For 3D: second dimension values (first is fixed)
        For 1D: all enum values (single column display)

        """
        if self.dimensions == 1:
            return [e.value for e in self.key_types[0]]

        # Row dimension is second-to-last free dimension
        free_dims = [i for i in range(self.dimensions) if i not in fixed_dims]
        # Use first free dim (or 0) if < 2 dims, otherwise second-to-last
        row_dim = (free_dims[0] if free_dims else 0) if len(free_dims) < 2 else free_dims[-2]

        return [e.value for e in self.key_types[row_dim]]

    def column_labels(self, fixed_dims: dict[int, StrEnum]) -> list[str]:
        """Get column labels for the grid view.

        For 2D: second dimension values
        For 3D: third dimension values (first is fixed)
        For 1D: single "Value" column

        """
        if self.dimensions == 1:
            return ["Value"]

        # Column dimension is last free dimension
        free_dims = [i for i in range(self.dimensions) if i not in fixed_dims]
        if not free_dims:
            return ["Value"]

        col_dim = free_dims[-1]
        return [e.value for e in self.key_types[col_dim]]

    def get_cell(
        self,
        fixed_dims: dict[int, StrEnum],
        row_label: str,
        col_label: str,
    ) -> Any:
        """Get a cell value from the grid view.

        Args:
            fixed_dims: Fixed dimension values for slicing
            row_label: Row enum value as string
            col_label: Column enum value as string (or "Value" for 1D)

        Returns:
            The cell value

        """
        full_key = self._build_full_key(fixed_dims, row_label, col_label)
        key_str = self._serialize_key(full_key)
        return self.flat_data.get(key_str)

    def _build_full_key(
        self,
        fixed_dims: dict[int, StrEnum],
        row_label: str,
        col_label: str,
    ) -> tuple[StrEnum, ...]:
        """Build a full key tuple from fixed dims, row label, and column label."""
        if self.dimensions == 1:
            return (self.key_types[0](row_label),)

        # Determine row and column dimensions
        free_dims = [i for i in range(self.dimensions) if i not in fixed_dims]

        if len(free_dims) < 2:
            row_dim = free_dims[0] if free_dims else 0
            col_dim = None
        else:
            row_dim = free_dims[-2]
            col_dim = free_dims[-1]

        # Build the full key
        full_key: list[StrEnum] = []
        for i in range(self.dimensions):
            if i in fixed_dims:
                full_key.append(fixed_dims[i])
            elif i == row_dim:
                full_key.append(self.key_types[i](row_label))
            elif i == col_dim:
                full_key.append(self.key_types[i](col_label))

        return tuple(full_key)

    def update_cell(
        self,
        fixed_dims: dict[int, StrEnum],
        row_label: str,
        col_label: str,
        value: Any,
    ) -> None:
        """Update a cell value in the flat data.

        Args:
            fixed_dims: Fixed dimension values for slicing
            row_label: Row enum value as string
            col_label: Column enum value as string (or "Value" for 1D)
            value: The new value to set

        """
        full_key = self._build_full_key(fixed_dims, row_label, col_label)
        key_str = self._serialize_key(full_key)
        self.flat_data[key_str] = value
        self.modified = True

    def get_fixed_dimension_options(self) -> list[tuple[int, str, list[str]]]:
        """Get options for fixed dimensions (for slice control).

        Returns a list of (dimension_index, enum_type_name, [enum_values])
        for dimensions that should be fixed (all except last 2).

        """
        if self.dimensions <= 2:
            return []

        result = []
        # All dimensions except the last two should be fixable
        for i in range(self.dimensions - 2):
            enum_type = self.key_types[i]
            result.append((i, enum_type.__name__, [e.value for e in enum_type]))

        return result

    def to_serializable(self) -> dict[str, Any]:
        """Convert flat_data to a format suitable for TOML serialization."""
        return dict(self.flat_data)


def _resolve_forward_ref(
    field_type: Any,
    model_cls: type[BaseModel],
) -> Any:
    """Resolve a ForwardRef to its actual type.

    Args:
        field_type: The type annotation, possibly a ForwardRef
        model_cls: The model class where the field is defined (for module context)

    Returns:
        The resolved type, or the original type if not a ForwardRef

    """
    if not isinstance(field_type, ForwardRef):
        return field_type

    # Get the module where the model is defined for resolution context
    module = sys.modules.get(model_cls.__module__)
    if module is None:
        return field_type

    try:
        return field_type.evaluate(globals=vars(module))
    except Exception:  # noqa: BLE001
        return field_type


def extract_table_fields_from_model(
    model_cls: type[BaseModel],
    prefix: str = "",
) -> list[tuple[str, tuple[type[StrEnum], ...], type]]:
    """Extract all Table fields from a Pydantic model recursively.

    Args:
        model_cls: The Pydantic model class to inspect
        prefix: Path prefix for nested fields

    Returns:
        List of (field_path, key_types, value_type) tuples

    """
    result: list[tuple[str, tuple[type[StrEnum], ...], type]] = []

    for field_name, field_info in model_cls.model_fields.items():
        field_type = field_info.annotation
        if field_type is None:
            continue

        # Resolve ForwardRef if present
        field_type = _resolve_forward_ref(field_type, model_cls)

        field_path = f"{prefix}.{field_name}" if prefix else field_name
        origin = get_origin(field_type)

        if origin is Table or (isinstance(origin, type) and issubclass(origin, Table)):
            # This is a Table field
            type_args = get_args(field_type)
            if len(type_args) == 2:
                key_type_arg, value_type = type_args

                # Extract enum types from key type
                key_type_args = get_args(key_type_arg)
                key_types = key_type_args or (key_type_arg,)

                result.append((field_path, key_types, value_type))

        elif isinstance(origin, type) and issubclass(origin, BaseModel):
            # Nested model - recurse
            result.extend(extract_table_fields_from_model(origin, field_path))
        elif isinstance(field_type, type) and issubclass(field_type, BaseModel):
            # Direct BaseModel subclass - recurse
            result.extend(extract_table_fields_from_model(field_type, field_path))

    return result


def load_tables_from_toml(
    project: Project,
    toml_data: dict[str, Any],
) -> dict[str, dict[str, TableData]]:
    """Load all Table data from TOML into TableData objects.

    Args:
        project: The veriq Project instance
        toml_data: Parsed TOML data

    Returns:
        Nested dict: {scope_name: {field_path: TableData}}

    """
    result: dict[str, dict[str, TableData]] = {}

    for scope_name, scope in project.scopes.items():
        scope_tables: dict[str, TableData] = {}

        try:
            root_model = scope.get_root_model()
        except RuntimeError:
            # Scope has no root model
            continue

        # Find all Table fields in this scope's model
        table_fields = extract_table_fields_from_model(root_model)

        # Get the scope's model data from TOML
        scope_toml = toml_data.get(scope_name, {})
        model_toml = scope_toml.get("model", {})

        for field_path, key_types, value_type in table_fields:
            # Navigate to the table data in TOML
            flat_data = _get_nested_value(model_toml, field_path)
            if flat_data is not None and isinstance(flat_data, dict):
                table_data = TableData(
                    field_name=field_path,
                    key_types=key_types,
                    value_type=value_type,
                    flat_data=dict(flat_data),  # Make a copy
                )
                scope_tables[field_path] = table_data

        if scope_tables:
            result[scope_name] = scope_tables

    return result


def _get_nested_value(data: dict[str, Any], path: str) -> Any:
    """Get a nested value from a dict using dot-separated path."""
    parts = path.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


def _set_nested_value(data: dict[str, Any], path: str, value: Any) -> None:
    """Set a nested value in a dict using dot-separated path."""
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def save_tables_to_toml(
    tables: dict[str, dict[str, TableData]],
    toml_data: dict[str, Any],
) -> dict[str, Any]:
    """Save modified TableData back to TOML structure.

    Args:
        tables: The table data from load_tables_from_toml
        toml_data: The original TOML data (will be modified in place)

    Returns:
        The modified TOML data

    """
    for scope_name, scope_tables in tables.items():
        if scope_name not in toml_data:
            toml_data[scope_name] = {}
        if "model" not in toml_data[scope_name]:
            toml_data[scope_name]["model"] = {}

        model_data = toml_data[scope_name]["model"]

        for field_path, table_data in scope_tables.items():
            if table_data.modified:
                _set_nested_value(model_data, field_path, table_data.to_serializable())

    return toml_data
