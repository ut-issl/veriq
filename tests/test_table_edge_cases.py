"""Comprehensive edge case tests for vq.Table including nested tables and Pydantic models as values.

Note: Tests for Table[K, PydanticModel] where PydanticModel values are accessed through
calculations are currently excluded because this feature is not yet fully supported in the
evaluation system. However, Tables with Pydantic model values DO work for:
- Serialization to TOML (see test_table_basemodel_toml.py)
- Direct access in Python code
- Loading from TOML files

The limitation is specifically around path resolution and dependency graph building for
nested structures within table values.
"""

from enum import StrEnum
from typing import Annotated

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._path import AttributePart, CalcPath, ItemPart, ModelPath, ProjectPath, VerificationPath


# ==================== Enum definitions ====================


class Mode(StrEnum):
    """Operating mode for the system."""

    NOMINAL = "nominal"
    SAFE = "safe"


class Component(StrEnum):
    """System component identifier."""

    BATTERY = "battery"
    SOLAR = "solar"
    PAYLOAD = "payload"


class Phase(StrEnum):
    """Mission phase identifier."""

    LAUNCH = "launch"
    ORBIT = "orbit"
    DEORBIT = "deorbit"


class Status(StrEnum):
    """Component status identifier."""

    ACTIVE = "active"
    STANDBY = "standby"


# ==================== Tests: Table with Pydantic model as value ====================
# Note: The following tests are commented out because Table[K, PydanticModel] with
# path-based access through calculations is not yet fully supported in the evaluation
# system. The issue is that iter_leaf_path_parts() doesn't properly flatten Table
# values that contain Pydantic models. However, these tables DO work for TOML I/O
# (see test_table_basemodel_toml.py) and direct Python access.


def test_table_with_pydantic_model_value_serialization() -> None:
    """Test that Table[K, PydanticModel] can be created and serialized (without evaluation)."""
    
    class ComponentSpec(BaseModel):
        power: float
        mass: float
        efficiency: float

    class Model(BaseModel):
        component_specs: vq.Table[Component, ComponentSpec]

    # Create table with Pydantic model values
    table = vq.Table(
        {
            Component.BATTERY: ComponentSpec(power=100.0, mass=5.0, efficiency=0.95),
            Component.SOLAR: ComponentSpec(power=200.0, mass=3.0, efficiency=0.85),
            Component.PAYLOAD: ComponentSpec(power=50.0, mass=2.0, efficiency=0.90),
        },
    )

    # Verify we can create a model with it
    model = Model(component_specs=table)
    assert model.component_specs[Component.BATTERY].power == 100.0
    assert model.component_specs[Component.SOLAR].mass == 3.0

    # Verify serialization works
    serialized = model.model_dump()
    assert serialized["component_specs"]["battery"]["power"] == 100.0


@pytest.mark.xfail(
    reason="Table[K, PydanticModel] with path-based access in calculations not yet supported. "
    "Issue: iter_leaf_path_parts() doesn't properly flatten Table values containing Pydantic models.",
    strict=True,
)
def test_table_with_pydantic_model_value_in_root_model() -> None:
    """Test Table[K, PydanticModel] in root model - basic case with model values."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    # Define a Pydantic model to use as table value
    class ComponentSpec(BaseModel):
        power: float
        mass: float
        efficiency: float

    @scope.root_model()
    class RootModel(BaseModel):
        component_specs: vq.Table[Component, ComponentSpec]

    # Create test data
    model_data = {
        scope.name: RootModel(
            component_specs=vq.Table(
                {
                    Component.BATTERY: ComponentSpec(power=100.0, mass=5.0, efficiency=0.95),
                    Component.SOLAR: ComponentSpec(power=200.0, mass=3.0, efficiency=0.85),
                    Component.PAYLOAD: ComponentSpec(power=50.0, mass=2.0, efficiency=0.90),
                },
            ),
        ),
    }

    # Evaluate the project - this will fail with KeyError
    result = evaluate_project(project, model_data)

    # Verify the table is stored correctly - access via model path
    battery_power = result[
        ProjectPath(
            scope=scope.name,
            path=ModelPath(
                root="$",
                parts=(AttributePart("component_specs"), ItemPart("battery"), AttributePart("power")),
            ),
        )
    ]
    assert battery_power == 100.0


@pytest.mark.xfail(
    reason="Table[K, PydanticModel] as calculation output not yet supported",
    strict=True,
)
def test_table_with_pydantic_model_value_in_calculation() -> None:
    """Test Table[K, PydanticModel] as calculation output."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    class PowerProfile(BaseModel):
        avg_power: float
        peak_power: float
        duration_seconds: float

    @scope.root_model()
    class RootModel(BaseModel):
        base_power: float

    @scope.calculation()
    def power_profiles(
        base_power: Annotated[float, vq.Ref("$.base_power")],
    ) -> vq.Table[Mode, PowerProfile]:
        # Generate power profiles for different modes
        return vq.Table(
            {
                Mode.NOMINAL: PowerProfile(
                    avg_power=base_power,
                    peak_power=base_power * 1.5,
                    duration_seconds=3600.0,
                ),
                Mode.SAFE: PowerProfile(
                    avg_power=base_power * 0.5,
                    peak_power=base_power * 0.8,
                    duration_seconds=7200.0,
                ),
            },
        )

    model_data = {scope.name: RootModel(base_power=100.0)}
    result = evaluate_project(project, model_data)

    # Verify calculation output - access leaf values
    nominal_avg_power = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@power_profiles", parts=(ItemPart("nominal"), AttributePart("avg_power"))),
        )
    ]
    assert nominal_avg_power == 100.0


@pytest.mark.xfail(
    reason="Table[K, PydanticModel] with nested field access not yet supported",
    strict=True,
)
def test_table_with_pydantic_model_value_nested_access() -> None:
    """Test accessing individual fields within Pydantic model values in a table."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    class ThermalSpec(BaseModel):
        min_temp: float
        max_temp: float
        heat_capacity: float

    @scope.root_model()
    class RootModel(BaseModel):
        thermal_specs: vq.Table[Component, ThermalSpec]

    @scope.calculation()
    def battery_temp_range(
        battery_min_temp: Annotated[float, vq.Ref("$.thermal_specs[battery].min_temp")],
        battery_max_temp: Annotated[float, vq.Ref("$.thermal_specs[battery].max_temp")],
    ) -> float:
        # Calculate temperature range for battery using individual field references
        return battery_max_temp - battery_min_temp

    model_data = {
        scope.name: RootModel(
            thermal_specs=vq.Table(
                {
                    Component.BATTERY: ThermalSpec(min_temp=-20.0, max_temp=60.0, heat_capacity=100.0),
                    Component.SOLAR: ThermalSpec(min_temp=-40.0, max_temp=80.0, heat_capacity=50.0),
                    Component.PAYLOAD: ThermalSpec(min_temp=-10.0, max_temp=50.0, heat_capacity=75.0),
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    # Verify calculation that accesses nested fields
    temp_range = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_temp_range", parts=()),
        )
    ]
    assert temp_range == 80.0  # 60.0 - (-20.0)


@pytest.mark.xfail(
    reason="Table[K, PydanticModel] with deeply nested models not yet supported",
    strict=True,
)
def test_table_with_complex_pydantic_model_value() -> None:
    """Test Table with nested Pydantic models as values."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    # Define nested Pydantic models
    class Dimensions(BaseModel):
        length: float
        width: float
        height: float

    class ComponentInfo(BaseModel):
        dimensions: Dimensions
        mass: float
        power: float

    @scope.root_model()
    class RootModel(BaseModel):
        component_info: vq.Table[Component, ComponentInfo]

    @scope.calculation()
    def battery_volume(
        length: Annotated[float, vq.Ref("$.component_info[battery].dimensions.length")],
        width: Annotated[float, vq.Ref("$.component_info[battery].dimensions.width")],
        height: Annotated[float, vq.Ref("$.component_info[battery].dimensions.height")],
    ) -> float:
        # Calculate volume from individual dimension fields
        return length * width * height

    model_data = {
        scope.name: RootModel(
            component_info=vq.Table(
                {
                    Component.BATTERY: ComponentInfo(
                        dimensions=Dimensions(length=10.0, width=5.0, height=3.0),
                        mass=5.0,
                        power=100.0,
                    ),
                    Component.SOLAR: ComponentInfo(
                        dimensions=Dimensions(length=20.0, width=10.0, height=0.5),
                        mass=3.0,
                        power=200.0,
                    ),
                    Component.PAYLOAD: ComponentInfo(
                        dimensions=Dimensions(length=8.0, width=6.0, height=4.0),
                        mass=2.0,
                        power=50.0,
                    ),
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    # Verify calculation
    volume = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_volume", parts=()),
        )
    ]
    assert volume == 150.0  # 10.0 * 5.0 * 3.0


# ==================== Tests: Nested Tables (Table with Table as value) ====================


def test_nested_table_single_to_single() -> None:
    """Test Table[K1, Table[K2, V]] - nested single-key tables."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        # Outer table: Component -> Inner table: Mode -> power value
        power_matrix: vq.Table[Component, vq.Table[Mode, float]]

    @scope.calculation()
    def battery_nominal_power(
        power_matrix: Annotated[vq.Table[Component, vq.Table[Mode, float]], vq.Ref("$.power_matrix")],
    ) -> float:
        # Access nested table: battery component, nominal mode
        return power_matrix[Component.BATTERY][Mode.NOMINAL]

    model_data = {
        scope.name: RootModel(
            power_matrix=vq.Table(
                {
                    Component.BATTERY: vq.Table(
                        {
                            Mode.NOMINAL: 100.0,
                            Mode.SAFE: 50.0,
                        },
                    ),
                    Component.SOLAR: vq.Table(
                        {
                            Mode.NOMINAL: 200.0,
                            Mode.SAFE: 100.0,
                        },
                    ),
                    Component.PAYLOAD: vq.Table(
                        {
                            Mode.NOMINAL: 75.0,
                            Mode.SAFE: 25.0,
                        },
                    ),
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    # Verify nested table access
    power = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_nominal_power", parts=()),
        )
    ]
    assert power == 100.0


def test_nested_table_tuple_to_single() -> None:
    """Test Table[tuple[K1, K2], Table[K3, V]] - tuple key outer, single key inner."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        # Outer table: (Component, Phase) -> Inner table: Mode -> power value
        power_matrix: vq.Table[tuple[Component, Phase], vq.Table[Mode, float]]

    @scope.calculation()
    def battery_launch_nominal_power(
        power_matrix: Annotated[
            vq.Table[tuple[Component, Phase], vq.Table[Mode, float]],
            vq.Ref("$.power_matrix"),
        ],
    ) -> float:
        # Access nested table with tuple key
        return power_matrix[(Component.BATTERY, Phase.LAUNCH)][Mode.NOMINAL]

    # Create test data - need all combinations of Component and Phase
    outer_table_data = {}
    for component in Component:
        for phase in Phase:
            # Create inner table for each (component, phase) combination
            outer_table_data[(component, phase)] = vq.Table(
                {
                    Mode.NOMINAL: float((list(Component).index(component) + 1) * 100 + list(Phase).index(phase) * 10),
                    Mode.SAFE: float((list(Component).index(component) + 1) * 50 + list(Phase).index(phase) * 5),
                },
            )

    model_data = {
        scope.name: RootModel(power_matrix=vq.Table(outer_table_data)),
    }

    result = evaluate_project(project, model_data)

    # Verify nested access
    power = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_launch_nominal_power", parts=()),
        )
    ]
    # Battery is first (index 0), so (0+1)*100 = 100
    # Launch is first (index 0), so 0*10 = 0
    # Total: 100 + 0 = 100
    assert power == 100.0


def test_nested_table_as_calculation_output() -> None:
    """Test nested Table as calculation output."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        base_value: float

    @scope.calculation()
    def power_matrix(
        base_value: Annotated[float, vq.Ref("$.base_value")],
    ) -> vq.Table[Component, vq.Table[Mode, float]]:
        # Generate nested table as calculation output
        return vq.Table(
            {
                Component.BATTERY: vq.Table(
                    {
                        Mode.NOMINAL: base_value * 1.0,
                        Mode.SAFE: base_value * 0.5,
                    },
                ),
                Component.SOLAR: vq.Table(
                    {
                        Mode.NOMINAL: base_value * 2.0,
                        Mode.SAFE: base_value * 1.0,
                    },
                ),
                Component.PAYLOAD: vq.Table(
                    {
                        Mode.NOMINAL: base_value * 0.75,
                        Mode.SAFE: base_value * 0.25,
                    },
                ),
            },
        )

    model_data = {scope.name: RootModel(base_value=100.0)}
    result = evaluate_project(project, model_data)

    # Verify nested table calculation output
    # Access the whole outer table
    outer_table = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@power_matrix", parts=()),
        )
    ]
    assert isinstance(outer_table, vq.Table)
    assert outer_table[Component.BATTERY][Mode.NOMINAL] == 100.0
    assert outer_table[Component.SOLAR][Mode.SAFE] == 100.0


def test_nested_table_chained_calculations() -> None:
    """Test chained calculations with nested tables."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        nested_table: vq.Table[Component, vq.Table[Mode, float]]

    @scope.calculation()
    def doubled_nested_table(
        nested_table: Annotated[vq.Table[Component, vq.Table[Mode, float]], vq.Ref("$.nested_table")],
    ) -> vq.Table[Component, vq.Table[Mode, float]]:
        # Double all values in nested table
        result = {}
        for component in Component:
            inner_table = {}
            for mode in Mode:
                inner_table[mode] = nested_table[component][mode] * 2
            result[component] = vq.Table(inner_table)
        return vq.Table(result)

    @scope.calculation()
    def battery_safe_doubled(
        doubled: Annotated[vq.Table[Component, vq.Table[Mode, float]], vq.Ref("@doubled_nested_table")],
    ) -> float:
        return doubled[Component.BATTERY][Mode.SAFE]

    model_data = {
        scope.name: RootModel(
            nested_table=vq.Table(
                {
                    Component.BATTERY: vq.Table({Mode.NOMINAL: 10.0, Mode.SAFE: 5.0}),
                    Component.SOLAR: vq.Table({Mode.NOMINAL: 20.0, Mode.SAFE: 10.0}),
                    Component.PAYLOAD: vq.Table({Mode.NOMINAL: 15.0, Mode.SAFE: 7.5}),
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    # Verify chained calculation
    value = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_safe_doubled", parts=()),
        )
    ]
    assert value == 10.0  # 5.0 * 2


def test_triple_nested_table() -> None:
    """Test deeply nested tables: Table[K1, Table[K2, Table[K3, V]]]."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        # Triple nested: Component -> Phase -> Mode -> float
        power_cube: vq.Table[Component, vq.Table[Phase, vq.Table[Mode, float]]]

    @scope.calculation()
    def battery_launch_nominal_power(
        power_cube: Annotated[
            vq.Table[Component, vq.Table[Phase, vq.Table[Mode, float]]],
            vq.Ref("$.power_cube"),
        ],
    ) -> float:
        # Access triple-nested table
        return power_cube[Component.BATTERY][Phase.LAUNCH][Mode.NOMINAL]

    # Build triple-nested table
    outer_data = {}
    for component in Component:
        middle_data = {}
        for phase in Phase:
            inner_data = {}
            for mode in Mode:
                # Generate some test value
                comp_idx = list(Component).index(component)
                phase_idx = list(Phase).index(phase)
                mode_idx = list(Mode).index(mode)
                value = float((comp_idx + 1) * 100 + phase_idx * 10 + mode_idx)
                inner_data[mode] = value
            middle_data[phase] = vq.Table(inner_data)
        outer_data[component] = vq.Table(middle_data)

    model_data = {
        scope.name: RootModel(power_cube=vq.Table(outer_data)),
    }

    result = evaluate_project(project, model_data)

    # Verify triple-nested access
    power = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_launch_nominal_power", parts=()),
        )
    ]
    # Battery: comp_idx=0, Launch: phase_idx=0, Nominal: mode_idx=0
    # (0+1)*100 + 0*10 + 0 = 100
    assert power == 100.0


# ==================== Tests: Basic edge cases ====================


def test_table_with_string_value() -> None:
    """Test Table with string values."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        component_names: vq.Table[Component, str]

    @scope.calculation()
    def battery_name(
        component_names: Annotated[vq.Table[Component, str], vq.Ref("$.component_names")],
    ) -> str:
        return component_names[Component.BATTERY].upper()

    model_data = {
        scope.name: RootModel(
            component_names=vq.Table(
                {
                    Component.BATTERY: "Lithium-Ion Battery",
                    Component.SOLAR: "Solar Panel Array",
                    Component.PAYLOAD: "Science Payload",
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    name = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_name", parts=()),
        )
    ]
    assert name == "LITHIUM-ION BATTERY"


def test_table_with_int_value() -> None:
    """Test Table with integer values."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        component_ids: vq.Table[Component, int]

    @scope.calculation()
    def total_ids(
        component_ids: Annotated[vq.Table[Component, int], vq.Ref("$.component_ids")],
    ) -> int:
        return sum(component_ids.values())

    model_data = {
        scope.name: RootModel(
            component_ids=vq.Table(
                {
                    Component.BATTERY: 1001,
                    Component.SOLAR: 2002,
                    Component.PAYLOAD: 3003,
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    total = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@total_ids", parts=()),
        )
    ]
    assert total == 6006  # 1001 + 2002 + 3003


def test_table_with_bool_value() -> None:
    """Test Table with boolean values."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        component_active: vq.Table[Component, bool]

    @scope.calculation()
    def active_count(
        component_active: Annotated[vq.Table[Component, bool], vq.Ref("$.component_active")],
    ) -> int:
        return sum(1 for active in component_active.values() if active)

    model_data = {
        scope.name: RootModel(
            component_active=vq.Table(
                {
                    Component.BATTERY: True,
                    Component.SOLAR: True,
                    Component.PAYLOAD: False,
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    count = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@active_count", parts=()),
        )
    ]
    assert count == 2


def test_table_with_list_value() -> None:
    """Test Table with list values."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        component_measurements: vq.Table[Component, list[float]]

    @scope.calculation()
    def battery_avg_measurement(
        component_measurements: Annotated[vq.Table[Component, list[float]], vq.Ref("$.component_measurements")],
    ) -> float:
        battery_measurements = component_measurements[Component.BATTERY]
        return sum(battery_measurements) / len(battery_measurements)

    model_data = {
        scope.name: RootModel(
            component_measurements=vq.Table(
                {
                    Component.BATTERY: [100.0, 105.0, 110.0],
                    Component.SOLAR: [200.0, 210.0, 220.0],
                    Component.PAYLOAD: [50.0, 55.0, 60.0],
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    avg = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_avg_measurement", parts=()),
        )
    ]
    assert avg == 105.0  # (100 + 105 + 110) / 3


def test_table_with_dict_value() -> None:
    """Test Table with dict values."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        component_metadata: vq.Table[Component, dict[str, str]]

    @scope.calculation()
    def battery_manufacturer(
        component_metadata: Annotated[vq.Table[Component, dict[str, str]], vq.Ref("$.component_metadata")],
    ) -> str:
        return component_metadata[Component.BATTERY]["manufacturer"]

    model_data = {
        scope.name: RootModel(
            component_metadata=vq.Table(
                {
                    Component.BATTERY: {"manufacturer": "BattCorp", "model": "LC-100"},
                    Component.SOLAR: {"manufacturer": "SolarTech", "model": "SP-200"},
                    Component.PAYLOAD: {"manufacturer": "ScienceCo", "model": "PL-50"},
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    manufacturer = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_manufacturer", parts=()),
        )
    ]
    assert manufacturer == "BattCorp"


def test_table_with_tuple_single_enum() -> None:
    """Test Table with single-element tuple key (edge case)."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        # Single-element tuple key
        power_table: vq.Table[tuple[Component], float]

    @scope.calculation()
    def battery_power(
        power_table: Annotated[vq.Table[tuple[Component], float], vq.Ref("$.power_table")],
    ) -> float:
        return power_table[(Component.BATTERY,)]

    model_data = {
        scope.name: RootModel(
            power_table=vq.Table(
                {
                    (Component.BATTERY,): 100.0,
                    (Component.SOLAR,): 200.0,
                    (Component.PAYLOAD,): 50.0,
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    power = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@battery_power", parts=()),
        )
    ]
    assert power == 100.0


def test_table_with_four_element_tuple_key() -> None:
    """Test Table with 4-element tuple key (stress test for tuple keys)."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        # Four-element tuple key
        complex_table: vq.Table[tuple[Component, Phase, Mode, Status], float]

    @scope.calculation()
    def specific_value(
        complex_table: Annotated[
            vq.Table[tuple[Component, Phase, Mode, Status], float],
            vq.Ref("$.complex_table"),
        ],
    ) -> float:
        return complex_table[(Component.BATTERY, Phase.LAUNCH, Mode.NOMINAL, Status.ACTIVE)]

    # Build exhaustive table for all combinations
    table_data = {}
    counter = 0.0
    for component in Component:
        for phase in Phase:
            for mode in Mode:
                for status in Status:
                    table_data[(component, phase, mode, status)] = counter
                    counter += 1.0

    model_data = {
        scope.name: RootModel(complex_table=vq.Table(table_data)),
    }

    result = evaluate_project(project, model_data)

    value = result[
        ProjectPath(
            scope=scope.name,
            path=CalcPath(root="@specific_value", parts=()),
        )
    ]
    # The first combination (BATTERY, LAUNCH, NOMINAL, ACTIVE) should have value 0.0
    assert value == 0.0


def test_table_in_verification() -> None:
    """Test using Table in verification functions."""
    project = vq.Project("Test Project")
    scope = vq.Scope("Test Scope")
    project.add_scope(scope)

    @scope.root_model()
    class RootModel(BaseModel):
        power_limits: vq.Table[Component, float]
        actual_power: vq.Table[Component, float]

    @scope.verification()
    def power_within_limits(
        power_limits: Annotated[vq.Table[Component, float], vq.Ref("$.power_limits")],
        actual_power: Annotated[vq.Table[Component, float], vq.Ref("$.actual_power")],
    ) -> bool:
        # Verify all components are within power limits
        for component in Component:
            if actual_power[component] > power_limits[component]:
                return False
        return True

    model_data = {
        scope.name: RootModel(
            power_limits=vq.Table(
                {
                    Component.BATTERY: 120.0,
                    Component.SOLAR: 250.0,
                    Component.PAYLOAD: 60.0,
                },
            ),
            actual_power=vq.Table(
                {
                    Component.BATTERY: 100.0,
                    Component.SOLAR: 200.0,
                    Component.PAYLOAD: 50.0,
                },
            ),
        ),
    }

    result = evaluate_project(project, model_data)

    # Verify verification result - use VerificationPath
    verification_result = result[
        ProjectPath(
            scope=scope.name,
            path=VerificationPath(root="?power_within_limits"),
        )
    ]
    assert verification_result is True


def test_table_serialization_with_pydantic_model_value() -> None:
    """Test that Table with Pydantic model values serializes and deserializes correctly."""

    class ComponentSpec(BaseModel):
        power: float
        mass: float

    class Model(BaseModel):
        specs: vq.Table[Component, ComponentSpec]

    # Create table with model values
    table = vq.Table(
        {
            Component.BATTERY: ComponentSpec(power=100.0, mass=5.0),
            Component.SOLAR: ComponentSpec(power=200.0, mass=3.0),
            Component.PAYLOAD: ComponentSpec(power=50.0, mass=2.0),
        },
    )

    model = Model(specs=table)

    # Serialize
    serialized = model.model_dump()

    # Verify serialization structure
    assert "specs" in serialized
    assert "battery" in serialized["specs"]
    assert serialized["specs"]["battery"]["power"] == 100.0
    assert serialized["specs"]["battery"]["mass"] == 5.0

    # Deserialize
    deserialized_model = Model(**serialized)

    # Verify deserialization
    assert deserialized_model.specs[Component.BATTERY].power == 100.0
    assert deserialized_model.specs[Component.BATTERY].mass == 5.0
    assert deserialized_model.specs[Component.SOLAR].power == 200.0


def test_table_serialization_with_nested_table() -> None:
    """Test that nested Table serializes and deserializes correctly."""

    class Model(BaseModel):
        nested: vq.Table[Component, vq.Table[Mode, float]]

    # Create nested table
    table = vq.Table(
        {
            Component.BATTERY: vq.Table({Mode.NOMINAL: 100.0, Mode.SAFE: 50.0}),
            Component.SOLAR: vq.Table({Mode.NOMINAL: 200.0, Mode.SAFE: 100.0}),
            Component.PAYLOAD: vq.Table({Mode.NOMINAL: 75.0, Mode.SAFE: 25.0}),
        },
    )

    model = Model(nested=table)

    # Serialize
    serialized = model.model_dump()

    # Verify serialization structure
    assert "nested" in serialized
    assert "battery" in serialized["nested"]
    assert serialized["nested"]["battery"]["nominal"] == 100.0
    assert serialized["nested"]["battery"]["safe"] == 50.0

    # Deserialize
    deserialized_model = Model(**serialized)

    # Verify deserialization
    assert deserialized_model.nested[Component.BATTERY][Mode.NOMINAL] == 100.0
    assert deserialized_model.nested[Component.BATTERY][Mode.SAFE] == 50.0
    assert deserialized_model.nested[Component.SOLAR][Mode.NOMINAL] == 200.0
