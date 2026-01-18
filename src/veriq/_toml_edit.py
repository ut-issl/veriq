"""TOML editing with comment preservation using TOML Kit.

This module provides a functional core for modifying TOML documents while
preserving comments, formatting, and whitespace. It uses TOML Kit's DOM-like
API to update values in place rather than regenerating the entire document.

Follows the "Functional Core, Imperative Shell" pattern - all functions here
are pure (no I/O), and file operations are handled by the CLI commands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.items import Item, Table


def _to_toml_value(value: Any) -> Item | Any:
    """Convert a Python value to a TOML Kit item, preserving types.

    TOML Kit needs values wrapped appropriately to maintain proper formatting.
    This function handles nested structures recursively.

    Args:
        value: Any Python value to convert

    Returns:
        A TOML Kit compatible value

    """
    if isinstance(value, dict):
        table = tomlkit.table()
        for k, v in value.items():
            table[k] = _to_toml_value(v)
        return table

    if isinstance(value, list):
        arr = tomlkit.array()
        for item in value:
            arr.append(_to_toml_value(item))
        return arr

    if isinstance(value, Path):
        return str(value)

    # Primitives (str, int, float, bool, datetime, etc.)
    return value


def update_toml_document(
    doc: TOMLDocument,
    updates: dict[str, Any],
) -> TOMLDocument:
    r"""Update values in a TOML document while preserving comments and formatting.

    This function recursively updates values in the document. Existing keys
    are updated in place (preserving comments), and new keys are added.
    Keys in the document that are not in updates are left unchanged.

    Args:
        doc: Parsed TOML document (from tomlkit.parse())
        updates: Nested dict of values to update

    Returns:
        The same document object (mutated in place)

    Example:
        >>> doc = tomlkit.parse("# Comment\nvalue = 1")
        >>> update_toml_document(doc, {"value": 2})
        >>> tomlkit.dumps(doc)
        '# Comment\nvalue = 2'

    """
    _update_container(doc, updates)
    return doc


def _update_container(
    container: TOMLDocument | Table,
    updates: dict[str, Any],
) -> None:
    """Recursively update a TOML container (document or table) with new values.

    Args:
        container: The TOML container to update
        updates: Dict of updates to apply

    """
    for key, value in updates.items():
        if key in container:
            existing = container[key]
            # If both are dict-like, recurse
            if isinstance(existing, Table) and isinstance(value, dict):
                _update_container(existing, value)
            else:
                # Replace the value
                container[key] = _to_toml_value(value)
        else:
            # Add new key
            container[key] = _to_toml_value(value)


def set_nested_value(
    doc: TOMLDocument | Table,
    keys: list[str],
    value: Any,
) -> None:
    r"""Set a value at a nested path, creating tables as needed.

    This function navigates through the document using the provided keys
    and sets the final value. Intermediate tables are created if they
    don't exist.

    Args:
        doc: The TOML document or table to modify
        keys: List of keys forming the path (e.g., ["Power", "model", "capacity"])
        value: The value to set

    Example:
        >>> doc = tomlkit.parse("")
        >>> set_nested_value(doc, ["Power", "model", "capacity"], 100.0)
        >>> tomlkit.dumps(doc)
        '[Power.model]\ncapacity = 100.0\n'

    """
    if not keys:
        return

    current: TOMLDocument | Table = doc

    # Navigate to the parent of the final key, creating tables as needed
    for key in keys[:-1]:
        if key not in current:
            current[key] = tomlkit.table()
        next_val = current[key]
        if not isinstance(next_val, Table):
            # Overwrite non-table value with a table
            current[key] = tomlkit.table()
        # After creating/getting the table, get it again and assert type
        table_val = current[key]
        if not isinstance(table_val, Table):
            msg = f"Expected Table at key {key}, got {type(table_val)}"
            raise TypeError(msg)
        current = table_val

    # Set the final value
    final_key = keys[-1]
    current[final_key] = _to_toml_value(value)


def merge_into_document(
    doc: TOMLDocument,
    new_data: dict[str, Any],
    existing_data: dict[str, Any],
) -> TOMLDocument:
    """Merge new schema defaults into an existing document.

    This function is used by `veriq update` to add new fields from an updated
    schema while preserving existing values and comments. It performs a
    three-way merge:

    1. Values in existing_data are kept (already in doc with comments)
    2. Values in new_data but not in existing_data are added (new schema fields)
    3. Values in existing_data but not in new_data generate warnings (removed fields)

    Note: This function does not generate warnings - that's handled by the
    update_input_data function in _update.py. This function focuses on
    updating the TOML document structure.

    Args:
        doc: The parsed TOML document to update
        new_data: Default data from current project schema
        existing_data: Existing data that was parsed from the document

    Returns:
        The updated document (same object, mutated in place)

    """
    _merge_recursive(doc, new_data, existing_data, [])
    return doc


def _merge_recursive(
    container: TOMLDocument | Table,
    new_data: dict[str, Any],
    existing_data: dict[str, Any],
    path: list[str],
) -> None:
    """Recursively merge new data into a TOML container.

    Args:
        container: The TOML container to update
        new_data: New default data from schema
        existing_data: Existing data from the file
        path: Current path in the data structure (for debugging)

    """
    for key, new_value in new_data.items():
        existing_value = existing_data.get(key)

        if key in container:
            # Key exists in document
            if isinstance(new_value, dict) and isinstance(existing_value, dict):
                # Both are dicts, recurse
                existing_container = container[key]
                if isinstance(existing_container, Table):
                    _merge_recursive(
                        existing_container,
                        new_value,
                        existing_value,
                        [*path, key],
                    )
            # else: existing value stays (preserves user's value and comments)
        else:
            # Key doesn't exist in document, add it with the new default
            container[key] = _to_toml_value(new_value)


def update_model_values(
    doc: TOMLDocument,
    scope_name: str,
    field_path: list[str],
    value: Any,
) -> TOMLDocument:
    r"""Update a model field value in the TOML document.

    This is a convenience function for updating a single field in a scope's
    model section. Used by the TUI editor.

    Args:
        doc: The TOML document to update
        scope_name: Name of the scope (e.g., "Power")
        field_path: Path to the field within the model (e.g., ["consumption", "nominal"])
        value: The new value to set

    Returns:
        The updated document (same object, mutated in place)

    Example:
        >>> doc = tomlkit.parse("[Power.model]\ncapacity = 100.0")
        >>> update_model_values(doc, "Power", ["capacity"], 150.0)
        >>> tomlkit.dumps(doc)
        '[Power.model]\ncapacity = 150.0\n'

    """
    full_path = [scope_name, "model", *field_path]
    set_nested_value(doc, full_path, value)
    return doc


def parse_toml_preserving(content: str) -> TOMLDocument:
    """Parse TOML content into a document that preserves comments.

    This is a thin wrapper around tomlkit.parse() for consistency.

    Args:
        content: TOML content as a string

    Returns:
        Parsed TOML document with comments preserved

    """
    return tomlkit.parse(content)


def dumps_toml(doc: TOMLDocument) -> str:
    """Convert a TOML document back to a string.

    This is a thin wrapper around tomlkit.dumps() for consistency.

    Args:
        doc: The TOML document to serialize

    Returns:
        TOML string with comments preserved

    """
    return tomlkit.dumps(doc)
