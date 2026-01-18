import json
from enum import StrEnum, unique
from typing import Annotated

from pydantic import BaseModel

import veriq as vq

project = vq.Project("Project")

system = vq.Scope("System")
thermal = vq.Scope("Thermal")
power = vq.Scope("Power")
aocs = vq.Scope("AOCS")
rwa = vq.Scope("RWA")

project.add_scope(system)
project.add_scope(aocs)
project.add_scope(power)
project.add_scope(thermal)
project.add_scope(rwa)


@unique
class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"
    MISSION = "mission"


@unique
class OperationPhase(StrEnum):
    INITIAL = "initial"
    CRUISE = "cruise"


@system.root_model()
class SatelliteModel(BaseModel):
    pass


@aocs.root_model()
class AOCSModel(BaseModel):
    # reaction_wheel_assembly: ReactionWheelAssemblyModel
    design: AOCSDesign
    requirement: AOCSRequirement


class AOCSDesign(BaseModel): ...


@rwa.root_model()
class ReactionWheelAssemblyModel(BaseModel):
    wheel_x: ReactionWheelModel
    wheel_y: ReactionWheelModel
    wheel_z: ReactionWheelModel

    # required by PowerInterface
    power_consumption: vq.Table[OperationMode, float]
    power_limit: vq.Table[OperationMode, float]
    peak_power_consumption: vq.Table[tuple[OperationPhase, OperationMode], float]

    # required by StructuralInterface
    mass: float


class ReactionWheelModel(BaseModel):
    max_torque: float  # in Nm
    power_consumption: float  # in Watts
    mass: float  # in kg


class AOCSRequirement(BaseModel): ...


# - There should be at most one model per scope.
@power.root_model()
class PowerSubsystemModel(BaseModel):
    design: PowerSubsystemDesign
    requirement: PowerSubsystemRequirement


class PowerSubsystemDesign(BaseModel):
    battery_a: BatteryModel
    battery_b: BatteryModel
    solar_panel: SolarPanelModel

    # Power budget per operation mode
    power_generation: vq.Table[OperationMode, float]  # in Watts
    power_consumption: vq.Table[OperationMode, float]  # in Watts

    # External configuration file
    config_file: vq.FileRef


class PowerSubsystemRequirement(BaseModel): ...


class BatteryModel(BaseModel):
    capacity: float  # in Watt-hours
    min_capacity: float  # minimum required capacity in Watt-hours


class SolarPanelModel(BaseModel):
    area: float  # in square meters
    efficiency: float  # as a fraction
    max_temperature: float  # maximum allowable temperature in Celsius
    thermal_coefficient: float  # heat-to-temperature conversion factor


class SolarPanelResult(BaseModel):
    heat_generation: float  # in Watts


@thermal.root_model()
class ThermalModel(BaseModel): ...


class ThermalResult(BaseModel):
    solar_panel_temperature_max: float  # in Celsius


@system.verification(imports=["Power", "Thermal"])
def power_thermal_compatibility(
    power_model: Annotated[PowerSubsystemModel, vq.Ref("$", scope="Power")],
    thermal_model: Annotated[ThermalModel, vq.Ref("$", scope="Thermal")],
) -> bool:
    """Verify the compatibility between power and thermal subsystems."""
    # Here we would implement the actual verification logic.
    return True  # Example condition


# Lookup order
# 1. Determine the scope. If not specified, use the scope of the function decorator.
# 2. If it has an accessor, use the accessor to get the model.
# 3. Otherwise, look for the model in the determined scope.
#    There should be at most one use of the model in that scope, or an error is raised.
@power.verification()
def verify_battery(
    first_battery: Annotated[BatteryModel, vq.Ref("$.design.battery_a")],
) -> bool:
    return first_battery.capacity > first_battery.min_capacity


@power.verification()
def verify_power_budget(
    power_generation: Annotated[vq.Table[OperationMode, float], vq.Ref("$.design.power_generation")],
    power_consumption: Annotated[vq.Table[OperationMode, float], vq.Ref("$.design.power_consumption")],
) -> vq.Table[OperationMode, bool]:
    """Verify that power generation exceeds consumption for each operation mode."""
    return vq.Table({mode: power_generation[mode] > power_consumption[mode] for mode in OperationMode})  # ty: ignore[invalid-return-type]


# Verification returning Table[K, bool]: verify power margins per operation mode.
# Each entry in the returned table represents a separate verification result.
@rwa.verification()
def verify_power_margin(
    power_consumption: Annotated[vq.Table[OperationMode, float], vq.Ref("$.power_consumption")],
    power_limit: Annotated[vq.Table[OperationMode, float], vq.Ref("$.power_limit")],
) -> vq.Table[OperationMode, bool]:
    """Verify that power consumption is within limits for each operation mode."""
    return vq.Table({mode: power_consumption[mode] < power_limit[mode] for mode in OperationMode})  # ty: ignore[invalid-return-type]


@thermal.calculation(imports=["Power"])
def calculate_temperature(
    solar_panel_heat_generation: Annotated[
        float,
        vq.Ref("@calculate_solar_panel_heat.heat_generation", scope="Power"),
    ],
    thermal_coefficient: Annotated[
        float,
        vq.Ref("$.design.solar_panel.thermal_coefficient", scope="Power"),
    ],
) -> ThermalResult:
    """Calculate the thermal result based on the thermal model and solar panel result."""
    temperature = solar_panel_heat_generation * thermal_coefficient
    return ThermalResult(solar_panel_temperature_max=temperature)


@power.verification(imports=["Thermal"], xfail=True)
def solar_panel_max_temperature(
    solar_panel_temperature_max: Annotated[
        float,
        vq.Ref("@calculate_temperature.solar_panel_temperature_max", scope="Thermal"),
    ],
    solar_panel: Annotated[SolarPanelModel, vq.Ref("$.design.solar_panel")],
) -> bool:
    """Assert that the solar panel maximum temperature is within limits."""
    return solar_panel_temperature_max < solar_panel.max_temperature


@power.calculation()
@vq.assume(vq.Ref("?solar_panel_max_temperature"))
def calculate_solar_panel_heat(
    solar_panel: Annotated[SolarPanelModel, vq.Ref("$.design.solar_panel")],
    config_file: Annotated[vq.FileRef, vq.Ref("$.design.config_file")],
) -> SolarPanelResult:
    """Calculate the heat generation of the solar panel using config parameters."""
    # Load configuration from external file
    config = json.loads(config_file.path.read_text())
    efficiency_derating = config.get("efficiency_derating", 1.0)

    # Calculate heat generation with derating factor
    heat_generation = 100.0 * efficiency_derating
    return SolarPanelResult(heat_generation=heat_generation)


# The following requirement definitions are in a different module in practice.
# This example demonstrates various requirement statuses in `veriq trace` output:
#   - VERIFIED: Requirement has direct verifications, all passed
#   - SATISFIED: No direct verifications, but all children pass
#   - FAILED: Some verification or child failed
#   - NOT_VERIFIED: Leaf requirement with no verifications (coverage gap)

with system.requirement("REQ-SYS-001", "System-level requirement (status propagates from children)."):
    # REQ-SYS-002: Will be FAILED because child REQ-TH-001 fails
    system.requirement("REQ-SYS-002", "Thermal subsystem requirements.")
    # REQ-SYS-003: Will be SATISFIED because all children pass (no direct verifications)
    with power.requirement("REQ-SYS-003", "Power subsystem requirements."):
        # REQ-PWR-001: Will be VERIFIED because both verifications pass
        power.requirement(
            "REQ-PWR-001",
            "Battery and power budget requirements.",
            verified_by=[verify_battery, verify_power_budget],
        )
    # REQ-SYS-004: Will be NOT_VERIFIED (no verifications attached)
    system.requirement("REQ-SYS-004", "Future requirement (not yet verified).")

with system.fetch_requirement("REQ-SYS-002"):
    # REQ-TH-001: Will be FAILED because solar_panel_max_temperature fails
    thermal.requirement(
        "REQ-TH-001",
        "Solar panel temperature must be within limits.",
        verified_by=[solar_panel_max_temperature],
    )
