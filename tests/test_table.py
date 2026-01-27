from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._path import CalcPath, ItemPart, ProjectPath


class Option(StrEnum):
    OPTION_A = "option_a"
    OPTION_B = "option_b"


class Region(StrEnum):
    NORTH = "north"
    SOUTH = "south"


class Product(StrEnum):
    WIDGET = "widget"
    GADGET = "gadget"


def test_table_as_calc_output() -> None:
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[Option, float]

    @scope.calculation()
    def output_table(
        input_table: Annotated[vq.Table[Option, float], vq.Ref("$.input_table")],
    ) -> vq.Table[Option, float]:
        # Transform the input table by multiplying by 2
        return vq.Table(  # ty: ignore[invalid-return-type]
            {
                Option.OPTION_A: input_table[Option.OPTION_A] * 2,
                Option.OPTION_B: input_table[Option.OPTION_B] * 2,
            },
        )

    # Create model data
    model_data = {
        scope.name: RootModel(
            input_table=vq.Table(  # ty: ignore[invalid-argument-type]
                {
                    Option.OPTION_A: 3.14,
                    Option.OPTION_B: 2.71,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    # Verify leaf values directly (tree model stores only leaf values)
    option_a_value = result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key="option_a"),)),
        ),
    )
    option_b_value = result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key="option_b"),)),
        ),
    )

    assert option_a_value == 6.28
    assert option_b_value == 5.42


def test_table_as_calc_output_with_calc_input() -> None:
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[Option, float]

    @scope.calculation()
    def double_table(
        input_table: Annotated[vq.Table[Option, float], vq.Ref("$.input_table")],
    ) -> vq.Table[Option, float]:
        # Transform the input table by multiplying by 2
        return vq.Table(  # ty: ignore[invalid-return-type]
            {
                Option.OPTION_A: input_table[Option.OPTION_A] * 2,
                Option.OPTION_B: input_table[Option.OPTION_B] * 2,
            },
        )

    @scope.calculation()
    def output_table(
        doubled_table: Annotated[vq.Table[Option, float], vq.Ref("@double_table")],
    ) -> vq.Table[Option, float]:
        # Further transform the doubled table by multiplying by 3
        return vq.Table(  # ty: ignore[invalid-return-type]
            {
                Option.OPTION_A: doubled_table[Option.OPTION_A] * 3,
                Option.OPTION_B: doubled_table[Option.OPTION_B] * 3,
            },
        )

    # Create model data
    model_data = {
        "Test Scope": RootModel(
            input_table=vq.Table(  # ty: ignore[invalid-argument-type]
                {
                    Option.OPTION_A: 3.14,
                    Option.OPTION_B: 2.71,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    # Verify leaf values directly (tree model stores only leaf values)
    option_a_value = result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key="option_a"),)),
        ),
    )
    option_b_value = result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key="option_b"),)),
        ),
    )

    assert option_a_value == 3.14 * 2 * 3
    assert option_b_value == 2.71 * 2 * 3


def test_table_with_tuple_index_as_calc_output() -> None:
    """Test table with tuple of StrEnums as index."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[tuple[Region, Product], float]

    @scope.calculation()
    def output_table(
        input_table: Annotated[vq.Table[tuple[Region, Product], float], vq.Ref("$.input_table")],
    ) -> vq.Table[tuple[Region, Product], float]:
        # Transform the input table by multiplying by 2
        return vq.Table(  # ty: ignore[invalid-return-type]
            {
                (Region.NORTH, Product.WIDGET): input_table[(Region.NORTH, Product.WIDGET)] * 2,
                (Region.NORTH, Product.GADGET): input_table[(Region.NORTH, Product.GADGET)] * 2,
                (Region.SOUTH, Product.WIDGET): input_table[(Region.SOUTH, Product.WIDGET)] * 2,
                (Region.SOUTH, Product.GADGET): input_table[(Region.SOUTH, Product.GADGET)] * 2,
            },
        )

    # Create model data
    model_data = {
        scope.name: RootModel(
            input_table=vq.Table(  # ty: ignore[invalid-argument-type]
                {
                    (Region.NORTH, Product.WIDGET): 10.0,
                    (Region.NORTH, Product.GADGET): 20.0,
                    (Region.SOUTH, Product.WIDGET): 30.0,
                    (Region.SOUTH, Product.GADGET): 40.0,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    # Verify leaf values directly (tree model stores only leaf values)
    # Tuple keys are stored in ItemPart
    assert result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key=("north", "widget")),)),
        ),
    ) == 20.0
    assert result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key=("north", "gadget")),)),
        ),
    ) == 40.0
    assert result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key=("south", "widget")),)),
        ),
    ) == 60.0
    assert result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key=("south", "gadget")),)),
        ),
    ) == 80.0


def test_table_with_tuple_index_as_calc_output_with_calc_input() -> None:
    """Test table with tuple of StrEnums as index with chained calculations."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[tuple[Region, Product], float]

    @scope.calculation()
    def double_table(
        input_table: Annotated[vq.Table[tuple[Region, Product], float], vq.Ref("$.input_table")],
    ) -> vq.Table[tuple[Region, Product], float]:
        # Transform the input table by multiplying by 2
        return vq.Table(  # ty: ignore[invalid-return-type]
            {
                (Region.NORTH, Product.WIDGET): input_table[(Region.NORTH, Product.WIDGET)] * 2,
                (Region.NORTH, Product.GADGET): input_table[(Region.NORTH, Product.GADGET)] * 2,
                (Region.SOUTH, Product.WIDGET): input_table[(Region.SOUTH, Product.WIDGET)] * 2,
                (Region.SOUTH, Product.GADGET): input_table[(Region.SOUTH, Product.GADGET)] * 2,
            },
        )

    @scope.calculation()
    def output_table(
        doubled_table: Annotated[vq.Table[tuple[Region, Product], float], vq.Ref("@double_table")],
    ) -> vq.Table[tuple[Region, Product], float]:
        # Further transform the doubled table by multiplying by 3
        return vq.Table(  # ty: ignore[invalid-return-type]
            {
                (Region.NORTH, Product.WIDGET): doubled_table[(Region.NORTH, Product.WIDGET)] * 3,
                (Region.NORTH, Product.GADGET): doubled_table[(Region.NORTH, Product.GADGET)] * 3,
                (Region.SOUTH, Product.WIDGET): doubled_table[(Region.SOUTH, Product.WIDGET)] * 3,
                (Region.SOUTH, Product.GADGET): doubled_table[(Region.SOUTH, Product.GADGET)] * 3,
            },
        )

    # Create model data
    model_data = {
        "Test Scope": RootModel(
            input_table=vq.Table(  # ty: ignore[invalid-argument-type]
                {
                    (Region.NORTH, Product.WIDGET): 10.0,
                    (Region.NORTH, Product.GADGET): 20.0,
                    (Region.SOUTH, Product.WIDGET): 30.0,
                    (Region.SOUTH, Product.GADGET): 40.0,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    # Verify leaf values directly (tree model stores only leaf values)
    assert result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key=("north", "widget")),)),
        ),
    ) == 10.0 * 2 * 3
    assert result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key=("north", "gadget")),)),
        ),
    ) == 20.0 * 2 * 3
    assert result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key=("south", "widget")),)),
        ),
    ) == 30.0 * 2 * 3
    assert result.get_value(
        ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key=("south", "gadget")),)),
        ),
    ) == 40.0 * 2 * 3


def test_table_with_triple_tuple_index() -> None:
    """Test table with tuple of 3 StrEnums as index."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        input_table: vq.Table[tuple[Region, Product, Option], float]

    @scope.calculation()
    def output_table(
        input_table: Annotated[vq.Table[tuple[Region, Product, Option], float], vq.Ref("$.input_table")],
    ) -> vq.Table[tuple[Region, Product, Option], float]:
        # Transform the input table by adding 100
        return vq.Table(  # ty: ignore[invalid-return-type]
            {
                (Region.NORTH, Product.WIDGET, Option.OPTION_A): input_table[
                    (Region.NORTH, Product.WIDGET, Option.OPTION_A)
                ]
                + 100,
                (Region.NORTH, Product.WIDGET, Option.OPTION_B): input_table[
                    (Region.NORTH, Product.WIDGET, Option.OPTION_B)
                ]
                + 100,
                (Region.NORTH, Product.GADGET, Option.OPTION_A): input_table[
                    (Region.NORTH, Product.GADGET, Option.OPTION_A)
                ]
                + 100,
                (Region.NORTH, Product.GADGET, Option.OPTION_B): input_table[
                    (Region.NORTH, Product.GADGET, Option.OPTION_B)
                ]
                + 100,
                (Region.SOUTH, Product.WIDGET, Option.OPTION_A): input_table[
                    (Region.SOUTH, Product.WIDGET, Option.OPTION_A)
                ]
                + 100,
                (Region.SOUTH, Product.WIDGET, Option.OPTION_B): input_table[
                    (Region.SOUTH, Product.WIDGET, Option.OPTION_B)
                ]
                + 100,
                (Region.SOUTH, Product.GADGET, Option.OPTION_A): input_table[
                    (Region.SOUTH, Product.GADGET, Option.OPTION_A)
                ]
                + 100,
                (Region.SOUTH, Product.GADGET, Option.OPTION_B): input_table[
                    (Region.SOUTH, Product.GADGET, Option.OPTION_B)
                ]
                + 100,
            },
        )

    # Create model data
    model_data = {
        scope.name: RootModel(
            input_table=vq.Table(  # ty: ignore[invalid-argument-type]
                {
                    (Region.NORTH, Product.WIDGET, Option.OPTION_A): 1.0,
                    (Region.NORTH, Product.WIDGET, Option.OPTION_B): 2.0,
                    (Region.NORTH, Product.GADGET, Option.OPTION_A): 3.0,
                    (Region.NORTH, Product.GADGET, Option.OPTION_B): 4.0,
                    (Region.SOUTH, Product.WIDGET, Option.OPTION_A): 5.0,
                    (Region.SOUTH, Product.WIDGET, Option.OPTION_B): 6.0,
                    (Region.SOUTH, Product.GADGET, Option.OPTION_A): 7.0,
                    (Region.SOUTH, Product.GADGET, Option.OPTION_B): 8.0,
                },
            ),
        ),
    }

    # Evaluate the project
    result = evaluate_project(project, model_data)

    # Check that the calculation was evaluated correctly
    # Verify leaf values directly (tree model stores only leaf values)
    def make_path(key: tuple[str, str, str]) -> ProjectPath:
        return ProjectPath(
            scope="Test Scope",
            path=CalcPath(root="@output_table", parts=(ItemPart(key=key),)),
        )

    assert result.get_value(make_path(("north", "widget", "option_a"))) == 101.0
    assert result.get_value(make_path(("north", "widget", "option_b"))) == 102.0
    assert result.get_value(make_path(("north", "gadget", "option_a"))) == 103.0
    assert result.get_value(make_path(("north", "gadget", "option_b"))) == 104.0
    assert result.get_value(make_path(("south", "widget", "option_a"))) == 105.0
    assert result.get_value(make_path(("south", "widget", "option_b"))) == 106.0
    assert result.get_value(make_path(("south", "gadget", "option_a"))) == 107.0
    assert result.get_value(make_path(("south", "gadget", "option_b"))) == 108.0
