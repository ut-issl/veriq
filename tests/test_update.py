"""Tests for the update functionality (functional core)."""

from enum import StrEnum

from veriq._update import UpdateResult, UpdateWarning, deep_merge, update_input_data


def test_deep_merge_preserves_existing_values():
    """Test that existing values are preserved during merge."""
    new_default = {"a": 1, "b": 2, "c": 3}
    existing = {"a": 10, "b": 20}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"a": 10, "b": 20, "c": 3}
    assert len(warnings) == 0


def test_deep_merge_adds_new_fields():
    """Test that new fields from schema are added with default values."""
    new_default = {"a": 1, "b": 2, "c": 3}
    existing = {"a": 10}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"a": 10, "b": 2, "c": 3}
    assert len(warnings) == 0


def test_deep_merge_warns_about_removed_fields():
    """Test that warnings are generated for removed fields."""
    new_default = {"a": 1, "b": 2}
    existing = {"a": 10, "b": 20, "c": 30}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"a": 10, "b": 20}
    assert len(warnings) == 1
    assert warnings[0].path == "c"
    assert "no longer exists" in warnings[0].message.lower()


def test_deep_merge_nested_dicts():
    """Test deep merging of nested dictionaries."""
    new_default = {
        "outer": {
            "a": 1,
            "b": 2,
            "nested": {"x": 10, "y": 20},
        },
    }
    existing = {
        "outer": {
            "a": 100,
            "nested": {"x": 999},
        },
    }

    result, warnings = deep_merge(new_default, existing)

    assert result == {
        "outer": {
            "a": 100,
            "b": 2,
            "nested": {"x": 999, "y": 20},
        },
    }
    assert len(warnings) == 0


def test_deep_merge_warns_about_nested_removed_fields():
    """Test warnings for removed fields in nested structures."""
    new_default = {"outer": {"a": 1}}
    existing = {"outer": {"a": 10, "b": 20}}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"outer": {"a": 10}}
    assert len(warnings) == 1
    assert "outer.b" in warnings[0].path


def test_deep_merge_type_mismatch_warning():
    """Test that type mismatches generate warnings."""
    new_default = {"field": 42}
    existing = {"field": "string"}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"field": 42}  # Uses new default
    assert len(warnings) == 1
    assert "type" in warnings[0].message.lower()


def test_deep_merge_nested_type_mismatch():
    """Test type mismatch in nested structure."""
    new_default = {"outer": {"inner": 42}}
    existing = {"outer": "string"}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"outer": {"inner": 42}}
    assert len(warnings) == 1


def test_deep_merge_preserves_non_dict_values():
    """Test that non-dict values of same type are preserved."""
    new_default = {"num": 0, "text": "", "flag": False}
    existing = {"num": 42, "text": "hello", "flag": True}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"num": 42, "text": "hello", "flag": True}
    assert len(warnings) == 0


def test_deep_merge_empty_existing():
    """Test merging when existing data is empty."""
    new_default = {"a": 1, "b": 2}
    existing = {}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"a": 1, "b": 2}
    assert len(warnings) == 0


def test_deep_merge_empty_new_default():
    """Test merging when new default is empty."""
    new_default = {}
    existing = {"a": 1, "b": 2}

    result, warnings = deep_merge(new_default, existing)

    assert result == {}
    assert len(warnings) == 2  # Both fields removed


def test_deep_merge_complex_nested_structure():
    """Test merging with complex nested structures."""
    new_default = {
        "scope1": {"model": {"field1": 1, "field2": 2}},
        "scope2": {"model": {"field3": 3}},
    }
    existing = {
        "scope1": {"model": {"field1": 100, "old_field": 999}},
        "scope2": {"model": {"field3": 300}},
    }

    result, warnings = deep_merge(new_default, existing)

    assert result == {
        "scope1": {"model": {"field1": 100, "field2": 2}},
        "scope2": {"model": {"field3": 300}},
    }
    assert len(warnings) == 1
    assert "old_field" in warnings[0].path


def test_update_input_data_returns_update_result():
    """Test that update_input_data returns UpdateResult."""
    new_default = {"a": 1}
    existing = {"a": 10}

    result = update_input_data(new_default, existing)

    assert isinstance(result, UpdateResult)
    assert result.updated_data == {"a": 10}
    assert isinstance(result.warnings, list)


def test_update_input_data_with_warnings():
    """Test update_input_data with warnings."""
    new_default = {"a": 1}
    existing = {"a": 10, "b": 20}

    result = update_input_data(new_default, existing)

    assert result.updated_data == {"a": 10}
    assert len(result.warnings) == 1
    assert isinstance(result.warnings[0], UpdateWarning)


def test_deep_merge_path_tracking():
    """Test that warning paths are correctly tracked through nested structures."""
    new_default = {
        "level1": {
            "level2": {
                "level3": {"field": 1},
            },
        },
    }
    existing = {
        "level1": {
            "level2": {
                "level3": {"field": 100, "removed": 999},
            },
        },
    }

    _result, warnings = deep_merge(new_default, existing)

    assert len(warnings) == 1
    assert warnings[0].path == "level1.level2.level3.removed"


def test_deep_merge_multiple_warnings():
    """Test that multiple warnings are collected."""
    new_default = {"a": 1, "b": {"c": 2}}
    existing = {"a": 10, "b": {"c": 20, "d": 30}, "e": 40}

    _result, warnings = deep_merge(new_default, existing)

    assert len(warnings) == 2
    paths = {w.path for w in warnings}
    assert "b.d" in paths
    assert "e" in paths


def test_deep_merge_list_values():
    """Test that list values are preserved when types match."""
    new_default = {"items": [1, 2, 3]}
    existing = {"items": [4, 5, 6]}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"items": [4, 5, 6]}
    assert len(warnings) == 0


def test_deep_merge_dict_to_list_type_mismatch():
    """Test type mismatch between dict and list."""
    new_default = {"field": {"a": 1}}
    existing = {"field": [1, 2, 3]}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"field": {"a": 1}}
    assert len(warnings) == 1
    assert "type" in warnings[0].message.lower()


class Mode(StrEnum):
    """Test enum for StrEnum tests."""

    NOMINAL = "nominal"
    SAFE = "safe"


def test_deep_merge_strenum_default_with_string_existing():
    """Test that StrEnum default and string existing are treated as compatible.

    StrEnum values are stored as plain strings in TOML files, so when the schema
    has a StrEnum default and the existing value is a string, they should be
    treated as compatible types (no false positive type mismatch warning).
    """
    new_default = {"mode": Mode.NOMINAL}
    existing = {"mode": "safe"}  # Plain string from TOML

    result, warnings = deep_merge(new_default, existing)

    # Should preserve existing string value without type mismatch warning
    assert result == {"mode": "safe"}
    assert len(warnings) == 0


def test_deep_merge_string_default_with_strenum_existing():
    """Test that string default and StrEnum existing are also compatible."""
    new_default = {"mode": "nominal"}
    existing = {"mode": Mode.SAFE}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"mode": Mode.SAFE}
    assert len(warnings) == 0


def test_deep_merge_strenum_nested():
    """Test StrEnum handling in nested structures."""
    new_default = {"config": {"mode": Mode.NOMINAL, "value": 10}}
    existing = {"config": {"mode": "safe", "value": 20}}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"config": {"mode": "safe", "value": 20}}
    assert len(warnings) == 0


def test_deep_merge_int_compatible_with_float():
    """Test that int values are compatible with float schema fields.

    TOML files may store integer values (e.g., 100) for fields that the schema
    defines as float. These should be treated as compatible without warnings,
    and the int value should be preserved to maintain TOML formatting.
    """
    new_default = {"temperature": 0.0}
    existing = {"temperature": 100}  # int from TOML

    result, warnings = deep_merge(new_default, existing)

    assert result == {"temperature": 100}  # Preserved as int
    assert len(warnings) == 0


def test_deep_merge_int_compatible_with_float_nested():
    """Test int/float compatibility in nested structures."""
    new_default = {"sensor": {"temperature": 0.0, "pressure": 0.0}}
    existing = {"sensor": {"temperature": 25, "pressure": 101}}

    result, warnings = deep_merge(new_default, existing)

    assert result == {"sensor": {"temperature": 25, "pressure": 101}}
    assert len(warnings) == 0
