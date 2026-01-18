"""Step 6: External Files - Reference data files with automatic checksum tracking."""

from typing import Annotated

from pydantic import BaseModel

import veriq as vq

project = vq.Project("MySatellite")
power = vq.Scope("Power")
project.add_scope(power)


@power.root_model()
class PowerModel(BaseModel):
    # Reference to an external CSV file with power profiles
    power_profile: vq.FileRef

    # Regular scalar values work alongside FileRef
    battery_capacity: float


class PowerAnalysisOutput(BaseModel):
    peak_power: float
    average_power: float
    total_energy: float


@power.calculation()
def analyze_power_profile(
    power_profile: Annotated[vq.FileRef, vq.Ref("$.power_profile")],
    battery_capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> PowerAnalysisOutput:
    """Analyze power profile from external CSV file."""
    # Read file content via the path attribute
    content = power_profile.path.read_text()

    # Parse CSV (time, power pairs)
    lines = content.strip().split("\n")
    powers = []
    for line in lines[1:]:  # Skip header
        _time, power = line.split(",")
        powers.append(float(power))

    peak = max(powers)
    average = sum(powers) / len(powers)
    total = sum(powers)  # Simplified: assuming 1-hour intervals

    return PowerAnalysisOutput(
        peak_power=peak,
        average_power=average,
        total_energy=total,
    )


@power.verification()
def verify_battery_sufficient(
    total_energy: Annotated[float, vq.Ref("@analyze_power_profile.total_energy")],
    battery_capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> bool:
    """Verify battery can supply the total energy needed."""
    return battery_capacity >= total_energy
