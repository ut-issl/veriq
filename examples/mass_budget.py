"""Mass Budget Example for veriq.

This example demonstrates veriq's capabilities for satellite mass budget management:
- NumPy integration for center of gravity (CoG) calculations
- Table usage for component-indexed and axis-indexed data
- Parameterized requirements via TOML input
- Requirement traceability with hierarchical requirement tree

Prerequisites:
    This example requires NumPy. Install it with:
        uv pip install numpy
"""

from enum import StrEnum, unique
from typing import Annotated

import numpy as np
from pydantic import BaseModel

import veriq as vq

# -----------------------------------------------------------------------------
# Project and Scope Setup
# -----------------------------------------------------------------------------

project = vq.Project("Mass Budget")
system = vq.Scope("System")
project.add_scope(system)


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


@unique
class Component(StrEnum):
    """Satellite components tracked in the mass budget."""

    STRUCTURE = "structure"
    BATTERY = "battery"
    SOLAR_PANEL = "solar_panel"


@unique
class Axis(StrEnum):
    """Coordinate axes for CoG calculations."""

    X = "x"
    Y = "y"
    Z = "z"


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class MassBudgetDesign(BaseModel):
    """Design parameters for the mass budget.

    Each component has:
    - mass: Current Best Estimate (CBE) in kg
    - position: (x, y, z) coordinates in meters from satellite origin
    - margin_percent: growth margin as percentage
    """

    mass: vq.Table[Component, float]  # kg (Current Best Estimate)
    position: vq.Table[tuple[Component, Axis], float]  # m from satellite origin
    margin_percent: vq.Table[Component, float]  # growth margin percentage


class MassBudgetRequirement(BaseModel):
    """Requirement parameters for mass budget verification."""

    mass_limit: float  # kg - launch vehicle mass constraint
    cog_limit: vq.Table[Axis, float]  # m - CoG envelope per axis (±limit from origin)


@system.root_model()
class MassBudgetModel(BaseModel):
    """Root model for the mass budget scope."""

    design: MassBudgetDesign
    requirement: MassBudgetRequirement


# -----------------------------------------------------------------------------
# Calculation Results
# -----------------------------------------------------------------------------


class MassResult(BaseModel):
    """Result of mass calculations."""

    total_mass: float  # kg (CBE total)
    mass_with_margin: float  # kg (total with margins applied)


class CogResult(BaseModel):
    """Result of center of gravity calculation."""

    cog: vq.Table[Axis, float]  # m (x, y, z) from satellite origin


# -----------------------------------------------------------------------------
# Calculations
# -----------------------------------------------------------------------------


@system.calculation()
def calculate_mass(
    mass: Annotated[vq.Table[Component, float], vq.Ref("$.design.mass")],
    margin_percent: Annotated[vq.Table[Component, float], vq.Ref("$.design.margin_percent")],
) -> MassResult:
    """Calculate total mass and mass with margin using NumPy.

    Total mass is the sum of all component CBE masses.
    Mass with margin applies each component's individual margin percentage.
    """
    masses = np.array(list(mass.values()))
    margins = np.array(list(margin_percent.values()))

    total_mass = float(np.sum(masses))
    mass_with_margin = float(np.sum(masses * (1 + margins / 100)))

    return MassResult(total_mass=total_mass, mass_with_margin=mass_with_margin)


@system.calculation()
def calculate_cog(
    mass: Annotated[vq.Table[Component, float], vq.Ref("$.design.mass")],
    position: Annotated[vq.Table[tuple[Component, Axis], float], vq.Ref("$.design.position")],
) -> CogResult:
    """Calculate center of gravity using NumPy weighted average.

    CoG = sum(mass_i * position_i) / sum(mass_i)
    """
    masses = np.array(list(mass.values()))
    positions = np.array([[position[comp, axis] for axis in Axis] for comp in Component])

    # Weighted average: sum(mass * position) / sum(mass)
    total_mass = np.sum(masses)
    cog_vector = np.sum(masses[:, np.newaxis] * positions, axis=0) / total_mass

    return CogResult(
        cog=vq.Table(  # ty: ignore[invalid-argument-type]
            {
                Axis.X: float(cog_vector[0]),
                Axis.Y: float(cog_vector[1]),
                Axis.Z: float(cog_vector[2]),
            },
        ),
    )


# -----------------------------------------------------------------------------
# Verifications
# -----------------------------------------------------------------------------


@system.verification()
def verify_total_mass(
    mass_with_margin: Annotated[float, vq.Ref("@calculate_mass.mass_with_margin")],
    mass_limit: Annotated[float, vq.Ref("$.requirement.mass_limit")],
) -> bool:
    """Verify that total mass with margin does not exceed the launch vehicle limit."""
    return mass_with_margin <= mass_limit


@system.verification()
def verify_cog_envelope(
    cog: Annotated[vq.Table[Axis, float], vq.Ref("@calculate_cog.cog")],
    cog_limit: Annotated[vq.Table[Axis, float], vq.Ref("$.requirement.cog_limit")],
) -> vq.Table[Axis, bool]:
    """Verify that CoG is within the allowed envelope for each axis."""
    return vq.Table({axis: abs(cog[axis]) <= cog_limit[axis] for axis in Axis})  # ty: ignore[invalid-return-type]


# -----------------------------------------------------------------------------
# Requirements
# -----------------------------------------------------------------------------

with system.requirement("REQ-MAS-001", "Mass properties shall meet launch vehicle constraints."):
    system.requirement(
        "REQ-MAS-002",
        "Total mass with margin shall not exceed LV limit.",
        verified_by=[verify_total_mass],
    )
    system.requirement(
        "REQ-MAS-003",
        "CoG shall be within allowed envelope.",
        verified_by=[verify_cog_envelope],
    )
