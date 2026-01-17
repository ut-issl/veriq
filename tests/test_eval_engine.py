"""Tests for the evaluation engine module."""

from typing import Annotated

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._eval_engine import EvaluationResult, evaluate_graph
from veriq._ir import build_graph_spec
from veriq._path import AttributePart, CalcPath, ModelPath, ProjectPath, iter_leaf_path_parts


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_success_when_no_errors(self) -> None:
        result = EvaluationResult(values={}, errors=[])
        assert result.success is True

    def test_not_success_when_errors(self) -> None:
        path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=()))
        result = EvaluationResult(values={}, errors=[(path, "Some error")])
        assert result.success is False

    def test_get_value(self) -> None:
        path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
        result = EvaluationResult(values={path: 42.0}, errors=[])
        assert result.get_value(path) == 42.0

    def test_get_value_missing(self) -> None:
        result = EvaluationResult(values={}, errors=[])
        path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
        with pytest.raises(KeyError):
            result.get_value(path)


class TestEvaluateGraph:
    """Tests for evaluate_graph function."""

    def test_simple_calculation(self) -> None:
        """Test evaluating a simple calculation."""
        project = vq.Project(name="TestProject")
        scope = vq.Scope(name="TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            x: float

        @scope.calculation()
        def double_x(x: Annotated[float, vq.Ref("$.x")]) -> float:
            return x * 2

        # Build spec and initial values
        spec = build_graph_spec(project)
        initial_values = {
            ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=(AttributePart("x"),)),
            ): 5.0,
        }

        # Evaluate
        result = evaluate_graph(spec, initial_values)

        assert result.success
        # Find the calculation output
        calc_path = ProjectPath(
            scope="TestScope",
            path=CalcPath(root="@double_x", parts=()),
        )
        assert result.values[calc_path] == 10.0

    def test_chained_calculations(self) -> None:
        """Test evaluating chained calculations."""
        project = vq.Project(name="TestProject")
        scope = vq.Scope(name="TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            x: float

        @scope.calculation()
        def double_x(x: Annotated[float, vq.Ref("$.x")]) -> float:
            return x * 2

        @scope.calculation()
        def triple_doubled(doubled: Annotated[float, vq.Ref("@double_x")]) -> float:
            return doubled * 3

        spec = build_graph_spec(project)
        initial_values = {
            ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=(AttributePart("x"),)),
            ): 5.0,
        }

        result = evaluate_graph(spec, initial_values)

        assert result.success

        # double_x should be 10
        double_path = ProjectPath(
            scope="TestScope",
            path=CalcPath(root="@double_x", parts=()),
        )
        assert result.values[double_path] == 10.0

        # triple_doubled should be 30
        triple_path = ProjectPath(
            scope="TestScope",
            path=CalcPath(root="@triple_doubled", parts=()),
        )
        assert result.values[triple_path] == 30.0

    def test_verification(self) -> None:
        """Test evaluating a verification."""
        project = vq.Project(name="TestProject")
        scope = vq.Scope(name="TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            x: float

        @scope.verification()
        def x_positive(x: Annotated[float, vq.Ref("$.x")]) -> bool:
            return x > 0

        spec = build_graph_spec(project)

        # Test with positive value
        initial_values = {
            ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=(AttributePart("x"),)),
            ): 5.0,
        }

        result = evaluate_graph(spec, initial_values)
        assert result.success

        from veriq._path import VerificationPath

        verif_path = ProjectPath(
            scope="TestScope",
            path=VerificationPath(root="?x_positive", parts=()),
        )
        assert result.values[verif_path] is True

    def test_verification_fails(self) -> None:
        """Test verification that returns False."""
        project = vq.Project(name="TestProject")
        scope = vq.Scope(name="TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            x: float

        @scope.verification()
        def x_positive(x: Annotated[float, vq.Ref("$.x")]) -> bool:
            return x > 0

        spec = build_graph_spec(project)

        # Test with negative value
        initial_values = {
            ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=(AttributePart("x"),)),
            ): -5.0,
        }

        result = evaluate_graph(spec, initial_values)
        assert result.success  # Evaluation succeeded, but verification returned False

        from veriq._path import VerificationPath

        verif_path = ProjectPath(
            scope="TestScope",
            path=VerificationPath(root="?x_positive", parts=()),
        )
        assert result.values[verif_path] is False

    def test_multiple_inputs(self) -> None:
        """Test calculation with multiple inputs."""
        project = vq.Project(name="TestProject")
        scope = vq.Scope(name="TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            voltage: float
            current: float

        @scope.calculation()
        def power(
            voltage: Annotated[float, vq.Ref("$.voltage")],
            current: Annotated[float, vq.Ref("$.current")],
        ) -> float:
            return voltage * current

        spec = build_graph_spec(project)
        initial_values = {
            ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=(AttributePart("voltage"),)),
            ): 12.0,
            ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=(AttributePart("current"),)),
            ): 2.5,
        }

        result = evaluate_graph(spec, initial_values)

        assert result.success
        calc_path = ProjectPath(
            scope="TestScope",
            path=CalcPath(root="@power", parts=()),
        )
        assert result.values[calc_path] == 30.0

    def test_nested_model_input(self) -> None:
        """Test calculation with nested model as input."""
        project = vq.Project(name="TestProject")
        scope = vq.Scope(name="TestScope")
        project.add_scope(scope)

        class Inner(BaseModel):
            a: float
            b: float

        @scope.root_model()
        class Outer(BaseModel):
            inner: Inner

        @scope.calculation()
        def sum_inner(inner: Annotated[Inner, vq.Ref("$.inner")]) -> float:
            return inner.a + inner.b

        spec = build_graph_spec(project)

        # Create initial values for the nested structure
        initial_values = {
            ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=(AttributePart("inner"), AttributePart("a"))),
            ): 3.0,
            ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=(AttributePart("inner"), AttributePart("b"))),
            ): 7.0,
        }

        result = evaluate_graph(spec, initial_values)

        assert result.success
        calc_path = ProjectPath(
            scope="TestScope",
            path=CalcPath(root="@sum_inner", parts=()),
        )
        assert result.values[calc_path] == 10.0

    def test_missing_initial_value_error(self) -> None:
        """Test that missing initial values produce errors."""
        project = vq.Project(name="TestProject")
        scope = vq.Scope(name="TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            x: float

        @scope.calculation()
        def double_x(x: Annotated[float, vq.Ref("$.x")]) -> float:
            return x * 2

        spec = build_graph_spec(project)

        # Don't provide initial values
        result = evaluate_graph(spec, {})

        assert not result.success
        assert len(result.errors) > 0

    def test_calculation_output_with_model(self) -> None:
        """Test calculation that returns a Pydantic model."""
        project = vq.Project(name="TestProject")
        scope = vq.Scope(name="TestScope")
        project.add_scope(scope)

        class Result(BaseModel):
            doubled: float
            tripled: float

        @scope.root_model()
        class TestModel(BaseModel):
            x: float

        @scope.calculation()
        def compute(x: Annotated[float, vq.Ref("$.x")]) -> Result:
            return Result(doubled=x * 2, tripled=x * 3)

        spec = build_graph_spec(project)
        initial_values = {
            ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=(AttributePart("x"),)),
            ): 5.0,
        }

        result = evaluate_graph(spec, initial_values)

        assert result.success

        # Check both output fields
        doubled_path = ProjectPath(
            scope="TestScope",
            path=CalcPath(root="@compute", parts=(AttributePart("doubled"),)),
        )
        tripled_path = ProjectPath(
            scope="TestScope",
            path=CalcPath(root="@compute", parts=(AttributePart("tripled"),)),
        )

        assert result.values[doubled_path] == 10.0
        assert result.values[tripled_path] == 15.0


class TestEvaluateGraphIntegration:
    """Integration tests comparing new evaluate_graph with existing evaluate_project."""

    def test_matches_existing_evaluation(self) -> None:
        """Test that new evaluation produces same results as existing."""
        from veriq._eval import evaluate_project

        project = vq.Project(name="TestProject")
        scope = vq.Scope(name="TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestModel(BaseModel):
            x: float
            y: float

        @scope.calculation()
        def sum_xy(
            x: Annotated[float, vq.Ref("$.x")],
            y: Annotated[float, vq.Ref("$.y")],
        ) -> float:
            return x + y

        @scope.verification()
        def sum_positive(s: Annotated[float, vq.Ref("@sum_xy")]) -> bool:
            return s > 0

        # Create model data for existing evaluate_project
        model_data = {"TestScope": TestModel(x=3.0, y=7.0)}

        # Evaluate with existing function
        old_result = evaluate_project(project, model_data)

        # Build spec and initial values for new function
        spec = build_graph_spec(project)

        root_model = scope.get_root_model()
        initial_values = {}
        for leaf_parts in iter_leaf_path_parts(root_model):
            leaf_path = ProjectPath(
                scope="TestScope",
                path=ModelPath(root="$", parts=leaf_parts),
            )
            # Get value from model_data
            from veriq._path import get_value_by_parts

            value = get_value_by_parts(model_data["TestScope"], leaf_parts)
            initial_values[leaf_path] = value

        # Evaluate with new function
        new_result = evaluate_graph(spec, initial_values)

        assert new_result.success

        # Compare results for calculation
        calc_path = ProjectPath(
            scope="TestScope",
            path=CalcPath(root="@sum_xy", parts=()),
        )
        assert new_result.values[calc_path] == old_result[calc_path]

        # Compare results for verification
        from veriq._path import VerificationPath

        verif_path = ProjectPath(
            scope="TestScope",
            path=VerificationPath(root="?sum_positive", parts=()),
        )
        assert new_result.values[verif_path] == old_result[verif_path]
