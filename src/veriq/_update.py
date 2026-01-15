"""Update input data by merging existing values with new schema defaults.

This module implements the functional core for updating input TOML files
when the project schema changes. It follows the "Functional Core, Imperative Shell"
pattern where all logic is pure functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UpdateWarning:
    """Warning about a field that exists in old data but not in new schema."""

    path: str
    message: str


@dataclass(frozen=True)
class UpdateResult:
    """Result of updating input data with warnings."""

    updated_data: dict[str, Any]
    warnings: list[UpdateWarning]


def deep_merge(
    new_default: Any,
    existing: Any,
    path: str = "",
) -> tuple[Any, list[UpdateWarning]]:
    """Deep merge existing data with new default structure.

    Strategy:
    - For dictionaries: merge recursively, preferring existing values
    - For other types: prefer existing value if types match, otherwise use default
    - Warn about fields in existing that don't exist in new default

    Args:
        new_default: The new default value from updated schema
        existing: The existing value from old input file
        path: Current path in the data structure (for warnings)

    Returns:
        Tuple of (merged value, list of warnings)

    """
    warnings: list[UpdateWarning] = []

    # If both are dicts, merge recursively
    if isinstance(new_default, dict) and isinstance(existing, dict):
        result = {}

        # Process all keys from new default
        for key, default_value in new_default.items():
            key_path = f"{path}.{key}" if path else key

            if key in existing:
                # Recursive merge
                merged_value, merge_warnings = deep_merge(
                    default_value,
                    existing[key],
                    key_path,
                )
                result[key] = merged_value
                warnings.extend(merge_warnings)
            else:
                # New field - use default
                result[key] = default_value

        # Warn about fields in existing that don't exist in new default
        for key in existing:
            if key not in new_default:
                key_path = f"{path}.{key}" if path else key
                warnings.append(
                    UpdateWarning(
                        path=key_path,
                        message=f"Field '{key_path}' no longer exists in schema",
                    ),
                )

        return result, warnings

    # If both are the same type (and not dict), prefer existing
    if type(new_default) is type(existing):
        return existing, warnings

    # Type mismatch - use default and warn
    if path:
        warnings.append(
            UpdateWarning(
                path=path,
                message=f"Type mismatch at '{path}': expected {type(new_default).__name__}, "
                f"got {type(existing).__name__}. Using default value.",
            ),
        )

    return new_default, warnings


def update_input_data(
    new_default_data: dict[str, Any],
    existing_data: dict[str, Any],
) -> UpdateResult:
    """Update existing input data with new defaults from current schema.

    This is the main entry point for the functional core. It takes the new
    default data (generated from current project schema) and existing data
    (from old TOML file) and merges them intelligently.

    Args:
        new_default_data: Default data from current project schema
        existing_data: Existing data from old TOML file

    Returns:
        UpdateResult containing merged data and any warnings

    """
    updated_data, warnings = deep_merge(new_default_data, existing_data)
    return UpdateResult(updated_data=updated_data, warnings=warnings)
