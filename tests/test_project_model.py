from enum import StrEnum, unique
from typing import Annotated

from pydantic import BaseModel

import veriq as vq


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
