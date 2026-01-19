"""Step 7: Requirements Traceability.

This example demonstrates how to define requirements and link them to verifications.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel

import veriq as vq

project = vq.Project("MySatellite")

system = vq.Scope("System")
power = vq.Scope("Power")
thermal = vq.Scope("Thermal")
project.add_scope(system)
project.add_scope(power)
project.add_scope(thermal)


class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"


# --- System Scope (container for system-level requirements) ---
@system.root_model()
class SystemModel(BaseModel):
    pass


# --- Power Scope ---
@power.root_model()
class PowerModel(BaseModel):
    battery_capacity: float
    power_generation: vq.Table[Mode, float]
    power_consumption: vq.Table[Mode, float]


@power.verification()
def verify_battery(
    capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> bool:
    """Battery capacity must be at least 100 Wh."""
    return capacity >= 100.0


@power.verification()
def verify_power_margin(
    generation: Annotated[vq.Table[Mode, float], vq.Ref("$.power_generation")],
    consumption: Annotated[vq.Table[Mode, float], vq.Ref("$.power_consumption")],
) -> vq.Table[Mode, bool]:
    """Power generation must exceed consumption in all modes."""
    return vq.Table({mode: generation[mode] > consumption[mode] for mode in Mode})


# --- Thermal Scope ---
@thermal.root_model()
class ThermalModel(BaseModel):
    max_temperature: float
    calculated_temperature: float


@thermal.verification()
def verify_temperature(
    temp: Annotated[float, vq.Ref("$.calculated_temperature")],
    max_temp: Annotated[float, vq.Ref("$.max_temperature")],
) -> bool:
    """Temperature must be within limits."""
    return temp <= max_temp


# --- Requirements Definition ---
# System-level requirement with children
with system.requirement("REQ-SYS-001", "System shall meet all subsystem requirements."):
    # Power subsystem requirements
    with system.requirement("REQ-SYS-002", "Power subsystem requirements."):
        power.requirement(
            "REQ-PWR-001",
            "Battery capacity must be sufficient.",
            verified_by=[verify_battery],
        )
        power.requirement(
            "REQ-PWR-002",
            "Power margin must be positive in all modes.",
            verified_by=[verify_power_margin],
        )

    # Thermal subsystem requirements
    with system.requirement("REQ-SYS-003", "Thermal subsystem requirements."):
        thermal.requirement(
            "REQ-TH-001",
            "Temperature must be within limits.",
            verified_by=[verify_temperature],
        )

    # Future requirement (not yet verified)
    system.requirement("REQ-SYS-004", "Future requirement (placeholder).")
