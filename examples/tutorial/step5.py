"""Step 5: Using Tables.

This example demonstrates how to use tables for multi-dimensional
data like operating modes.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel

import veriq as vq

project = vq.Project("MySatellite")
power = vq.Scope("Power")
project.add_scope(power)


class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"
    MISSION = "mission"


@power.root_model()
class PowerModel(BaseModel):
    # Single values
    battery_capacity: float  # in Watt-hours

    # Tables indexed by operation mode
    power_consumption: vq.Table[OperationMode, float]  # in Watts
    power_generation: vq.Table[OperationMode, float]  # in Watts


class PowerMarginOutput(BaseModel):
    margin: vq.Table[OperationMode, float]  # in Watts


@power.calculation()
def calculate_power_margin(
    consumption: Annotated[vq.Table[OperationMode, float], vq.Ref("$.power_consumption")],
    generation: Annotated[vq.Table[OperationMode, float], vq.Ref("$.power_generation")],
) -> PowerMarginOutput:
    """Calculate power margin for each operation mode."""
    margin = vq.Table({mode: generation[mode] - consumption[mode] for mode in OperationMode})
    return PowerMarginOutput(margin=margin)  # type: ignore[arg-type]


@power.verification()
def verify_positive_margin(
    margin: Annotated[vq.Table[OperationMode, float], vq.Ref("@calculate_power_margin.margin")],
) -> vq.Table[OperationMode, bool]:
    """Verify positive power margin for each mode."""
    return vq.Table({mode: margin[mode] > 0 for mode in OperationMode})  # type: ignore[return-value]
