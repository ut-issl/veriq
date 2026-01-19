---
icon: material/numeric-7-circle
---

# Step 7: Requirements Traceability

In this step, you'll learn how to define engineering requirements and link them to verifications. This creates a complete traceability chain from requirements to verification results.

## Why Requirements Matter

So far, we've created verifications that check if values meet certain conditions. But in engineering projects, we need to:

- **Document requirements** - What constraints must the design satisfy?
- **Track coverage** - Which requirements have verifications?
- **Show traceability** - Which verifications prove which requirements?
- **Report status** - Are all requirements satisfied?

veriq's requirement system addresses all these needs.

## Defining Requirements

Requirements are created using `scope.requirement()`:

```python
import veriq as vq

project = vq.Project("MySatellite")
power = vq.Scope("Power")
project.add_scope(power)

# Define a requirement
power.requirement(
    "REQ-PWR-001",
    "Battery capacity must be at least 100 Wh.",
)
```

Each requirement has:

- **ID** - A unique identifier (e.g., "REQ-PWR-001")
- **Description** - Human-readable explanation

## Linking Verifications to Requirements

The key to traceability is linking verifications to requirements using `verified_by`:

```python
@power.verification()
def verify_battery_capacity(
    capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> bool:
    return capacity >= 100.0

# Link the verification to the requirement
power.requirement(
    "REQ-PWR-001",
    "Battery capacity must be at least 100 Wh.",
    verified_by=[verify_battery_capacity],
)
```

Now when you run `veriq trace`, you can see that REQ-PWR-001 is verified by `verify_battery_capacity`.

## Hierarchical Requirements

Real projects have hierarchical requirements. Use the context manager pattern to create parent-child relationships:

```python
system = vq.Scope("System")
project.add_scope(system)

# Parent requirement with children
with system.requirement("REQ-SYS-001", "System shall meet all subsystem requirements."):
    # Child requirements (automatically nested under REQ-SYS-001)
    power.requirement(
        "REQ-PWR-001",
        "Battery capacity must be at least 100 Wh.",
        verified_by=[verify_battery_capacity],
    )
    power.requirement(
        "REQ-PWR-002",
        "Power margin must be positive in all modes.",
        verified_by=[verify_power_margin],
    )
```

The parent requirement's status is derived from its children:

- **SATISFIED** - All children pass (parent has no direct verifications)
- **FAILED** - Any child fails

## Cross-Scope Requirements

Requirements can span multiple scopes. Use `fetch_requirement()` to add children to an existing requirement:

```python
# Define parent in System scope
with system.requirement("REQ-SYS-002", "Thermal constraints."):
    pass  # Children added later

# Add child from Thermal scope
with system.fetch_requirement("REQ-SYS-002"):
    thermal.requirement(
        "REQ-TH-001",
        "Solar panel temperature must be within limits.",
        verified_by=[verify_temperature],
    )
```

## Complete Example

Here's a complete example with hierarchical requirements:

```python title="examples/tutorial/step7.py"
import veriq as vq
from pydantic import BaseModel
from typing import Annotated
from enum import StrEnum

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
```

## Input File

```toml title="examples/tutorial/step7.in.toml"
[Power.model]
battery_capacity = 150.0

[Power.model.power_generation]
nominal = 100.0
safe = 50.0

[Power.model.power_consumption]
nominal = 80.0
safe = 30.0

[Thermal.model]
max_temperature = 85.0
calculated_temperature = 75.0
```

## Running Traceability Analysis

Use `veriq trace` to see the requirement tree with verification status:

```bash
veriq trace examples/tutorial/step7.py -i examples/tutorial/step7.in.toml
```

**Example output:**

```
 Requirement          Description                              Status          Verifications
 REQ-SYS-001          System shall meet all subsystem requi... ○ SATISFIED     -
 ├── REQ-SYS-002      Power subsystem requirements.            ○ SATISFIED     -
 │   ├── REQ-PWR-001  Battery capacity must be sufficient.     ✓ VERIFIED      ✓ Power::?verify_battery
 │   └── REQ-PWR-002  Power margin must be positive in all...  ✓ VERIFIED      ✓ Power::?verify_power_margin[nominal]
 │                                                                             ✓ Power::?verify_power_margin[safe]
 ├── REQ-SYS-003      Thermal subsystem requirements.          ○ SATISFIED     -
 │   └── REQ-TH-001   Temperature must be within limits.       ✓ VERIFIED      ✓ Thermal::?verify_temperature
 └── REQ-SYS-004      Future requirement (placeholder).        ? NOT_VERIFIED  -

╭───────────────────────────────────────────────────── Summary ──────────────────────────────────────────────────────╮
│ Total requirements: 7                                                                                              │
│ ✓ Verified: 3                                                                                                      │
│ ○ Satisfied: 3                                                                                                     │
│ ✗ Failed: 0                                                                                                        │
│ ? Not verified: 1                                                                                                  │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

✓ All requirements satisfied
```

## Requirement Statuses

| Status | Symbol | Meaning |
|--------|--------|---------|
| VERIFIED | ✓ | Has direct verifications, all passed |
| SATISFIED | ○ | No direct verifications, but all children pass |
| FAILED | ✗ | Some verification or child failed |
| NOT_VERIFIED | ? | Leaf requirement with no verifications (coverage gap) |

## Expected Failures (xfail)

Sometimes you need to track requirements that are known to fail temporarily. Use `xfail=True`:

```python
power.requirement(
    "REQ-PWR-003",
    "Advanced power management (not yet implemented).",
    verified_by=[verify_advanced_power],
    xfail=True,  # Expected to fail
)
```

Expected failures are marked differently in the trace output and don't cause `veriq trace` to exit with an error code.

## Requirement Dependencies

Use `vq.depends()` to declare that one requirement depends on another:

```python
req_power = power.requirement("REQ-PWR-001", "Power requirement.")

with power.requirement("REQ-PWR-002", "Dependent requirement."):
    vq.depends(req_power)  # REQ-PWR-002 depends on REQ-PWR-001
```

If REQ-PWR-001 fails, REQ-PWR-002 will also be marked as failed.

## What You Learned

- **Requirements** - Define engineering requirements with IDs and descriptions
- **`verified_by`** - Link verifications to requirements for traceability
- **Hierarchical requirements** - Use context managers for parent-child relationships
- **`fetch_requirement()`** - Add children to requirements across scopes
- **`veriq trace`** - View requirement tree with verification status
- **Requirement statuses** - VERIFIED, SATISFIED, FAILED, NOT_VERIFIED
- **`xfail`** - Mark requirements as expected failures
- **`vq.depends()`** - Declare dependencies between requirements

## Summary

The requirement system in veriq provides:

1. **Documentation** - Requirements are defined in code alongside verifications
2. **Traceability** - Clear links from requirements to verifications
3. **Coverage analysis** - Identify requirements without verifications (NOT_VERIFIED)
4. **Status propagation** - Parent requirements inherit status from children
5. **Reporting** - `veriq trace` shows the complete picture

This completes the tutorial! You now know how to use veriq to:

- Define projects with scopes and models
- Create calculations with automatic dependency resolution
- Add verifications to check requirements
- Use tables for multi-dimensional data
- Reference external files with checksum tracking
- Define requirements with full traceability
