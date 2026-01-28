"""Tests for the vq.assume feature - validity tracking based on assumed verifications."""

from typing import Annotated

from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._path import CalcPath, ProjectPath, VerificationPath


def test_assume_valid_when_verification_passes() -> None:
    """Test that calculations are valid when assumed verification passes."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    @scope.verification()
    def value_positive(val: Annotated[float, vq.Ref("$.value")]) -> bool:
        return val > 0

    @scope.calculation()
    @vq.assume(vq.Ref("?value_positive"))
    def doubled_value(val: Annotated[float, vq.Ref("$.value")]) -> float:
        return val * 2

    model_data = {"TestScope": TestModel(value=10.0)}
    result = evaluate_project(project, model_data)

    # Verification should pass
    verif_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?value_positive", parts=()),
    )
    assert result.get_value(verif_path) is True
    assert result.is_valid(verif_path)

    # Calculation should be valid since assumption holds
    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@doubled_value", parts=()),
    )
    assert result.get_value(calc_path) == 20.0
    assert result.is_valid(calc_path)


def test_assume_invalid_when_verification_fails() -> None:
    """Test that calculations are invalid when assumed verification fails."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    @scope.verification()
    def value_positive(val: Annotated[float, vq.Ref("$.value")]) -> bool:
        return val > 0

    @scope.calculation()
    @vq.assume(vq.Ref("?value_positive"))
    def doubled_value(val: Annotated[float, vq.Ref("$.value")]) -> float:
        return val * 2

    model_data = {"TestScope": TestModel(value=-5.0)}
    result = evaluate_project(project, model_data)

    # Verification should fail
    verif_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?value_positive", parts=()),
    )
    assert result.get_value(verif_path) is False
    assert result.is_valid(verif_path)  # Verification itself is valid (it ran)

    # Calculation should be invalid since assumption doesn't hold
    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@doubled_value", parts=()),
    )
    # The calculated value is still computed
    assert result.get_value(calc_path) == -10.0
    # But it's marked as invalid
    assert not result.is_valid(calc_path)


def test_assume_transitive_invalidity() -> None:
    """Test that invalidity propagates transitively through dependencies."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    @scope.verification()
    def value_positive(val: Annotated[float, vq.Ref("$.value")]) -> bool:
        return val > 0

    @scope.calculation()
    @vq.assume(vq.Ref("?value_positive"))
    def doubled_value(val: Annotated[float, vq.Ref("$.value")]) -> float:
        return val * 2

    @scope.calculation()
    def tripled_doubled(doubled: Annotated[float, vq.Ref("@doubled_value")]) -> float:
        return doubled * 3

    model_data = {"TestScope": TestModel(value=-5.0)}
    result = evaluate_project(project, model_data)

    # doubled_value is invalid (assumed verification failed)
    doubled_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@doubled_value", parts=()),
    )
    assert not result.is_valid(doubled_path)

    # tripled_doubled depends on invalid doubled_value, so it's also invalid
    tripled_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@tripled_doubled", parts=()),
    )
    assert not result.is_valid(tripled_path)


def test_assume_multiple_verifications_all_must_pass() -> None:
    """Test that multiple assumptions must all hold for validity."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    @scope.verification()
    def value_positive(val: Annotated[float, vq.Ref("$.value")]) -> bool:
        return val > 0

    @scope.verification()
    def value_small(val: Annotated[float, vq.Ref("$.value")]) -> bool:
        return val < 100

    @scope.calculation()
    @vq.assume(vq.Ref("?value_positive"))
    @vq.assume(vq.Ref("?value_small"))
    def doubled_value(val: Annotated[float, vq.Ref("$.value")]) -> float:
        return val * 2

    # Value is positive but not small - one assumption fails
    model_data = {"TestScope": TestModel(value=150.0)}
    result = evaluate_project(project, model_data)

    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@doubled_value", parts=()),
    )
    # Calculation is invalid because one assumption failed
    assert not result.is_valid(calc_path)


def test_assume_cross_scope() -> None:
    """Test that cross-scope assumptions work correctly."""
    project = vq.Project("TestProject")
    power = vq.Scope("Power")
    thermal = vq.Scope("Thermal")
    project.add_scope(power)
    project.add_scope(thermal)

    @power.root_model()
    class PowerModel(BaseModel):
        temperature: float

    @thermal.root_model()
    class ThermalModel(BaseModel):
        max_temp: float

    @thermal.verification(imports=["Power"])
    def temp_in_range(
        temp: Annotated[float, vq.Ref("$.temperature", scope="Power")],
        max_temp: Annotated[float, vq.Ref("$.max_temp")],
    ) -> bool:
        return temp < max_temp

    @power.calculation()
    @vq.assume(vq.Ref("?temp_in_range", scope="Thermal"))
    def power_output(temp: Annotated[float, vq.Ref("$.temperature")]) -> float:
        return 100.0 - temp

    # Temperature exceeds max - verification fails
    model_data = {
        "Power": PowerModel(temperature=90.0),
        "Thermal": ThermalModel(max_temp=80.0),
    }
    result = evaluate_project(project, model_data)

    # Verification should fail
    verif_path = ProjectPath(
        scope="Thermal",
        path=VerificationPath(root="?temp_in_range", parts=()),
    )
    assert result.get_value(verif_path) is False

    # Calculation should be invalid
    calc_path = ProjectPath(
        scope="Power",
        path=CalcPath(root="@power_output", parts=()),
    )
    assert not result.is_valid(calc_path)


def test_assume_invalid_verification_overrides_to_false() -> None:
    """Test that invalid verifications are overridden to False in values."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float

    @scope.verification()
    def base_assumption(val: Annotated[float, vq.Ref("$.value")]) -> bool:
        return val > 0

    @scope.verification()
    @vq.assume(vq.Ref("?base_assumption"))
    def dependent_verification(val: Annotated[float, vq.Ref("$.value")]) -> bool:
        # This would return True for value=10, but it's based on invalid assumption
        return val < 100

    # base_assumption fails, so dependent_verification is invalid
    model_data = {"TestScope": TestModel(value=-5.0)}
    result = evaluate_project(project, model_data)

    # dependent_verification returns True, but since it's invalid, output should be False
    dep_verif_path = ProjectPath(
        scope="TestScope",
        path=VerificationPath(root="?dependent_verification", parts=()),
    )
    # The value should be overridden to False because it's invalid
    assert result.get_value(dep_verif_path) is False
    assert not result.is_valid(dep_verif_path)


def test_assume_table_verification_all_entries_must_pass() -> None:
    """Test that Table[K, bool] verifications require all entries to be True."""
    from enum import StrEnum, unique

    @unique
    class Mode(StrEnum):
        NOMINAL = "nominal"
        SAFE = "safe"

    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        values: vq.Table[Mode, float]

    @scope.verification()
    def all_positive(values: Annotated[vq.Table[Mode, float], vq.Ref("$.values")]) -> vq.Table[Mode, bool]:
        return vq.Table({mode: values[mode] > 0 for mode in Mode})  # ty: ignore[invalid-return-type]

    @scope.calculation()
    @vq.assume(vq.Ref("?all_positive"))
    def sum_values(values: Annotated[vq.Table[Mode, float], vq.Ref("$.values")]) -> float:
        return sum(values[mode] for mode in Mode)

    # One value is negative - not all verifications pass
    model_data = {
        "TestScope": TestModel(
            values=vq.Table({Mode.NOMINAL: 10.0, Mode.SAFE: -5.0}),  # ty: ignore[invalid-argument-type]
        ),
    }
    result = evaluate_project(project, model_data)

    # Calculation should be invalid because not all verification entries passed
    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@sum_values", parts=()),
    )
    assert not result.is_valid(calc_path)
