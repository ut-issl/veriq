"""Tests for path parsing and navigation logic in veriq._path."""

from enum import StrEnum, unique

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._path import (
    AttributePart,
    CalcPath,
    ItemPart,
    ModelPath,
    Path,
    ProjectPath,
    VerificationPath,
    get_value_by_parts,
    hydrate_value_by_leaf_values,
    iter_leaf_path_parts,
    parse_path,
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


class InnerModel(BaseModel):
    value: float
    name: str


class OuterModel(BaseModel):
    inner: InnerModel
    count: int


class ModelWithTable(BaseModel):
    data: vq.Table[Color, float]


class ModelWithTupleTable(BaseModel):
    matrix: vq.Table[tuple[Color, Size], float]


# --- Path.parse() Tests ---


class TestPathParse:
    @pytest.mark.parametrize(
        ("path_str", "expected_root", "expected_parts"),
        [
            ("$", "$", ()),
            ("@calc", "@calc", ()),
            ("?verify", "?verify", ()),
            ("root", "root", ()),
        ],
    )
    def test_parse_root_only(
        self, path_str: str, expected_root: str, expected_parts: tuple,
    ):
        path = Path.parse(path_str)
        assert path.root == expected_root
        assert path.parts == expected_parts

    @pytest.mark.parametrize(
        ("path_str", "expected_root", "expected_parts"),
        [
            ("$.field", "$", (AttributePart("field"),)),
            ("$.field.nested", "$", (AttributePart("field"), AttributePart("nested"))),
            (
                "$.a.b.c",
                "$",
                (AttributePart("a"), AttributePart("b"), AttributePart("c")),
            ),
            ("@calc.output", "@calc", (AttributePart("output"),)),
            (
                "@calc.output.nested",
                "@calc",
                (AttributePart("output"), AttributePart("nested")),
            ),
        ],
    )
    def test_parse_with_attributes(
        self, path_str: str, expected_root: str, expected_parts: tuple,
    ):
        path = Path.parse(path_str)
        assert path.root == expected_root
        assert path.parts == expected_parts

    @pytest.mark.parametrize(
        ("path_str", "expected_root", "expected_parts"),
        [
            ("$.table[key]", "$", (AttributePart("table"), ItemPart("key"))),
            ("$[key]", "$", (ItemPart("key"),)),
            ("@calc[idx]", "@calc", (ItemPart("idx"),)),
        ],
    )
    def test_parse_with_single_item(
        self, path_str: str, expected_root: str, expected_parts: tuple,
    ):
        path = Path.parse(path_str)
        assert path.root == expected_root
        assert path.parts == expected_parts

    @pytest.mark.parametrize(
        ("path_str", "expected_root", "expected_parts"),
        [
            (
                "$.table[key1,key2]",
                "$",
                (AttributePart("table"), ItemPart(("key1", "key2"))),
            ),
            (
                "$.matrix[red,small]",
                "$",
                (AttributePart("matrix"), ItemPart(("red", "small"))),
            ),
            ("$[a, b, c]", "$", (ItemPart(("a", "b", "c")),)),
        ],
    )
    def test_parse_with_tuple_item(
        self, path_str: str, expected_root: str, expected_parts: tuple,
    ):
        path = Path.parse(path_str)
        assert path.root == expected_root
        assert path.parts == expected_parts

    @pytest.mark.parametrize(
        ("path_str", "expected_root", "expected_parts"),
        [
            (
                "$.table[key].field",
                "$",
                (AttributePart("table"), ItemPart("key"), AttributePart("field")),
            ),
            (
                "$.a.b[x].c[y].d",
                "$",
                (
                    AttributePart("a"),
                    AttributePart("b"),
                    ItemPart("x"),
                    AttributePart("c"),
                    ItemPart("y"),
                    AttributePart("d"),
                ),
            ),
        ],
    )
    def test_parse_mixed_parts(
        self, path_str: str, expected_root: str, expected_parts: tuple,
    ):
        path = Path.parse(path_str)
        assert path.root == expected_root
        assert path.parts == expected_parts

    def test_parse_with_whitespace(self):
        path = Path.parse("  $.field  ")
        assert path.root == "$"
        assert path.parts == (AttributePart("field"),)


class TestPathStr:
    @pytest.mark.parametrize(
        "path_str",
        [
            "$",
            "$.field",
            "$.field.nested",
            "@calc",
            "@calc.output",
            "?verify",
        ],
    )
    def test_str_roundtrip_simple(self, path_str: str):
        path = Path.parse(path_str)
        assert str(path) == path_str

    def test_str_with_item(self):
        path = Path.parse("$.table[key]")
        assert str(path) == "$.table[key]"


# --- parse_path() Tests ---


class TestParsePath:
    def test_parse_model_path(self):
        path = parse_path("$.field")
        assert isinstance(path, ModelPath)
        assert path.root == "$"
        assert path.parts == (AttributePart("field"),)

    def test_parse_calc_path(self):
        path = parse_path("@calculation.output")
        assert isinstance(path, CalcPath)
        assert path.root == "@calculation"
        assert path.calc_name == "calculation"
        assert path.parts == (AttributePart("output"),)

    def test_parse_verification_path(self):
        path = parse_path("?verify_something")
        assert isinstance(path, VerificationPath)
        assert path.root == "?verify_something"
        assert path.verification_name == "verify_something"
        assert path.parts == ()

    def test_parse_verification_path_with_parts(self):
        path = parse_path("?verify[key]")
        assert isinstance(path, VerificationPath)
        assert path.verification_name == "verify"
        assert path.parts == (ItemPart("key"),)

    def test_parse_unknown_path_raises(self):
        with pytest.raises(ValueError, match="Unknown path type"):
            parse_path("unknown.path")


# --- ModelPath Tests ---


class TestModelPath:
    def test_valid_model_path(self):
        path = ModelPath.parse("$.field")
        assert path.root == "$"

    def test_invalid_root_raises(self):
        with pytest.raises(ValueError, match="ModelPath root must be"):
            ModelPath(root="@invalid", parts=())


# --- CalcPath Tests ---


class TestCalcPath:
    def test_valid_calc_path(self):
        path = CalcPath.parse("@calc.output")
        assert path.root == "@calc"
        assert path.calc_name == "calc"

    def test_invalid_prefix_raises(self):
        with pytest.raises(ValueError, match="CalcPath root must start with"):
            CalcPath(root="$invalid", parts=())


# --- VerificationPath Tests ---


class TestVerificationPath:
    def test_valid_verification_path(self):
        path = VerificationPath.parse("?verify")
        assert path.root == "?verify"
        assert path.verification_name == "verify"

    def test_invalid_prefix_raises(self):
        with pytest.raises(ValueError, match="VerificationPath root must start with"):
            VerificationPath(root="@invalid", parts=())


# --- ProjectPath Tests ---


class TestProjectPath:
    def test_project_path_str(self):
        ppath = ProjectPath(scope="Power", path=ModelPath.parse("$.field"))
        assert str(ppath) == "Power::$.field"


# --- get_value_by_parts() Tests ---


class TestGetValueByParts:
    def test_simple_attribute(self):
        model = InnerModel(value=42.0, name="test")
        parts = (AttributePart("value"),)
        result = get_value_by_parts(model, parts)
        assert result == 42.0

    def test_nested_attributes(self):
        model = OuterModel(inner=InnerModel(value=3.14, name="pi"), count=10)
        parts = (AttributePart("inner"), AttributePart("value"))
        result = get_value_by_parts(model, parts)
        assert result == 3.14

    def test_empty_parts_returns_model(self):
        model = InnerModel(value=1.0, name="one")
        parts: tuple[AttributePart, ...] = ()
        result = get_value_by_parts(model, parts)
        assert result == model

    def test_table_single_key(self):
        table = vq.Table({Color.RED: 1.0, Color.GREEN: 2.0, Color.BLUE: 3.0})
        model = ModelWithTable(data=table)  # ty: ignore[invalid-argument-type]
        parts = (AttributePart("data"), ItemPart("red"))
        result = get_value_by_parts(model, parts)
        assert result == 1.0

    def test_table_tuple_key(self):
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
        model = ModelWithTupleTable(matrix=table)  # ty: ignore[invalid-argument-type]
        parts = (AttributePart("matrix"), ItemPart(("green", "large")))
        result = get_value_by_parts(model, parts)
        assert result == 4.0


# --- iter_leaf_path_parts() Tests ---


class TestIterLeafPathParts:
    def test_primitive_type(self):
        parts = list(iter_leaf_path_parts(float))
        assert parts == [()]

    def test_basemodel_simple(self):
        parts = list(iter_leaf_path_parts(InnerModel))
        assert len(parts) == 2
        assert (AttributePart("value"),) in parts
        assert (AttributePart("name"),) in parts

    def test_basemodel_nested(self):
        parts = list(iter_leaf_path_parts(OuterModel))
        assert len(parts) == 3
        assert (AttributePart("inner"), AttributePart("value")) in parts
        assert (AttributePart("inner"), AttributePart("name")) in parts
        assert (AttributePart("count"),) in parts

    def test_table_single_key(self):
        parts = list(iter_leaf_path_parts(vq.Table[Color, float]))
        # Should yield the table itself plus each key
        assert () in parts  # The table itself
        assert (ItemPart("red"),) in parts
        assert (ItemPart("green"),) in parts
        assert (ItemPart("blue"),) in parts

    def test_table_tuple_key(self):
        parts = list(iter_leaf_path_parts(vq.Table[tuple[Color, Size], float]))
        # Should yield the table itself plus each key combination
        assert () in parts
        assert (ItemPart(("red", "small")),) in parts
        assert (ItemPart(("red", "large")),) in parts
        assert (ItemPart(("green", "small")),) in parts
        assert (ItemPart(("green", "large")),) in parts
        assert (ItemPart(("blue", "small")),) in parts
        assert (ItemPart(("blue", "large")),) in parts


# --- hydrate_value_by_leaf_values() Tests ---


class TestHydrateValueByLeafValues:
    def test_primitive(self):
        leaf_values = {(): 42.0}
        result = hydrate_value_by_leaf_values(float, leaf_values)
        assert result == 42.0

    def test_basemodel_simple(self):
        leaf_values = {
            (AttributePart("value"),): 3.14,
            (AttributePart("name"),): "pi",
        }
        result = hydrate_value_by_leaf_values(InnerModel, leaf_values)
        assert isinstance(result, InnerModel)
        assert result.value == 3.14
        assert result.name == "pi"

    def test_basemodel_nested(self):
        leaf_values = {
            (AttributePart("inner"), AttributePart("value")): 2.71,
            (AttributePart("inner"), AttributePart("name")): "e",
            (AttributePart("count"),): 5,
        }
        result = hydrate_value_by_leaf_values(OuterModel, leaf_values)
        assert isinstance(result, OuterModel)
        assert result.inner.value == 2.71
        assert result.inner.name == "e"
        assert result.count == 5

    def test_table_single_key(self):
        leaf_values = {
            (ItemPart("red"),): 1.0,
            (ItemPart("green"),): 2.0,
            (ItemPart("blue"),): 3.0,
        }
        result = hydrate_value_by_leaf_values(vq.Table[Color, float], leaf_values)
        assert isinstance(result, vq.Table)
        assert result[Color.RED] == 1.0
        assert result[Color.GREEN] == 2.0
        assert result[Color.BLUE] == 3.0

    def test_table_tuple_key(self):
        leaf_values = {
            (ItemPart(("red", "small")),): 1.0,
            (ItemPart(("red", "large")),): 2.0,
            (ItemPart(("green", "small")),): 3.0,
            (ItemPart(("green", "large")),): 4.0,
            (ItemPart(("blue", "small")),): 5.0,
            (ItemPart(("blue", "large")),): 6.0,
        }
        result = hydrate_value_by_leaf_values(
            vq.Table[tuple[Color, Size], float], leaf_values,
        )
        assert isinstance(result, vq.Table)
        assert result[(Color.RED, Size.SMALL)] == 1.0
        assert result[(Color.GREEN, Size.LARGE)] == 4.0
        assert result[(Color.BLUE, Size.SMALL)] == 5.0

    def test_empty_path_returns_value_directly(self):
        """When () is in leaf_values, it should return that value directly."""
        table = vq.Table({Color.RED: 1.0, Color.GREEN: 2.0, Color.BLUE: 3.0})
        leaf_values = {(): table}
        result = hydrate_value_by_leaf_values(vq.Table[Color, float], leaf_values)
        assert result is table

    def test_basemodel_with_generic_table_field(self):
        """Test hydrating a BaseModel that has a generic Table field.

        This tests the fix for the issubclass() error when field_type
        is a generic alias like Table[Color, float] instead of a class.
        """
        leaf_values = {
            (AttributePart("data"), ItemPart("red")): 1.0,
            (AttributePart("data"), ItemPart("green")): 2.0,
            (AttributePart("data"), ItemPart("blue")): 3.0,
        }
        result = hydrate_value_by_leaf_values(ModelWithTable, leaf_values)
        assert isinstance(result, ModelWithTable)
        assert isinstance(result.data, vq.Table)
        assert result.data[Color.RED] == 1.0
        assert result.data[Color.GREEN] == 2.0
        assert result.data[Color.BLUE] == 3.0
