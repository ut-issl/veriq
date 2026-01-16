from enum import StrEnum, unique
from typing import Annotated

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._path import CalcPath, ModelPath, ProjectPath, VerificationPath


# Define operation modes
@unique
class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"
    MISSION = "mission"


# Define a component configuration (BaseModel)
class PowerConfig(BaseModel):
    """Power configuration for an operation mode."""

    consumption: float  # in Watts
    max_peak: float  # in Watts
    voltage: float  # in Volts


# Create project and scope
project = vq.Project("SatelliteExample")
power = vq.Scope("Power")
project.add_scope(power)


# Define the root model with a Table of BaseModel values
@power.root_model()
class PowerModel(BaseModel):
    """Power subsystem model."""

    battery_capacity: float  # in Watt-hours
    # Table mapping operation modes to their power configurations
    mode_configs: vq.Table[OperationMode, PowerConfig]


# Add a simple calculation
class PowerResult(BaseModel):
    """Results from power calculations."""

    max_discharge_power: float  # in Watts


@power.calculation()
def calculate_battery_performance(
    battery_capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> PowerResult:
    """Calculate maximum discharge power from battery."""
    max_discharge = battery_capacity * 0.5  # 0.5C discharge rate
    return PowerResult(max_discharge_power=max_discharge)


@power.verification()
def verify_battery_performance(
    battery_performance: Annotated[PowerResult, vq.Ref("@calculate_battery_performance")],
) -> bool:
    return battery_performance.max_discharge_power > 400.0


def test_project_input_model() -> None:
    # Generate project input model
    power_input_model_value = {
        "battery_capacity": 1000.0,
        "mode_configs": {
            "nominal": {
                "consumption": 100.0,
                "max_peak": 200.0,
                "voltage": 12.0,
            },
            "safe": {
                "consumption": 20.0,
                "max_peak": 50.0,
                "voltage": 12.0,
            },
            "mission": {
                "consumption": 150.0,
                "max_peak": 300.0,
                "voltage": 12.0,
            },
        },
    }
    # Check the power_input_model_value is valid
    _power_input_model_instance = PowerModel.model_validate(power_input_model_value)

    project_input_model_value = {
        power.name: {
            "model": power_input_model_value,
        },
    }
    _project_input_model_instance = project.input_model().model_validate(project_input_model_value)


def test_project_output_model() -> None:
    # Generate project input model
    power_input_model_value = {
        "battery_capacity": 1000.0,
        "mode_configs": {
            "nominal": {
                "consumption": 100.0,
                "max_peak": 200.0,
                "voltage": 12.0,
            },
            "safe": {
                "consumption": 20.0,
                "max_peak": 50.0,
                "voltage": 12.0,
            },
            "mission": {
                "consumption": 150.0,
                "max_peak": 300.0,
                "voltage": 12.0,
            },
        },
    }
    # Check the power_input_model_value is valid
    _power_input_model_instance = PowerModel.model_validate(power_input_model_value)

    power_calc_model_value = {
        "calculate_battery_performance": {
            "max_discharge_power": 500.0,
        },
    }
    power_verification_model_value = {
        "verify_battery_performance": True,
    }

    project_output_model_value = {
        power.name: {
            "model": power_input_model_value,
            "calc": power_calc_model_value,
            "verification": power_verification_model_value,
        },
    }
    _project_output_model_instance = project.output_model().model_validate(project_output_model_value)


# --- Project.get_type() Tests ---


class TestProjectGetType:
    def test_get_type_model_path_simple(self):
        """Test getting type for a simple model field path."""
        ppath = ProjectPath(scope="Power", path=ModelPath.parse("$.battery_capacity"))
        result = project.get_type(ppath)
        assert result is float

    def test_get_type_model_path_nested(self):
        """Test getting type for a nested model field path."""
        ppath = ProjectPath(
            scope="Power", path=ModelPath.parse("$.mode_configs[nominal].consumption")
        )
        result = project.get_type(ppath)
        assert result is float

    def test_get_type_model_path_table(self):
        """Test getting type for a Table field."""
        ppath = ProjectPath(scope="Power", path=ModelPath.parse("$.mode_configs"))
        result = project.get_type(ppath)
        # Should be the Table type (generic alias)
        assert hasattr(result, "__origin__") or result is vq.Table

    def test_get_type_model_path_table_item(self):
        """Test getting type for a Table item."""
        ppath = ProjectPath(
            scope="Power", path=ModelPath.parse("$.mode_configs[nominal]")
        )
        result = project.get_type(ppath)
        assert result is PowerConfig

    def test_get_type_calc_path(self):
        """Test getting type for a calculation output."""
        ppath = ProjectPath(
            scope="Power", path=CalcPath.parse("@calculate_battery_performance")
        )
        result = project.get_type(ppath)
        assert result is PowerResult

    def test_get_type_calc_path_nested(self):
        """Test getting type for a nested calculation output field."""
        ppath = ProjectPath(
            scope="Power",
            path=CalcPath.parse("@calculate_battery_performance.max_discharge_power"),
        )
        result = project.get_type(ppath)
        assert result is float

    def test_get_type_verification_path(self):
        """Test getting type for a verification result."""
        ppath = ProjectPath(
            scope="Power", path=VerificationPath.parse("?verify_battery_performance")
        )
        result = project.get_type(ppath)
        assert result is bool

    def test_get_type_missing_scope_raises(self):
        """Test that missing scope raises KeyError."""
        ppath = ProjectPath(
            scope="NonexistentScope", path=ModelPath.parse("$.field")
        )
        with pytest.raises(KeyError, match="Scope 'NonexistentScope' not found"):
            project.get_type(ppath)

    def test_get_type_missing_calculation_raises(self):
        """Test that missing calculation raises KeyError."""
        ppath = ProjectPath(
            scope="Power", path=CalcPath.parse("@nonexistent_calc")
        )
        with pytest.raises(KeyError, match="Calculation 'nonexistent_calc' not found"):
            project.get_type(ppath)

    def test_get_type_missing_verification_raises(self):
        """Test that missing verification raises KeyError."""
        ppath = ProjectPath(
            scope="Power", path=VerificationPath.parse("?nonexistent_verif")
        )
        with pytest.raises(KeyError, match="Verification 'nonexistent_verif' not found"):
            project.get_type(ppath)


# --- Calculation/Verification Validation Tests ---


class TestCalculationValidation:
    def test_calculation_cross_scope_without_import_raises(self):
        """Test that cross-scope reference without import raises ValueError."""
        test_project = vq.Project("TestProject")
        scope_a = vq.Scope("ScopeA")
        scope_b = vq.Scope("ScopeB")
        test_project.add_scope(scope_a)
        test_project.add_scope(scope_b)

        @scope_a.root_model()
        class ModelA(BaseModel):
            value: float

        @scope_b.root_model()
        class ModelB(BaseModel):
            other: float

        # This should raise because ScopeA is not imported
        with pytest.raises(ValueError, match="not imported"):

            @scope_b.calculation()
            def bad_calc(
                val: Annotated[float, vq.Ref("$.value", scope="ScopeA")],
            ) -> float:
                return val * 2

    def test_calculation_cross_scope_with_import_succeeds(self):
        """Test that cross-scope reference with import succeeds."""
        test_project = vq.Project("TestProject")
        scope_a = vq.Scope("ScopeA")
        scope_b = vq.Scope("ScopeB")
        test_project.add_scope(scope_a)
        test_project.add_scope(scope_b)

        @scope_a.root_model()
        class ModelA(BaseModel):
            value: float

        @scope_b.root_model()
        class ModelB(BaseModel):
            other: float

        # This should succeed because ScopeA is imported
        @scope_b.calculation(imports=["ScopeA"])
        def good_calc(
            val: Annotated[float, vq.Ref("$.value", scope="ScopeA")],
        ) -> float:
            return val * 2

        assert good_calc.name == "good_calc"


class TestVerificationValidation:
    def test_verification_invalid_return_type_raises(self):
        """Test that verification with non-bool return type raises TypeError."""
        test_scope = vq.Scope("TestScope")

        @test_scope.root_model()
        class TestModel(BaseModel):
            value: float

        with pytest.raises(TypeError, match="invalid return type"):

            @test_scope.verification()
            def bad_verif(
                val: Annotated[float, vq.Ref("$.value")],
            ) -> float:  # Invalid - should be bool
                return val

    def test_verification_cross_scope_without_import_raises(self):
        """Test that cross-scope reference without import raises ValueError."""
        test_project = vq.Project("TestProject")
        scope_a = vq.Scope("ScopeA")
        scope_b = vq.Scope("ScopeB")
        test_project.add_scope(scope_a)
        test_project.add_scope(scope_b)

        @scope_a.root_model()
        class ModelA(BaseModel):
            value: float

        @scope_b.root_model()
        class ModelB(BaseModel):
            other: float

        with pytest.raises(ValueError, match="not imported"):

            @scope_b.verification()
            def bad_verif(
                val: Annotated[float, vq.Ref("$.value", scope="ScopeA")],
            ) -> bool:
                return val > 0


# --- Requirement Tests ---


class TestRequirement:
    def test_requirement_iter_all(self):
        """Test iterating over all requirements."""
        test_scope = vq.Scope("TestScope")
        req1 = test_scope.requirement("REQ-1", description="Top requirement")
        with req1:
            req1_1 = test_scope.requirement("REQ-1.1", description="Sub requirement 1")
            req1_2 = test_scope.requirement("REQ-1.2", description="Sub requirement 2")
            with req1_2:
                req1_2_1 = test_scope.requirement(
                    "REQ-1.2.1", description="Sub-sub requirement"
                )

        all_reqs = list(req1.iter_requirements())
        assert len(all_reqs) == 4
        assert req1 in all_reqs
        assert req1_1 in all_reqs
        assert req1_2 in all_reqs
        assert req1_2_1 in all_reqs

    def test_requirement_iter_leaf_only(self):
        """Test iterating over leaf requirements only."""
        test_scope = vq.Scope("TestScope")
        req1 = test_scope.requirement("REQ-1", description="Top requirement")
        with req1:
            req1_1 = test_scope.requirement("REQ-1.1", description="Leaf 1")
            req1_2 = test_scope.requirement("REQ-1.2", description="Parent")
            with req1_2:
                req1_2_1 = test_scope.requirement("REQ-1.2.1", description="Leaf 2")

        leaf_reqs = list(req1.iter_requirements(leaf_only=True))
        assert len(leaf_reqs) == 2
        assert req1_1 in leaf_reqs
        assert req1_2_1 in leaf_reqs
        assert req1 not in leaf_reqs
        assert req1_2 not in leaf_reqs

    def test_requirement_iter_with_depth(self):
        """Test iterating with depth limit."""
        test_scope = vq.Scope("TestScope")
        req1 = test_scope.requirement("REQ-1", description="Level 0")
        with req1:
            req1_1 = test_scope.requirement("REQ-1.1", description="Level 1")
            with req1_1:
                req1_1_1 = test_scope.requirement("REQ-1.1.1", description="Level 2")

        # Depth 1 should include req1 and req1_1 but not req1_1_1
        reqs_depth_1 = list(req1.iter_requirements(depth=1))
        assert req1 in reqs_depth_1
        assert req1_1 in reqs_depth_1
        assert req1_1_1 not in reqs_depth_1

    def test_fetch_requirement(self):
        """Test fetching a requirement by ID."""
        test_scope = vq.Scope("TestScope")
        req = test_scope.requirement("REQ-FETCH", description="Test fetch")

        fetched = test_scope.fetch_requirement("REQ-FETCH")
        assert fetched is req

    def test_fetch_requirement_not_found_raises(self):
        """Test that fetching nonexistent requirement raises KeyError."""
        test_scope = vq.Scope("TestScope")

        with pytest.raises(KeyError, match="not found"):
            test_scope.fetch_requirement("NONEXISTENT")


# --- Scope Tests ---


class TestScope:
    def test_scope_duplicate_calculation_raises(self):
        """Test that duplicate calculation name raises KeyError."""
        test_scope = vq.Scope("TestScope")

        @test_scope.root_model()
        class TestModel(BaseModel):
            value: float

        @test_scope.calculation()
        def my_calc(val: Annotated[float, vq.Ref("$.value")]) -> float:
            return val

        with pytest.raises(KeyError, match="already exists"):

            @test_scope.calculation()
            def my_calc(val: Annotated[float, vq.Ref("$.value")]) -> float:  # noqa: F811
                return val * 2

    def test_scope_duplicate_verification_raises(self):
        """Test that duplicate verification name raises KeyError."""
        test_scope = vq.Scope("TestScope")

        @test_scope.root_model()
        class TestModel(BaseModel):
            value: float

        @test_scope.verification()
        def my_verif(val: Annotated[float, vq.Ref("$.value")]) -> bool:
            return val > 0

        with pytest.raises(KeyError, match="already exists"):

            @test_scope.verification()
            def my_verif(val: Annotated[float, vq.Ref("$.value")]) -> bool:  # noqa: F811
                return val < 100

    def test_scope_duplicate_requirement_raises(self):
        """Test that duplicate requirement ID raises KeyError."""
        test_scope = vq.Scope("TestScope")
        test_scope.requirement("REQ-1", description="First")

        with pytest.raises(KeyError, match="already exists"):
            test_scope.requirement("REQ-1", description="Duplicate")

    def test_scope_get_root_model_not_defined_raises(self):
        """Test that getting root model before it's defined raises RuntimeError."""
        test_scope = vq.Scope("EmptyScope")

        with pytest.raises(RuntimeError, match="does not have a root model"):
            test_scope.get_root_model()

    def test_scope_duplicate_root_model_raises(self):
        """Test that defining root model twice raises RuntimeError."""
        test_scope = vq.Scope("TestScope")

        @test_scope.root_model()
        class Model1(BaseModel):
            value: float

        with pytest.raises(RuntimeError, match="already has a root model"):

            @test_scope.root_model()
            class Model2(BaseModel):
                other: float


# --- Project Tests ---


class TestProject:
    def test_project_duplicate_scope_raises(self):
        """Test that adding duplicate scope raises KeyError."""
        test_project = vq.Project("TestProject")
        scope1 = vq.Scope("MyScope")
        test_project.add_scope(scope1)

        scope2 = vq.Scope("MyScope")  # Same name
        with pytest.raises(KeyError, match="already exists"):
            test_project.add_scope(scope2)
