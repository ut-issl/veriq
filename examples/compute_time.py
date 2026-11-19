"""Computation-time example: user metadata on nodes and structure-aware aggregation.

This example attaches a ``compute_time_s`` value to every calculation and verification
and then asks two different questions about a verification:

1. *How long does it take to evaluate everything it depends on, one node after another?*
   A set-style aggregation: sum over the upstream definitions, each counted once.
2. *How long until it can run if independent nodes evaluate in parallel?*
   A structure-aware aggregation: the critical path, propagated along the dependency DAG.

The dependency graph is diamond-shaped on purpose, so the two answers differ:

    Power::$ ──► @solar_generation (30 s) ──┐
       │                                     ├──► @power_margin (5 s) ──► ?margin_positive (2 s)
       └──────► @battery_sizing (120 s) ─────┘

``@solar_generation`` additionally *assumes* ``Thermal::?panel_within_limit``, which itself
depends on the solar generation result. veriq treats assumptions as premises checked after
the fact, so they are part of the upstream closure but never act as ordering constraints.

Run it:

    veriq calc examples/compute_time.py -i examples/compute_time.in.toml -o /tmp/out.toml --verify
    veriq upstream "Power::?margin_positive" -p examples/compute_time.py --key compute_time_s --bindings \\
        -i examples/compute_time.in.toml
    uv run python examples/compute_time.py      # the same aggregations through the Python API
"""

from typing import Annotated

from pydantic import BaseModel

import veriq as vq

# -----------------------------------------------------------------------------
# Project and scopes
# -----------------------------------------------------------------------------

project = vq.Project("ComputeTime")
power = vq.Scope("Power")
thermal = vq.Scope("Thermal")
project.add_scope(power)
project.add_scope(thermal)


# -----------------------------------------------------------------------------
# Models
#
# `vq.Meta` records properties of a field *definition* (unit, governing document, ...).
# The rationale for a concrete *value* lives next to the value, in the `provenance`
# table of the input TOML (see compute_time.in.toml).
# -----------------------------------------------------------------------------


class SolarPanel(BaseModel):
    area_m2: Annotated[float, vq.Meta(unit="m^2")]
    efficiency: Annotated[float, vq.Meta(unit="-", source_doc="SP-DS-004")]
    max_temp_c: Annotated[float, vq.Meta(unit="degC", source_doc="SP-DS-004")]


class Battery(BaseModel):
    capacity_ah: Annotated[float, vq.Meta(unit="Ah")]
    max_c_rate: Annotated[float, vq.Meta(unit="1/h")]


@power.root_model(metadata={"owner": "eps-team"})
class PowerDesign(BaseModel):
    solar_panel: Annotated[SolarPanel, vq.Meta(source_doc="SP-DS-004")]  # inherited by solar_panel.*
    battery: Battery
    bus_voltage_v: Annotated[float, vq.Meta(unit="V")]
    load_w: Annotated[float, vq.Meta(unit="W")]


@thermal.root_model(metadata={"owner": "thermal-team"})
class ThermalDesign(BaseModel):
    ambient_temp_c: Annotated[float, vq.Meta(unit="degC")]
    panel_heating_c_per_w: Annotated[float, vq.Meta(unit="degC/W")]


# -----------------------------------------------------------------------------
# Calculations: `metadata=` is free-form; veriq only stores it.
# -----------------------------------------------------------------------------


class BatteryBudget(BaseModel):
    energy_wh: float
    max_discharge_w: float


class PowerMargin(BaseModel):
    margin_w: float
    ratio: float


@power.calculation(imports=["Thermal"], metadata={"compute_time_s": 30.0, "tool": "orbit-propagator"})
@vq.assume(vq.Ref("?panel_within_limit", scope="Thermal"))
def solar_generation(panel: Annotated[SolarPanel, vq.Ref("$.solar_panel")]) -> float:
    """Average generated power [W], assuming the panel stays within its temperature limit."""
    solar_constant_w_per_m2 = 1361.0
    return panel.area_m2 * panel.efficiency * solar_constant_w_per_m2


@power.calculation(metadata={"compute_time_s": 120.0, "tool": "battery-model"})
def battery_sizing(
    battery: Annotated[Battery, vq.Ref("$.battery")],
    bus_voltage_v: Annotated[float, vq.Ref("$.bus_voltage_v")],
) -> BatteryBudget:
    energy_wh = battery.capacity_ah * bus_voltage_v
    return BatteryBudget(energy_wh=energy_wh, max_discharge_w=energy_wh * battery.max_c_rate)


@power.calculation(metadata={"compute_time_s": 5.0})
def power_margin(
    generation_w: Annotated[float, vq.Ref("@solar_generation")],
    max_discharge_w: Annotated[float, vq.Ref("@battery_sizing.max_discharge_w")],
    load_w: Annotated[float, vq.Ref("$.load_w")],
) -> PowerMargin:
    available_w = min(generation_w, max_discharge_w)
    return PowerMargin(margin_w=available_w - load_w, ratio=available_w / load_w)


@thermal.calculation(imports=["Power"], metadata={"compute_time_s": 45.0, "tool": "thermal-fem"})
def panel_temperature(
    ambient_temp_c: Annotated[float, vq.Ref("$.ambient_temp_c")],
    heating_c_per_w: Annotated[float, vq.Ref("$.panel_heating_c_per_w")],
    generation_w: Annotated[float, vq.Ref("@solar_generation", scope="Power")],
) -> float:
    return ambient_temp_c + heating_c_per_w * generation_w


# -----------------------------------------------------------------------------
# Verifications
# -----------------------------------------------------------------------------


@power.verification(metadata={"compute_time_s": 2.0})
def margin_positive(margin_w: Annotated[float, vq.Ref("@power_margin.margin_w")]) -> bool:
    return margin_w > 0


@thermal.verification(imports=["Power"], metadata={"compute_time_s": 1.0})
def panel_within_limit(
    panel_temp_c: Annotated[float, vq.Ref("@panel_temperature")],
    max_temp_c: Annotated[float, vq.Ref("$.solar_panel.max_temp_c", scope="Power")],
) -> bool:
    return panel_temp_c <= max_temp_c


# -----------------------------------------------------------------------------
# Requirements
# -----------------------------------------------------------------------------

power.requirement(
    "PWR-001",
    description="The power subsystem shall provide a positive power margin in nominal operation.",
    verified_by=[vq.Ref("?margin_positive")],
)


# -----------------------------------------------------------------------------
# The same aggregations through the Python API
# -----------------------------------------------------------------------------


def main() -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_positive")

    print(f"Upstream of {sub.target}: {len(sub)} definitions")
    for node_id in sub.topological_order():
        node = sub.nodes[node_id]
        print(
            f"  {node.kind.upper():<13} {node_id!s:<32} compute_time_s={node.user_metadata.get('compute_time_s', 0.0)}",
        )

    # Set-style: iterate the node set. Each definition once, no matter how many leaves it has.
    sequential = sum(n.user_metadata.get("compute_time_s", 0.0) for n in sub.nodes.values())
    # Structure-aware: critical path along data edges.
    parallel = sub.propagate("compute_time_s", combine=max)
    print(f"Sequential total : {sequential:>6.1f} s  (sum over definitions)")
    print(f"Critical path    : {parallel:>6.1f} s  (propagate with combine=max)")

    # With follow_assumes=False the assumed verification is still a node, but its own upstream is
    # left out, so the set-style total shrinks. The critical path does not change: assume edges
    # never take part in propagation.
    data_only = vq.upstream_subgraph(project, "Power::?margin_positive", follow_assumes=False)
    sequential_data_only = sum(n.user_metadata.get("compute_time_s", 0.0) for n in data_only.nodes.values())
    print(f"Sequential total : {sequential_data_only:>6.1f} s  (follow_assumes=False)")

    # Where do the inputs come from?
    print("Inputs (parameter <- reference):")
    for node_id in sub.topological_order():
        for binding in sub.inputs_of(node_id):
            print(f"  {node_id}: {binding.param} <- {binding.ref}")


if __name__ == "__main__":
    main()
