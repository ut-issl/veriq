"""Tests for the pure schema-artifact comparison core."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._diff import DiffEntry, DiffKind
from veriq._schema import diff_schemas


@pytest.fixture
def generated_schema() -> dict[str, Any]:
    class Design(BaseModel):
        voltage: float
        capacity: float = 100.0

    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="Power")
    project.add_scope(scope)
    scope.root_model()(Design)
    return project.input_model().model_json_schema()


def test_in_sync_schema_has_no_differences(generated_schema: dict[str, Any]) -> None:
    committed = json.loads(json.dumps(generated_schema))
    assert diff_schemas(committed, generated_schema) == []


def test_comparison_is_semantic_not_textual(generated_schema: dict[str, Any]) -> None:
    committed = json.loads(json.dumps(generated_schema, indent=4, sort_keys=True))
    assert diff_schemas(committed, generated_schema) == []
    assert diff_schemas({"b": 2, "a": 1}, {"a": 1, "b": 2}) == []


def test_missing_property_reports_exact_path(generated_schema: dict[str, Any]) -> None:
    committed = copy.deepcopy(generated_schema)
    capacity = committed["$defs"]["Design"]["properties"].pop("capacity")

    assert diff_schemas(committed, generated_schema) == [
        DiffEntry(("$defs", "Design", "properties", "capacity"), DiffKind.ADDED, None, capacity),
    ]


def test_obsolete_property_reports_exact_path(generated_schema: dict[str, Any]) -> None:
    committed = copy.deepcopy(generated_schema)
    committed["$defs"]["Design"]["properties"]["obsolete"] = {"type": "string"}

    assert diff_schemas(committed, generated_schema) == [
        DiffEntry(("$defs", "Design", "properties", "obsolete"), DiffKind.REMOVED, {"type": "string"}, None),
    ]


def test_numeric_default_type_drift_reports_exact_path(generated_schema: dict[str, Any]) -> None:
    committed = copy.deepcopy(generated_schema)
    committed["$defs"]["Design"]["properties"]["capacity"]["default"] = 100

    entries = diff_schemas(committed, generated_schema)
    assert entries == [
        DiffEntry(("$defs", "Design", "properties", "capacity", "default"), DiffKind.CHANGED, 100, 100.0),
    ]
    assert type(entries[0].left) is int
    assert type(entries[0].right) is float


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (100, 100.0),
        (100.0, 100),
        (True, 1),
        (False, 0.0),
        ([100], [100.0]),
        ([{"default": True}], [{"default": 1}]),
        (["a", "b"], ["b", "a"]),
        ({"type": "number"}, "number"),
        (None, "null"),
        (1, 2),
    ],
)
def test_changed_values_preserve_json_distinctions(left: Any, right: Any) -> None:
    entries = diff_schemas({"value": left}, {"value": right})
    assert entries == [DiffEntry(("value",), DiffKind.CHANGED, left, right)]
    assert type(entries[0].left) is type(left)
    assert type(entries[0].right) is type(right)


def test_object_order_inside_arrays_is_ignored() -> None:
    assert diff_schemas({"enum": [{"b": 2, "a": 1}]}, {"enum": [{"a": 1, "b": 2}]}) == []


def test_mixed_changes_are_sorted_by_path() -> None:
    assert diff_schemas({"z": 0, "nested": {"b": 1}}, {"a": None, "nested": {"b": 2}}) == [
        DiffEntry(("a",), DiffKind.ADDED, None, None),
        DiffEntry(("nested", "b"), DiffKind.CHANGED, 1, 2),
        DiffEntry(("z",), DiffKind.REMOVED, 0, None),
    ]


def test_comparison_does_not_mutate_inputs(generated_schema: dict[str, Any]) -> None:
    committed = {"outdated": True}
    original_committed = copy.deepcopy(committed)
    original_generated = copy.deepcopy(generated_schema)

    diff_schemas(committed, generated_schema)

    assert committed == original_committed
    assert generated_schema == original_generated
