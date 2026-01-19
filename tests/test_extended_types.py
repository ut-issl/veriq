"""Tests for extended input model types.

Phase 1: Test that StrEnum, IntEnum, datetime, and Optional fields work correctly.
These types should already be supported by the existing implementation.
"""

from datetime import UTC, date, datetime, time
from enum import IntEnum, StrEnum, unique
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from pathlib import Path

from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._io import load_model_data_from_toml
from veriq._path import AttributePart, CalcPath, ModelPath, ProjectPath

# =============================================================================
# Test Fixtures - Enum Types
# =============================================================================


@unique
class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"
    EMERGENCY = "emergency"


@unique
class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


# =============================================================================
# Tests for StrEnum Fields
# =============================================================================


def test_strenum_field_in_model() -> None:
    """Test that StrEnum can be used as a model field."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        mode: OperationMode
        value: float

    model_data = {"TestScope": TestModel(mode=OperationMode.NOMINAL, value=1.0)}
    result = evaluate_project(project, model_data)

    # Check that the mode value is stored correctly
    mode_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("mode"),)),
    )
    assert result.values[mode_path] == OperationMode.NOMINAL


def test_strenum_field_in_calculation() -> None:
    """Test that StrEnum can be referenced in calculations."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        mode: OperationMode
        base_power: float

    @scope.calculation()
    def adjusted_power(
        mode: Annotated[OperationMode, vq.Ref("$.mode")],
        base_power: Annotated[float, vq.Ref("$.base_power")],
    ) -> float:
        multipliers = {
            OperationMode.NOMINAL: 1.0,
            OperationMode.SAFE: 0.5,
            OperationMode.EMERGENCY: 2.0,
        }
        return base_power * multipliers[mode]

    model_data = {"TestScope": TestModel(mode=OperationMode.SAFE, base_power=100.0)}
    result = evaluate_project(project, model_data)

    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@adjusted_power", parts=()),
    )
    assert result.values[calc_path] == 50.0


def test_strenum_field_toml_roundtrip(tmp_path: Path) -> None:
    """Test that StrEnum fields can be loaded from TOML."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        mode: OperationMode
        value: float

    toml_content = """
[TestScope.model]
mode = "safe"
value = 42.0
"""
    toml_file = tmp_path / "input.toml"
    toml_file.write_text(toml_content)

    model_data = load_model_data_from_toml(project, toml_file)

    assert "TestScope" in model_data
    assert model_data["TestScope"].mode == OperationMode.SAFE  # ty: ignore[unresolved-attribute]
    assert model_data["TestScope"].value == 42.0  # ty: ignore[unresolved-attribute]


# =============================================================================
# Tests for IntEnum Fields
# =============================================================================


def test_intenum_field_in_model() -> None:
    """Test that IntEnum can be used as a model field."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        priority: Priority
        value: float

    model_data = {"TestScope": TestModel(priority=Priority.HIGH, value=1.0)}
    result = evaluate_project(project, model_data)

    priority_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("priority"),)),
    )
    assert result.values[priority_path] == Priority.HIGH


def test_intenum_field_in_calculation() -> None:
    """Test that IntEnum can be referenced in calculations."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        priority: Priority
        base_value: float

    @scope.calculation()
    def priority_weighted(
        priority: Annotated[Priority, vq.Ref("$.priority")],
        base_value: Annotated[float, vq.Ref("$.base_value")],
    ) -> float:
        # Use the int value of priority as a multiplier
        return base_value * priority.value

    model_data = {"TestScope": TestModel(priority=Priority.MEDIUM, base_value=10.0)}
    result = evaluate_project(project, model_data)

    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@priority_weighted", parts=()),
    )
    assert result.values[calc_path] == 20.0  # 10.0 * 2


def test_intenum_field_toml_roundtrip(tmp_path: Path) -> None:
    """Test that IntEnum fields can be loaded from TOML."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        priority: Priority
        value: float

    toml_content = """
[TestScope.model]
priority = 3
value = 42.0
"""
    toml_file = tmp_path / "input.toml"
    toml_file.write_text(toml_content)

    model_data = load_model_data_from_toml(project, toml_file)

    assert "TestScope" in model_data
    assert model_data["TestScope"].priority == Priority.HIGH  # ty: ignore[unresolved-attribute]
    assert model_data["TestScope"].value == 42.0  # ty: ignore[unresolved-attribute]


# =============================================================================
# Tests for datetime/date/time Fields
# =============================================================================


def test_datetime_field_in_model() -> None:
    """Test that datetime can be used as a model field."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        timestamp: datetime
        value: float

    test_time = datetime(2025, 6, 15, 12, 30, 45, tzinfo=UTC)
    model_data = {"TestScope": TestModel(timestamp=test_time, value=1.0)}
    result = evaluate_project(project, model_data)

    timestamp_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("timestamp"),)),
    )
    assert result.values[timestamp_path] == test_time


def test_date_field_in_model() -> None:
    """Test that date can be used as a model field."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        launch_date: date
        value: float

    test_date = date(2025, 12, 25)
    model_data = {"TestScope": TestModel(launch_date=test_date, value=1.0)}
    result = evaluate_project(project, model_data)

    date_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("launch_date"),)),
    )
    assert result.values[date_path] == test_date


def test_time_field_in_model() -> None:
    """Test that time can be used as a model field."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        event_time: time
        value: float

    test_time = time(14, 30, 0)
    model_data = {"TestScope": TestModel(event_time=test_time, value=1.0)}
    result = evaluate_project(project, model_data)

    time_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("event_time"),)),
    )
    assert result.values[time_path] == test_time


def test_datetime_field_in_calculation() -> None:
    """Test that datetime can be referenced in calculations."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        start_time: datetime
        end_time: datetime

    @scope.calculation()
    def duration_hours(
        start_time: Annotated[datetime, vq.Ref("$.start_time")],
        end_time: Annotated[datetime, vq.Ref("$.end_time")],
    ) -> float:
        delta = end_time - start_time
        return delta.total_seconds() / 3600

    model_data = {
        "TestScope": TestModel(
            start_time=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
            end_time=datetime(2025, 1, 1, 12, 30, 0, tzinfo=UTC),
        ),
    }
    result = evaluate_project(project, model_data)

    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@duration_hours", parts=()),
    )
    assert result.values[calc_path] == 2.5


def test_datetime_field_toml_roundtrip(tmp_path: Path) -> None:
    """Test that datetime fields can be loaded from TOML."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        timestamp: datetime
        value: float

    # TOML natively supports datetime with timezone
    toml_content = """
[TestScope.model]
timestamp = 2025-06-15T12:30:45Z
value = 42.0
"""
    toml_file = tmp_path / "input.toml"
    toml_file.write_text(toml_content)

    model_data = load_model_data_from_toml(project, toml_file)

    assert "TestScope" in model_data
    assert model_data["TestScope"].timestamp == datetime(2025, 6, 15, 12, 30, 45, tzinfo=UTC)  # ty: ignore[unresolved-attribute]
    assert model_data["TestScope"].value == 42.0  # ty: ignore[unresolved-attribute]


def test_date_field_toml_roundtrip(tmp_path: Path) -> None:
    """Test that date fields can be loaded from TOML."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        launch_date: date
        value: float

    toml_content = """
[TestScope.model]
launch_date = 2025-12-25
value = 42.0
"""
    toml_file = tmp_path / "input.toml"
    toml_file.write_text(toml_content)

    model_data = load_model_data_from_toml(project, toml_file)

    assert "TestScope" in model_data
    assert model_data["TestScope"].launch_date == date(2025, 12, 25)  # ty: ignore[unresolved-attribute]
    assert model_data["TestScope"].value == 42.0  # ty: ignore[unresolved-attribute]


def test_time_field_toml_roundtrip(tmp_path: Path) -> None:
    """Test that time fields can be loaded from TOML."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        event_time: time
        value: float

    toml_content = """
[TestScope.model]
event_time = 14:30:00
value = 42.0
"""
    toml_file = tmp_path / "input.toml"
    toml_file.write_text(toml_content)

    model_data = load_model_data_from_toml(project, toml_file)

    assert "TestScope" in model_data
    assert model_data["TestScope"].event_time == time(14, 30, 0)  # ty: ignore[unresolved-attribute]
    assert model_data["TestScope"].value == 42.0  # ty: ignore[unresolved-attribute]


# =============================================================================
# Tests for Optional Fields
# =============================================================================


def test_optional_field_with_value() -> None:
    """Test that Optional fields work when a value is provided."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        required_value: float
        optional_value: float | None = None

    model_data = {"TestScope": TestModel(required_value=1.0, optional_value=2.0)}
    result = evaluate_project(project, model_data)

    optional_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("optional_value"),)),
    )
    assert result.values[optional_path] == 2.0


def test_optional_field_with_none() -> None:
    """Test that Optional fields work when value is None."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        required_value: float
        optional_value: float | None = None

    model_data = {"TestScope": TestModel(required_value=1.0, optional_value=None)}
    result = evaluate_project(project, model_data)

    optional_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("optional_value"),)),
    )
    assert result.values[optional_path] is None


def test_optional_field_in_calculation() -> None:
    """Test that Optional fields can be referenced in calculations."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        base_value: float
        multiplier: float | None = None

    @scope.calculation()
    def computed_value(
        base_value: Annotated[float, vq.Ref("$.base_value")],
        multiplier: Annotated[float | None, vq.Ref("$.multiplier")],
    ) -> float:
        if multiplier is None:
            return base_value
        return base_value * multiplier

    # Test with None
    model_data = {"TestScope": TestModel(base_value=10.0, multiplier=None)}
    result = evaluate_project(project, model_data)

    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@computed_value", parts=()),
    )
    assert result.values[calc_path] == 10.0

    # Test with value
    model_data = {"TestScope": TestModel(base_value=10.0, multiplier=3.0)}
    result = evaluate_project(project, model_data)
    assert result.values[calc_path] == 30.0


def test_optional_field_toml_with_value(tmp_path: Path) -> None:
    """Test that Optional fields can be loaded from TOML with a value."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        required_value: float
        optional_value: float | None = None

    toml_content = """
[TestScope.model]
required_value = 1.0
optional_value = 2.0
"""
    toml_file = tmp_path / "input.toml"
    toml_file.write_text(toml_content)

    model_data = load_model_data_from_toml(project, toml_file)

    assert "TestScope" in model_data
    assert model_data["TestScope"].required_value == 1.0  # ty: ignore[unresolved-attribute]
    assert model_data["TestScope"].optional_value == 2.0  # ty: ignore[unresolved-attribute]


def test_optional_field_toml_omitted(tmp_path: Path) -> None:
    """Test that Optional fields use default when omitted from TOML."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        required_value: float
        optional_value: float | None = None

    toml_content = """
[TestScope.model]
required_value = 1.0
"""
    toml_file = tmp_path / "input.toml"
    toml_file.write_text(toml_content)

    model_data = load_model_data_from_toml(project, toml_file)

    assert "TestScope" in model_data
    assert model_data["TestScope"].required_value == 1.0  # ty: ignore[unresolved-attribute]
    assert model_data["TestScope"].optional_value is None  # ty: ignore[unresolved-attribute]


def test_optional_field_with_non_none_default() -> None:
    """Test Optional field with a non-None default value."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        value: float
        threshold: float | None = 100.0  # Default is not None

    model_data = {"TestScope": TestModel(value=1.0)}
    result = evaluate_project(project, model_data)

    threshold_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("threshold"),)),
    )
    assert result.values[threshold_path] == 100.0


# =============================================================================
# Tests for Combined Types
# =============================================================================


def test_combined_extended_types() -> None:
    """Test a model using multiple extended types together."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class MissionConfig(BaseModel):
        mode: OperationMode
        priority: Priority
        start_time: datetime
        end_time: datetime | None = None
        backup_power: float | None = None

    @scope.calculation()
    def mission_duration(
        start_time: Annotated[datetime, vq.Ref("$.start_time")],
        end_time: Annotated[datetime | None, vq.Ref("$.end_time")],
    ) -> float:
        if end_time is None:
            return 0.0
        return (end_time - start_time).total_seconds() / 3600

    model_data = {
        "TestScope": MissionConfig(
            mode=OperationMode.NOMINAL,
            priority=Priority.HIGH,
            start_time=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
            end_time=datetime(2025, 1, 1, 6, 0, 0, tzinfo=UTC),
            backup_power=None,
        ),
    }
    result = evaluate_project(project, model_data)

    # Check enum values
    mode_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("mode"),)),
    )
    assert result.values[mode_path] == OperationMode.NOMINAL

    priority_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("priority"),)),
    )
    assert result.values[priority_path] == Priority.HIGH

    # Check calculation
    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@mission_duration", parts=()),
    )
    assert result.values[calc_path] == 6.0
