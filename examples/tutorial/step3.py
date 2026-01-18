"""Step 3: Cross-Scope References.

This example demonstrates how to connect multiple scopes
so calculations in one scope can use values from another.
"""

from typing import Annotated

from pydantic import BaseModel

import veriq as vq

project = vq.Project("MySatellite")

# Create two scopes
power = vq.Scope("Power")
thermal = vq.Scope("Thermal")
project.add_scope(power)
project.add_scope(thermal)


# --- Power Scope ---
@power.root_model()
class PowerModel(BaseModel):
    solar_panel_area: float  # in square meters
    solar_panel_efficiency: float  # 0.0 to 1.0


class SolarPanelOutput(BaseModel):
    power_generated: float  # in Watts
    heat_generated: float  # in Watts


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
    return SolarPanelOutput(power_generated=power_out, heat_generated=heat_out)


# --- Thermal Scope ---
@thermal.root_model()
class ThermalModel(BaseModel):
    thermal_coefficient: float  # °C per Watt


class ThermalOutput(BaseModel):
    solar_panel_temperature: float  # in °C


@thermal.calculation(imports=["Power"])
def calculate_temperature(
    heat: Annotated[float, vq.Ref("@calculate_solar_panel.heat_generated", scope="Power")],
    coefficient: Annotated[float, vq.Ref("$.thermal_coefficient")],
) -> ThermalOutput:
    """Calculate solar panel temperature from heat generation."""
    temperature = heat * coefficient
    return ThermalOutput(solar_panel_temperature=temperature)
