"""Tests for I/O serialization logic in veriq._io."""

from enum import StrEnum, unique

from pydantic import BaseModel

import veriq as vq
from veriq._io import (
    _parts_to_keys,
    _serialize_value,
    _set_nested_value,
    results_to_dict,
    toml_to_model_data,
)
from veriq._path import (
    AttributePart,
    CalcPath,
    ItemPart,
    ModelPath,
    ProjectPath,
    VerificationPath,
)

# --- Test Fixtures ---


@unique
class Color(StrEnum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


@unique
class Size(StrEnum):
    SMALL = "small"
    LARGE = "large"


class SimpleModel(BaseModel):
    value: float
    name: str


class NestedModel(BaseModel):
    inner: SimpleModel
    count: int


# --- _serialize_value() Tests ---


class TestSerializeValue:
    def test_serialize_primitive_int(self):
        assert _serialize_value(42) == 42

    def test_serialize_primitive_float(self):
        assert _serialize_value(3.14) == 3.14

    def test_serialize_primitive_str(self):
        assert _serialize_value("hello") == "hello"

    def test_serialize_primitive_bool(self):
        assert _serialize_value(value=True) is True
        assert _serialize_value(value=False) is False

    def test_serialize_basemodel(self):
        model = SimpleModel(value=1.5, name="test")
        result = _serialize_value(model)
        assert result == {"value": 1.5, "name": "test"}

    def test_serialize_nested_basemodel(self):
        model = NestedModel(inner=SimpleModel(value=2.5, name="inner"), count=10)
        result = _serialize_value(model)
        assert result == {"inner": {"value": 2.5, "name": "inner"}, "count": 10}

    def test_serialize_table_single_key(self):
        table = vq.Table({Color.RED: 1.0, Color.GREEN: 2.0, Color.BLUE: 3.0})
        result = _serialize_value(table)
        assert result == {"red": 1.0, "green": 2.0, "blue": 3.0}

    def test_serialize_table_tuple_key(self):
        # Table requires all combinations of enum keys
        table = vq.Table(
            {
                (Color.RED, Size.SMALL): 1.0,
                (Color.RED, Size.LARGE): 2.0,
                (Color.GREEN, Size.SMALL): 3.0,
                (Color.GREEN, Size.LARGE): 4.0,
                (Color.BLUE, Size.SMALL): 5.0,
                (Color.BLUE, Size.LARGE): 6.0,
            },
        )
        result = _serialize_value(table)
        assert result == {
            "red,small": 1.0,
            "red,large": 2.0,
            "green,small": 3.0,
            "green,large": 4.0,
            "blue,small": 5.0,
            "blue,large": 6.0,
        }

    def test_serialize_table_with_basemodel_value(self):
        # Table requires all enum keys
        table = vq.Table(
            {
                Color.RED: SimpleModel(value=1.0, name="red_model"),
                Color.GREEN: SimpleModel(value=2.0, name="green_model"),
                Color.BLUE: SimpleModel(value=3.0, name="blue_model"),
            },
        )
        result = _serialize_value(table)
        assert result == {
            "red": {"value": 1.0, "name": "red_model"},
            "green": {"value": 2.0, "name": "green_model"},
            "blue": {"value": 3.0, "name": "blue_model"},
        }

    def test_serialize_dict(self):
        data = {"a": 1, "b": {"c": 2}}
        result = _serialize_value(data)
        assert result == {"a": 1, "b": {"c": 2}}

    def test_serialize_list(self):
        data = [1, 2, 3]
        result = _serialize_value(data)
        assert result == [1, 2, 3]

    def test_serialize_tuple(self):
        data = (1, 2, 3)
        result = _serialize_value(data)
        assert result == [1, 2, 3]  # Converted to list

    def test_serialize_nested_list(self):
        data = [SimpleModel(value=1.0, name="a"), SimpleModel(value=2.0, name="b")]
        result = _serialize_value(data)
        assert result == [{"value": 1.0, "name": "a"}, {"value": 2.0, "name": "b"}]


# --- _parts_to_keys() Tests ---


class TestPartsToKeys:
    def test_empty_parts(self):
        result = _parts_to_keys(())
        assert result == []

    def test_single_attribute(self):
        parts = (AttributePart("field"),)
        result = _parts_to_keys(parts)
        assert result == ["field"]

    def test_multiple_attributes(self):
        parts = (AttributePart("a"), AttributePart("b"), AttributePart("c"))
        result = _parts_to_keys(parts)
        assert result == ["a", "b", "c"]

    def test_single_item(self):
        parts = (ItemPart("key"),)
        result = _parts_to_keys(parts)
        assert result == ["key"]

    def test_tuple_item(self):
        parts = (ItemPart(("key1", "key2")),)
        result = _parts_to_keys(parts)
        assert result == ["key1,key2"]

    def test_mixed_parts(self):
        parts = (AttributePart("table"), ItemPart("key"), AttributePart("field"))
        result = _parts_to_keys(parts)
        assert result == ["table", "key", "field"]


# --- _set_nested_value() Tests ---


class TestSetNestedValue:
    def test_single_key(self):
        data: dict = {}
        _set_nested_value(data, ["key"], "value")
        assert data == {"key": "value"}

    def test_nested_keys(self):
        data: dict = {}
        _set_nested_value(data, ["a", "b", "c"], 42)
        assert data == {"a": {"b": {"c": 42}}}

    def test_creates_intermediate_dicts(self):
        data: dict = {}
        _set_nested_value(data, ["level1", "level2", "level3"], "deep")
        assert "level1" in data
        assert "level2" in data["level1"]
        assert data["level1"]["level2"]["level3"] == "deep"

    def test_preserves_existing_keys(self):
        data = {"a": {"existing": "value"}}
        _set_nested_value(data, ["a", "new"], "new_value")
        assert data == {"a": {"existing": "value", "new": "new_value"}}

    def test_serializes_value(self):
        data: dict = {}
        model = SimpleModel(value=1.0, name="test")
        _set_nested_value(data, ["model"], model)
        assert data == {"model": {"value": 1.0, "name": "test"}}


# --- results_to_dict() Tests ---


class TestResultsToDict:
    def test_model_path(self):
        results = {
            ProjectPath(
                scope="Power", path=ModelPath(root="$", parts=(AttributePart("value"),)),
            ): 42.0,
        }
        result = results_to_dict(results)
        assert result == {"Power": {"model": {"value": 42.0}}}

    def test_calc_path(self):
        results = {
            ProjectPath(
                scope="Power",
                path=CalcPath(root="@my_calc", parts=(AttributePart("output"),)),
            ): 100.0,
        }
        result = results_to_dict(results)
        assert result == {"Power": {"calc": {"my_calc": {"output": 100.0}}}}

    def test_verification_path_bool(self):
        results = {
            ProjectPath(
                scope="Power",
                path=VerificationPath(root="?my_verif", parts=()),
            ): True,
        }
        result = results_to_dict(results)
        assert result == {"Power": {"verification": {"my_verif": True}}}

    def test_verification_path_table(self):
        results = {
            ProjectPath(
                scope="Power",
                path=VerificationPath(root="?my_verif", parts=(ItemPart("red"),)),
            ): True,
            ProjectPath(
                scope="Power",
                path=VerificationPath(root="?my_verif", parts=(ItemPart("green"),)),
            ): False,
        }
        result = results_to_dict(results)
        assert result == {
            "Power": {"verification": {"my_verif": {"red": True, "green": False}}},
        }

    def test_multiple_scopes(self):
        results = {
            ProjectPath(
                scope="Power", path=ModelPath(root="$", parts=(AttributePart("a"),)),
            ): 1.0,
            ProjectPath(
                scope="Thermal", path=ModelPath(root="$", parts=(AttributePart("b"),)),
            ): 2.0,
        }
        result = results_to_dict(results)
        assert result == {
            "Power": {"model": {"a": 1.0}},
            "Thermal": {"model": {"b": 2.0}},
        }

    def test_combined_paths(self):
        results = {
            ProjectPath(
                scope="Power", path=ModelPath(root="$", parts=(AttributePart("input"),)),
            ): 10.0,
            ProjectPath(
                scope="Power",
                path=CalcPath(root="@calc", parts=(AttributePart("output"),)),
            ): 20.0,
            ProjectPath(
                scope="Power",
                path=VerificationPath(root="?verif", parts=()),
            ): True,
        }
        result = results_to_dict(results)
        assert result == {
            "Power": {
                "model": {"input": 10.0},
                "calc": {"calc": {"output": 20.0}},
                "verification": {"verif": True},
            },
        }


# --- toml_to_model_data() Tests ---


class TestTomlToModelData:
    def test_basic_conversion(self):
        # Set up a project with a scope
        project = vq.Project("TestProject")
        scope = vq.Scope("TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            value: float
            name: str

        toml_contents = {
            "TestScope": {
                "model": {"value": 3.14, "name": "pi"},
            },
        }

        result = toml_to_model_data(project, toml_contents)

        assert "TestScope" in result
        assert isinstance(result["TestScope"], TestModel)
        assert result["TestScope"].value == 3.14
        assert result["TestScope"].name == "pi"

    def test_missing_scope_in_toml(self):
        project = vq.Project("TestProject")
        scope = vq.Scope("TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            value: float

        # TOML has different scope
        toml_contents = {"OtherScope": {"model": {"value": 1.0}}}

        result = toml_to_model_data(project, toml_contents)

        # TestScope should not be in result since it's not in TOML
        assert "TestScope" not in result

    def test_missing_model_key_in_scope(self):
        project = vq.Project("TestProject")
        scope = vq.Scope("TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            value: float

        # TOML has scope but no 'model' key
        toml_contents = {"TestScope": {"other_key": {"value": 1.0}}}

        result = toml_to_model_data(project, toml_contents)

        assert "TestScope" not in result

    def test_with_table_field(self):
        project = vq.Project("TestProject")
        scope = vq.Scope("TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            data: vq.Table[Color, float]

        toml_contents = {
            "TestScope": {
                "model": {
                    "data": {"red": 1.0, "green": 2.0, "blue": 3.0},
                },
            },
        }

        result = toml_to_model_data(project, toml_contents)

        assert "TestScope" in result
        assert result["TestScope"].data[Color.RED] == 1.0  # ty: ignore[unresolved-attribute]
        assert result["TestScope"].data[Color.GREEN] == 2.0  # ty: ignore[unresolved-attribute]
        assert result["TestScope"].data[Color.BLUE] == 3.0  # ty: ignore[unresolved-attribute]

    def test_multiple_scopes(self):
        project = vq.Project("TestProject")
        scope_a = vq.Scope("ScopeA")
        scope_b = vq.Scope("ScopeB")
        project.add_scope(scope_a)
        project.add_scope(scope_b)

        @scope_a.root_model()
        class ModelA(BaseModel):
            a_value: float

        @scope_b.root_model()
        class ModelB(BaseModel):
            b_value: str

        toml_contents = {
            "ScopeA": {"model": {"a_value": 1.0}},
            "ScopeB": {"model": {"b_value": "hello"}},
        }

        result = toml_to_model_data(project, toml_contents)

        assert "ScopeA" in result
        assert "ScopeB" in result
        assert result["ScopeA"].a_value == 1.0  # ty: ignore[unresolved-attribute]
        assert result["ScopeB"].b_value == "hello"  # ty: ignore[unresolved-attribute]
