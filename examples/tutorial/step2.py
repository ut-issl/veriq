"""Step 2: Adding Calculations.

This example demonstrates how to add calculations that derive
values from your model inputs.
"""

from typing import Annotated

from pydantic import BaseModel

import veriq as vq

project = vq.Project("MySatellite")
power = vq.Scope("Power")
project.add_scope(power)


@power.root_model()
class PowerModel(BaseModel):
    battery_capacity: float  # in Watt-hours
    solar_panel_area: float  # in square meters
    solar_panel_efficiency: float  # 0.0 to 1.0


# Define the output structure
class SolarPanelOutput(BaseModel):
    power_generated: float  # in Watts
    heat_generated: float  # in Watts


# Create a calculation
@power.calculation()
def calculate_solar_panel(
    area: Annotated[float, vq.Ref("$.solar_panel_area")],
    efficiency: Annotated[float, vq.Ref("$.solar_panel_efficiency")],
) -> SolarPanelOutput:
    """Calculate power and heat from solar panels."""
    solar_flux = 1361.0  # W/m² at Earth orbit
    power_in = area * solar_flux
    power_out = power_in * efficiency
    heat_out = power_in - power_out

    return SolarPanelOutput(
        power_generated=power_out,
        heat_generated=heat_out,
    )


class BatteryOutput(BaseModel):
    charge_time: float  # in hours


@power.calculation()
def calculate_battery_charge(
    capacity: Annotated[float, vq.Ref("$.battery_capacity")],
    power: Annotated[float, vq.Ref("@calculate_solar_panel.power_generated")],
) -> BatteryOutput:
    """Calculate time to charge battery from solar power."""
    charge_time = capacity / power if power > 0 else float("inf")
    return BatteryOutput(charge_time=charge_time)
