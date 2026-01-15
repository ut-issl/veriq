"""Tests for Table[K, bool] verification return type."""

from enum import StrEnum, auto, unique
from typing import Annotated, get_args, get_origin

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._path import ItemPart, ProjectPath, VerificationPath


@unique
class Mode(StrEnum):
    NOMINAL = auto()
    SAFE = auto()


@unique
class Phase(StrEnum):
    INITIAL = auto()
    CRUISE = auto()


def test_table_verification_return_type_validation() -> None:
    """Test that verification return type is validated correctly."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    # Valid: bool return type
    @scope.verification()
    def verify_bool(value: Annotated[float, vq.Ref("$.value")]) -> bool:
        return value > 0

    # Valid: Table[K, bool] return type
    @scope.verification()
    def verify_table(value: Annotated[float, vq.Ref("$.value")]) -> vq.Table[Mode, bool]:
        return vq.Table({
            Mode.NOMINAL: value > 0,
            Mode.SAFE: value > 10,
        })


def test_table_verification_invalid_return_type() -> None:
    """Test that invalid verification return types are rejected."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    # Invalid: Table[K, float] return type (not bool)
    with pytest.raises(TypeError, match="Return type must be 'bool' or 'Table\\[K, bool\\]'"):

        @scope.verification()
        def verify_invalid(value: Annotated[float, vq.Ref("$.value")]) -> vq.Table[Mode, float]:  # type: ignore[type-var]
            return vq.Table({
                Mode.NOMINAL: value,
                Mode.SAFE: value * 2,
            })


def test_table_verification_evaluation() -> None:
    """Test that Table[K, bool] verifications are evaluated correctly."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        margin: vq.Table[Mode, float]

    @scope.verification()
    def verify_margins(
        margin: Annotated[vq.Table[Mode, float], vq.Ref("$.margin")],
    ) -> vq.Table[Mode, bool]:
        return vq.Table({mode: margin[mode] > 0.1 for mode in Mode})

    # Create model data
    model_data = {
        "TestScope": TestModel(
            margin=vq.Table({
                Mode.NOMINAL: 0.2,  # > 0.1, should pass
                Mode.SAFE: 0.05,  # < 0.1, should fail
            }),
        ),
    }

    # Evaluate the project
    results = evaluate_project(project, model_data)

    # For Table verifications, results should be stored at leaf paths with ItemPart
    nominal_ppath_with_part = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_margins", parts=(ItemPart(key="nominal"),)),
    )
    safe_ppath_with_part = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_margins", parts=(ItemPart(key="safe"),)),
    )

    assert results[nominal_ppath_with_part] is True
    assert results[safe_ppath_with_part] is False


def test_table_verification_with_bool_verification() -> None:
    """Test that both bool and Table[K, bool] verifications work together."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        threshold: float
        margins: vq.Table[Mode, float]

    @scope.verification()
    def verify_threshold(
        threshold: Annotated[float, vq.Ref("$.threshold")],
    ) -> bool:
        return threshold > 0

    @scope.verification()
    def verify_margins(
        margins: Annotated[vq.Table[Mode, float], vq.Ref("$.margins")],
    ) -> vq.Table[Mode, bool]:
        return vq.Table({mode: margins[mode] > 0.1 for mode in Mode})

    # Create model data
    model_data = {
        "TestScope": TestModel(
            threshold=1.0,
            margins=vq.Table({
                Mode.NOMINAL: 0.2,
                Mode.SAFE: 0.05,
            }),
        ),
    }

    # Evaluate the project
    results = evaluate_project(project, model_data)

    # Check bool verification result
    bool_ppath = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_threshold", parts=()),
    )
    assert results[bool_ppath] is True

    # Check Table verification results
    nominal_ppath = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_margins", parts=(ItemPart(key="nominal"),)),
    )
    safe_ppath = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_margins", parts=(ItemPart(key="safe"),)),
    )
    assert results[nominal_ppath] is True
    assert results[safe_ppath] is False


def test_multidim_table_verification() -> None:
    """Test that multi-dimensional Table[tuple[K1, K2], bool] verifications work."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        matrix: vq.Table[tuple[Phase, Mode], float]

    @scope.verification()
    def verify_matrix(
        matrix: Annotated[vq.Table[tuple[Phase, Mode], float], vq.Ref("$.matrix")],
    ) -> vq.Table[tuple[Phase, Mode], bool]:
        return vq.Table({
            (phase, mode): matrix[(phase, mode)] > 0
            for phase in Phase
            for mode in Mode
        })

    # Create model data
    model_data = {
        "TestScope": TestModel(
            matrix=vq.Table({
                (Phase.INITIAL, Mode.NOMINAL): 1.0,
                (Phase.INITIAL, Mode.SAFE): -1.0,
                (Phase.CRUISE, Mode.NOMINAL): 2.0,
                (Phase.CRUISE, Mode.SAFE): 0.5,
            }),
        ),
    }

    # Evaluate the project
    results = evaluate_project(project, model_data)

    # Check Table verification results
    assert results[ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_matrix", parts=(ItemPart(key=("initial", "nominal")),)),
    )] is True
    assert results[ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_matrix", parts=(ItemPart(key=("initial", "safe")),)),
    )] is False
    assert results[ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_matrix", parts=(ItemPart(key=("cruise", "nominal")),)),
    )] is True
    assert results[ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_matrix", parts=(ItemPart(key=("cruise", "safe")),)),
    )] is True


def test_project_output_model_with_table_verification() -> None:
    """Test that the output model correctly handles Table[K, bool] verification types."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    @scope.verification()
    def verify_bool(value: Annotated[float, vq.Ref("$.value")]) -> bool:
        return value > 0

    @scope.verification()
    def verify_table(value: Annotated[float, vq.Ref("$.value")]) -> vq.Table[Mode, bool]:
        return vq.Table({
            Mode.NOMINAL: value > 0,
            Mode.SAFE: value > 10,
        })

    # Generate and validate output model
    output_model = project.output_model()

    # Validate output model with sample data
    output_data = {
        "TestScope": {
            "model": {"value": 5.0},
            "verification": {
                "verify_bool": True,
                "verify_table": {
                    "nominal": True,
                    "safe": False,
                },
            },
        },
    }
    _validated = output_model.model_validate(output_data)


def test_verification_get_type() -> None:
    """Test that Project.get_type() works correctly for Table[K, bool] verifications."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    @scope.verification()
    def verify_bool(value: Annotated[float, vq.Ref("$.value")]) -> bool:
        return value > 0

    @scope.verification()
    def verify_table(value: Annotated[float, vq.Ref("$.value")]) -> vq.Table[Mode, bool]:
        return vq.Table({
            Mode.NOMINAL: value > 0,
            Mode.SAFE: value > 10,
        })

    # Test bool verification type
    bool_ppath = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_bool", parts=()),
    )
    assert project.get_type(bool_ppath) is bool

    # Test Table verification type at root
    table_ppath = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_table", parts=()),
    )
    table_type = project.get_type(table_ppath)
    # Should return the full Table type
    assert get_origin(table_type) is vq.Table
    key_type, value_type = get_args(table_type)
    assert key_type is Mode
    assert value_type is bool

    # Test Table verification type at leaf (with ItemPart)
    leaf_ppath = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_table", parts=(ItemPart(key="nominal"),)),
    )
    assert project.get_type(leaf_ppath) is bool
