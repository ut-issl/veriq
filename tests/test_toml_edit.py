"""Tests for TOML editing with comment preservation."""

from typing import Any

import pytest

from veriq._toml_edit import (
    dumps_toml,
    merge_into_document,
    parse_toml_preserving,
    set_nested_value,
    update_model_values,
    update_toml_document,
)


class TestUpdateTomlDocument:
    """Tests for update_toml_document function."""

    def test_preserves_header_comments(self):
        """Header comments before sections should be preserved."""
        original = """\
# Power subsystem configuration
[Power]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"Power": {"capacity": 150.0}})
        result = dumps_toml(doc)

        assert "# Power subsystem configuration" in result
        assert "capacity = 150.0" in result

    def test_preserves_inline_comments(self):
        """Inline comments after values should be preserved."""
        original = """\
[Power]
capacity = 100.0  # Maximum capacity in Wh
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"Power": {"capacity": 150.0}})
        result = dumps_toml(doc)

        assert "# Maximum capacity in Wh" in result
        assert "150.0" in result

    def test_preserves_comments_above_values(self):
        """Comments on the line above a value should be preserved."""
        original = """\
[Power]
# Battery capacity in watt-hours
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"Power": {"capacity": 150.0}})
        result = dumps_toml(doc)

        assert "# Battery capacity in watt-hours" in result
        assert "capacity = 150.0" in result

    def test_adds_new_keys(self):
        """New keys should be added to existing tables."""
        original = """\
[Power]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"Power": {"capacity": 100.0, "voltage": 12.0}})
        result = dumps_toml(doc)

        assert "capacity = 100.0" in result
        assert "voltage = 12.0" in result

    def test_adds_new_tables(self):
        """New tables should be added."""
        original = """\
[Power]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"Power": {"capacity": 100.0}, "Thermal": {"temp": 25.0}})
        result = dumps_toml(doc)

        assert "[Power]" in result
        assert "capacity = 100.0" in result
        assert "[Thermal]" in result
        assert "temp = 25.0" in result

    def test_updates_nested_values(self):
        """Nested table values should be updated correctly."""
        original = """\
[Power.model]
capacity = 100.0
voltage = 12.0
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"Power": {"model": {"capacity": 200.0}}})
        result = dumps_toml(doc)

        assert "capacity = 200.0" in result
        # voltage should remain unchanged
        assert "voltage = 12.0" in result

    def test_preserves_formatting(self):
        """Existing formatting should be preserved where possible."""
        original = """\
[Power]

capacity = 100.0

[Thermal]
temperature = 25.0
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"Power": {"capacity": 150.0}})
        result = dumps_toml(doc)

        # The structure should be preserved
        assert "[Power]" in result
        assert "[Thermal]" in result
        assert "capacity = 150.0" in result
        assert "temperature = 25.0" in result

    def test_handles_arrays(self):
        """Arrays should be updated correctly."""
        original = """\
[Power]
modes = ["nominal", "safe"]
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"Power": {"modes": ["nominal", "safe", "emergency"]}})
        result = dumps_toml(doc)

        assert "emergency" in result

    def test_handles_nested_dicts_in_arrays(self):
        """Arrays of tables should be handled."""
        original = """\
[[components]]
name = "battery"
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"components": [{"name": "battery", "capacity": 200.0}]})
        result = dumps_toml(doc)

        assert "battery" in result

    def test_preserves_multiline_comments(self):
        """Multi-line comment blocks should be preserved."""
        original = """\
# This is a multi-line comment
# that spans several lines
# explaining the power system
[Power]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"Power": {"capacity": 150.0}})
        result = dumps_toml(doc)

        assert "# This is a multi-line comment" in result
        assert "# that spans several lines" in result
        assert "# explaining the power system" in result
        assert "capacity = 150.0" in result


class TestSetNestedValue:
    """Tests for set_nested_value function."""

    def test_sets_top_level_value(self):
        """Setting a top-level value should work."""
        doc = parse_toml_preserving("")
        set_nested_value(doc, ["capacity"], 100.0)
        result = dumps_toml(doc)

        assert "capacity = 100.0" in result

    def test_creates_intermediate_tables(self):
        """Intermediate tables should be created as needed."""
        doc = parse_toml_preserving("")
        set_nested_value(doc, ["Power", "model", "capacity"], 100.0)
        result = dumps_toml(doc)

        assert "capacity = 100.0" in result

    def test_updates_existing_path(self):
        """Updating an existing path should work."""
        original = """\
[Power.model]
capacity = 50.0
"""
        doc = parse_toml_preserving(original)
        set_nested_value(doc, ["Power", "model", "capacity"], 100.0)
        result = dumps_toml(doc)

        assert "capacity = 100.0" in result

    def test_adds_to_existing_table(self):
        """Adding to an existing table should preserve other values."""
        original = """\
[Power.model]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        set_nested_value(doc, ["Power", "model", "voltage"], 12.0)
        result = dumps_toml(doc)

        assert "capacity = 100.0" in result
        assert "voltage = 12.0" in result

    def test_handles_empty_keys(self):
        """Empty keys list should be a no-op."""
        doc = parse_toml_preserving("[Power]\ncapacity = 100.0")
        set_nested_value(doc, [], 999)
        result = dumps_toml(doc)

        assert "capacity = 100.0" in result


class TestMergeIntoDocument:
    """Tests for merge_into_document function."""

    def test_preserves_existing_values(self):
        """Existing values should be preserved."""
        original = """\
# Important comment
[Power.model]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        new_data = {"Power": {"model": {"capacity": 999.0}}}  # Different default
        existing_data = {"Power": {"model": {"capacity": 100.0}}}

        merge_into_document(doc, new_data, existing_data)
        result = dumps_toml(doc)

        # Existing value should be preserved, not overwritten
        assert "capacity = 100.0" in result
        assert "# Important comment" in result

    def test_adds_new_fields(self):
        """New fields from schema should be added."""
        original = """\
[Power.model]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        new_data = {"Power": {"model": {"capacity": 100.0, "voltage": 12.0}}}
        existing_data = {"Power": {"model": {"capacity": 100.0}}}

        merge_into_document(doc, new_data, existing_data)
        result = dumps_toml(doc)

        assert "capacity = 100.0" in result
        assert "voltage = 12.0" in result

    def test_adds_new_scopes(self):
        """New scopes should be added."""
        original = """\
[Power.model]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        new_data = {
            "Power": {"model": {"capacity": 100.0}},
            "Thermal": {"model": {"temperature": 25.0}},
        }
        existing_data = {"Power": {"model": {"capacity": 100.0}}}

        merge_into_document(doc, new_data, existing_data)
        result = dumps_toml(doc)

        assert "[Power.model]" in result or "[Power]" in result
        assert "capacity = 100.0" in result
        assert "temperature = 25.0" in result

    def test_preserves_comments_when_adding_fields(self):
        """Comments should be preserved when adding new fields."""
        original = """\
# Power system configuration
[Power.model]
# Battery capacity
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        new_data = {"Power": {"model": {"capacity": 100.0, "voltage": 12.0}}}
        existing_data = {"Power": {"model": {"capacity": 100.0}}}

        merge_into_document(doc, new_data, existing_data)
        result = dumps_toml(doc)

        assert "# Power system configuration" in result
        assert "# Battery capacity" in result
        assert "capacity = 100.0" in result
        assert "voltage = 12.0" in result

    def test_handles_nested_new_tables(self):
        """Nested new tables should be handled correctly."""
        original = """\
[Power.model]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        new_data = {
            "Power": {
                "model": {
                    "capacity": 100.0,
                    "battery": {"type": "lithium", "cells": 4},
                },
            },
        }
        existing_data = {"Power": {"model": {"capacity": 100.0}}}

        merge_into_document(doc, new_data, existing_data)
        result = dumps_toml(doc)

        assert "capacity = 100.0" in result
        assert "lithium" in result
        assert "cells = 4" in result


class TestUpdateModelValues:
    """Tests for update_model_values function."""

    def test_updates_simple_field(self):
        """Simple field update should work."""
        original = """\
[Power.model]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        update_model_values(doc, "Power", ["capacity"], 150.0)
        result = dumps_toml(doc)

        assert "capacity = 150.0" in result

    def test_updates_nested_field(self):
        """Nested field update should work."""
        original = """\
[Power.model.battery]
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        update_model_values(doc, "Power", ["battery", "capacity"], 150.0)
        result = dumps_toml(doc)

        assert "capacity = 150.0" in result

    def test_creates_missing_structure(self):
        """Missing intermediate structure should be created."""
        doc = parse_toml_preserving("")
        update_model_values(doc, "Power", ["capacity"], 100.0)
        result = dumps_toml(doc)

        assert "capacity = 100.0" in result

    def test_preserves_comments(self):
        """Comments should be preserved when updating."""
        original = """\
# Power configuration
[Power.model]
# Battery capacity in Wh
capacity = 100.0
"""
        doc = parse_toml_preserving(original)
        update_model_values(doc, "Power", ["capacity"], 150.0)
        result = dumps_toml(doc)

        assert "# Power configuration" in result
        assert "# Battery capacity in Wh" in result
        assert "capacity = 150.0" in result


class TestParseAndDumps:
    """Tests for parse_toml_preserving and dumps_toml."""

    def test_round_trip_preserves_content(self):
        """Round-trip should preserve content exactly."""
        original = """\
# Header comment
[section]
key = "value"
"""
        doc = parse_toml_preserving(original)
        result = dumps_toml(doc)

        assert result == original

    def test_round_trip_preserves_complex_document(self):
        """Complex documents should round-trip correctly."""
        original = """\
# Project configuration
title = "My Project"

[Power.model]
# Battery capacity in watt-hours
capacity = 100.0  # Default value
voltage = 12.0

[Thermal.model]
temperature = 25.0
"""
        doc = parse_toml_preserving(original)
        result = dumps_toml(doc)

        assert "# Project configuration" in result
        assert "# Battery capacity in watt-hours" in result
        assert "# Default value" in result
        assert "capacity = 100.0" in result
        assert "voltage = 12.0" in result
        assert "temperature = 25.0" in result


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_handles_empty_document(self):
        """Empty document should be handled."""
        doc = parse_toml_preserving("")
        update_toml_document(doc, {"key": "value"})
        result = dumps_toml(doc)

        assert 'key = "value"' in result

    def test_handles_boolean_values(self):
        """Boolean values should be handled correctly."""
        original = "[config]\nenabled = false"
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"config": {"enabled": True}})
        result = dumps_toml(doc)

        assert "enabled = true" in result

    def test_handles_integer_values(self):
        """Integer values should be handled correctly."""
        original = "[config]\ncount = 10"
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"config": {"count": 20}})
        result = dumps_toml(doc)

        assert "count = 20" in result

    def test_handles_string_values(self):
        """String values should be handled correctly."""
        original = '[config]\nname = "old"'
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"config": {"name": "new"}})
        result = dumps_toml(doc)

        assert 'name = "new"' in result

    def test_handles_special_characters_in_strings(self):
        """Strings with special characters should be handled."""
        doc = parse_toml_preserving("")
        update_toml_document(doc, {"path": "/usr/local/bin"})
        result = dumps_toml(doc)

        assert "/usr/local/bin" in result

    def test_handles_deeply_nested_structure(self):
        """Deeply nested structures should be handled."""
        doc = parse_toml_preserving("")
        set_nested_value(doc, ["a", "b", "c", "d", "e"], "deep")
        result = dumps_toml(doc)

        assert 'e = "deep"' in result

    def test_preserves_table_order(self):
        """Table order should be preserved."""
        original = """\
[first]
a = 1

[second]
b = 2

[third]
c = 3
"""
        doc = parse_toml_preserving(original)
        update_toml_document(doc, {"second": {"b": 20}})
        result = dumps_toml(doc)

        # Check that order is preserved
        first_pos = result.find("[first]")
        second_pos = result.find("[second]")
        third_pos = result.find("[third]")

        assert first_pos < second_pos < third_pos


@pytest.mark.parametrize(
    ("value", "expected_str"),
    [
        (100, "100"),
        (100.5, "100.5"),
        (True, "true"),
        (False, "false"),
        ("hello", '"hello"'),
    ],
)
def test_value_types(value: Any, expected_str: str) -> None:
    """Various value types should be serialized correctly."""
    doc = parse_toml_preserving("")
    update_toml_document(doc, {"key": value})
    result = dumps_toml(doc)

    assert expected_str in result
