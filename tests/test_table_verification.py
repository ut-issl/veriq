"""Tests for Table[K, bool] verification return type.

This module tests the functionality that allows verifications to return
either `bool` (traditional) or `Table[K, bool]` (new feature for Issue #109).

The tests are organized following "Functional Core, Imperative Shell":
- Unit tests for `is_valid_verification_return_type` (pure function, no mocking)
- Integration tests for the full evaluation pipeline (minimal, behavior-focused)
"""

from enum import StrEnum, auto, unique
from typing import Annotated, get_args, get_origin

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._path import ItemPart, ProjectPath, VerificationPath

# =============================================================================
# Test Fixtures: Enum types used across tests
# =============================================================================


@unique
class Mode(StrEnum):
    """Operation mode enum for testing single-key Tables."""

    NOMINAL = auto()
    SAFE = auto()


@unique
class Phase(StrEnum):
    """Mission phase enum for testing multi-dimensional Tables."""

    INITIAL = auto()
    CRUISE = auto()


# =============================================================================
# Unit Tests: Functional Core (is_valid_verification_return_type)
# =============================================================================
# These tests verify the pure function that validates verification return types.
# No mocking is needed because this is a pure function with no side effects.


def test_is_valid_verification_return_type_bool() -> None:
    """bool is a valid verification return type."""
    assert vq.is_valid_verification_return_type(bool) is True


def test_is_valid_verification_return_type_table_bool() -> None:
    """Table[K, bool] is a valid verification return type."""
    assert vq.is_valid_verification_return_type(vq.Table[Mode, bool]) is True


def test_is_valid_verification_return_type_table_multidim_bool() -> None:
    """Table[tuple[K1, K2], bool] is a valid verification return type."""
    assert vq.is_valid_verification_return_type(vq.Table[tuple[Phase, Mode], bool]) is True


def test_is_valid_verification_return_type_int_invalid() -> None:
    """int is not a valid verification return type."""
    assert vq.is_valid_verification_return_type(int) is False


def test_is_valid_verification_return_type_float_invalid() -> None:
    """float is not a valid verification return type."""
    assert vq.is_valid_verification_return_type(float) is False


def test_is_valid_verification_return_type_str_invalid() -> None:
    """str is not a valid verification return type."""
    assert vq.is_valid_verification_return_type(str) is False


def test_is_valid_verification_return_type_table_float_invalid() -> None:
    """Table[K, float] is not a valid verification return type (value must be bool)."""
    assert vq.is_valid_verification_return_type(vq.Table[Mode, float]) is False


def test_is_valid_verification_return_type_table_int_invalid() -> None:
    """Table[K, int] is not a valid verification return type (value must be bool)."""
    assert vq.is_valid_verification_return_type(vq.Table[Mode, int]) is False


def test_is_valid_verification_return_type_table_str_invalid() -> None:
    """Table[K, str] is not a valid verification return type (value must be bool)."""
    assert vq.is_valid_verification_return_type(vq.Table[Mode, str]) is False


def test_is_valid_verification_return_type_table_multidim_float_invalid() -> None:
    """Table[tuple[K1, K2], float] is not valid (value must be bool)."""
    assert vq.is_valid_verification_return_type(vq.Table[tuple[Phase, Mode], float]) is False


# =============================================================================
# Integration Tests: Verification Registration
# =============================================================================
# These tests verify that the decorator correctly accepts/rejects return types.


def test_verification_decorator_accepts_bool_return() -> None:
    """Verification decorator accepts functions returning bool."""
    scope = vq.Scope("TestScope")

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    # Should not raise - bool is valid
    @scope.verification()
    def verify_bool(value: Annotated[float, vq.Ref("$.value")]) -> bool:
        return value > 0

    assert "verify_bool" in scope.verifications
    assert scope.verifications["verify_bool"].output_type is bool


def test_verification_decorator_accepts_table_bool_return() -> None:
    """Verification decorator accepts functions returning Table[K, bool]."""
    scope = vq.Scope("TestScope")

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    # Should not raise - Table[K, bool] is valid
    @scope.verification()
    def verify_table(value: Annotated[float, vq.Ref("$.value")]) -> vq.Table[Mode, bool]:
        return vq.Table({
            Mode.NOMINAL: value > 0,
            Mode.SAFE: value > 10,
        })

    assert "verify_table" in scope.verifications
    # Verify the output_type is the correct generic Table type
    output_type = scope.verifications["verify_table"].output_type
    assert get_origin(output_type) is vq.Table


def test_verification_decorator_rejects_invalid_return_type() -> None:
    """Verification decorator rejects functions with invalid return types."""
    scope = vq.Scope("TestScope")

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    # Should raise TypeError - Table[K, float] is invalid (value not bool)
    with pytest.raises(TypeError, match="Return type must be 'bool' or 'Table\\[K, bool\\]'"):

        @scope.verification()
        def verify_invalid(value: Annotated[float, vq.Ref("$.value")]) -> vq.Table[Mode, float]:  # type: ignore[type-var]
            return vq.Table({
                Mode.NOMINAL: value,
                Mode.SAFE: value * 2,
            })


# =============================================================================
# Integration Tests: Evaluation Pipeline
# =============================================================================
# These tests verify the end-to-end behavior of Table[K, bool] verifications.


def test_table_verification_evaluation_stores_leaf_paths() -> None:
    """Table[K, bool] verification results are stored at leaf paths.

    When a verification returns Table[K, bool], the results should be
    decomposed and stored at individual paths like ?verify[key], not
    as a single Table object.
    """
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

    model_data = {
        "TestScope": TestModel(
            margin=vq.Table({
                Mode.NOMINAL: 0.2,  # > 0.1, should pass
                Mode.SAFE: 0.05,  # < 0.1, should fail
            }),
        ),
    }

    results = evaluate_project(project, model_data)

    # Results should be stored at leaf paths with ItemPart
    nominal_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_margins", parts=(ItemPart(key="nominal"),)),
    )
    safe_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_margins", parts=(ItemPart(key="safe"),)),
    )

    assert results[nominal_path] is True
    assert results[safe_path] is False


def test_bool_and_table_verifications_coexist() -> None:
    """Both bool and Table[K, bool] verifications work in the same scope.

    This tests backward compatibility - existing bool verifications should
    continue to work alongside new Table[K, bool] verifications.
    """
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

    model_data = {
        "TestScope": TestModel(
            threshold=1.0,
            margins=vq.Table({
                Mode.NOMINAL: 0.2,
                Mode.SAFE: 0.05,
            }),
        ),
    }

    results = evaluate_project(project, model_data)

    # Bool verification: stored at path without parts
    bool_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_threshold", parts=()),
    )
    assert results[bool_path] is True

    # Table verification: stored at leaf paths
    nominal_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_margins", parts=(ItemPart(key="nominal"),)),
    )
    safe_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_margins", parts=(ItemPart(key="safe"),)),
    )
    assert results[nominal_path] is True
    assert results[safe_path] is False


def test_multidim_table_verification_evaluation() -> None:
    """Multi-dimensional Table[tuple[K1, K2], bool] verifications work correctly.

    Tables can have composite keys (tuple of enums). The results should be
    stored at paths with tuple keys like ?verify[phase,mode].
    """
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

    model_data = {
        "TestScope": TestModel(
            matrix=vq.Table({
                (Phase.INITIAL, Mode.NOMINAL): 1.0,   # > 0, True
                (Phase.INITIAL, Mode.SAFE): -1.0,    # < 0, False
                (Phase.CRUISE, Mode.NOMINAL): 2.0,   # > 0, True
                (Phase.CRUISE, Mode.SAFE): 0.5,      # > 0, True
            }),
        ),
    }

    results = evaluate_project(project, model_data)

    # Check each combination
    def make_path(phase: str, mode: str) -> ProjectPath:
        return ProjectPath(
            scope="TestScope",
            path=VerificationPath(root="?verify_matrix", parts=(ItemPart(key=(phase, mode)),)),
        )

    assert results[make_path("initial", "nominal")] is True
    assert results[make_path("initial", "safe")] is False
    assert results[make_path("cruise", "nominal")] is True
    assert results[make_path("cruise", "safe")] is True


# =============================================================================
# Integration Tests: Output Model Generation
# =============================================================================


def test_output_model_includes_table_verification_types() -> None:
    """Output model correctly represents Table[K, bool] verification types.

    The generated output model should have the correct type for Table
    verifications, allowing proper validation of output data.
    """
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

    output_model = project.output_model()

    # Validate that the model accepts properly structured data
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
    validated = output_model.model_validate(output_data)
    assert validated is not None


# =============================================================================
# Integration Tests: Type Resolution (Project.get_type)
# =============================================================================


def test_get_type_returns_correct_verification_types() -> None:
    """Project.get_type() returns correct types for verification paths.

    For bool verifications: returns bool
    For Table verifications at root: returns Table[K, bool]
    For Table verifications at leaf: returns bool (the value type)
    """
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

    # Bool verification: type is bool
    bool_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_bool", parts=()),
    )
    assert project.get_type(bool_path) is bool

    # Table verification at root: type is Table[Mode, bool]
    table_root_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_table", parts=()),
    )
    table_type = project.get_type(table_root_path)
    assert get_origin(table_type) is vq.Table
    key_type, value_type = get_args(table_type)
    assert key_type is Mode
    assert value_type is bool

    # Table verification at leaf: type is bool (the value type)
    table_leaf_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?verify_table", parts=(ItemPart(key="nominal"),)),
    )
    assert project.get_type(table_leaf_path) is bool
