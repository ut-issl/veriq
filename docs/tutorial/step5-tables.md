---
icon: material/numeric-5-circle
---

# Step 5: Using Tables

In this step, you'll use tables to handle multi-dimensional data like operating modes.

## Why Tables?

Engineering systems often have multiple operating modes:

- **Nominal**: Normal operations
- **Safe**: Low-power emergency mode
- **Mission**: High-power payload operations

Tables let you define values for each mode and verify requirements across all modes.

## Define an Enum for Modes

First, define an enum for your operating modes:

```python
from enum import StrEnum

class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"
    MISSION = "mission"
```

## Use Tables in Models

Use `vq.Table[KeyType, ValueType]` in your model:

```python title="examples/tutorial/step5.py"
import veriq as vq
from enum import StrEnum
from pydantic import BaseModel
from typing import Annotated

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
    battery_capacity: float

    # Table indexed by operation mode
    power_consumption: vq.Table[OperationMode, float]
    power_generation: vq.Table[OperationMode, float]


class PowerMarginOutput(BaseModel):
    margin: vq.Table[OperationMode, float]


@power.calculation()
def calculate_power_margin(
    consumption: Annotated[vq.Table[OperationMode, float], vq.Ref("$.power_consumption")],
    generation: Annotated[vq.Table[OperationMode, float], vq.Ref("$.power_generation")],
) -> PowerMarginOutput:
    """Calculate power margin for each operation mode."""
    margin = vq.Table({mode: generation[mode] - consumption[mode] for mode in OperationMode})
    return PowerMarginOutput(margin=margin)


@power.verification()
def verify_positive_margin(
    margin: Annotated[vq.Table[OperationMode, float], vq.Ref("@calculate_power_margin.margin")],
) -> vq.Table[OperationMode, bool]:
    """Verify positive power margin for each mode."""
    return vq.Table({mode: margin[mode] > 0 for mode in OperationMode})
```

## Table Verification Returns

When a verification returns `vq.Table[K, bool]`, each entry is treated as a separate verification result:

```python
@power.verification()
def verify_positive_margin(
    margin: Annotated[vq.Table[OperationMode, float], vq.Ref("@calculate_power_margin.margin")],
) -> vq.Table[OperationMode, bool]:  # Returns a table of booleans
    return vq.Table({mode: margin[mode] > 0 for mode in OperationMode})
```

This creates three verification results:

- `verify_positive_margin[nominal]`
- `verify_positive_margin[safe]`
- `verify_positive_margin[mission]`

## TOML Format for Tables

Tables are defined as TOML tables:

```toml title="examples/tutorial/step5.in.toml"
[Power.model]
battery_capacity = 100.0

[Power.model.power_consumption]
nominal = 50.0
safe = 20.0
mission = 80.0

[Power.model.power_generation]
nominal = 60.0
safe = 30.0
mission = 100.0
```

## Multi-Dimensional Tables

For tables with multiple keys, use a tuple:

```python
class OperationPhase(StrEnum):
    LAUNCH = "launch"
    CRUISE = "cruise"


class PowerModel(BaseModel):
    # Table indexed by (phase, mode)
    peak_power: vq.Table[tuple[OperationPhase, OperationMode], float]
```

In TOML, use comma-separated keys:

```toml
[Power.model.peak_power]
"launch,nominal" = 100.0
"launch,safe" = 30.0
"launch,mission" = 150.0
"cruise,nominal" = 80.0
"cruise,safe" = 25.0
"cruise,mission" = 120.0
```

Reference individual table entries:

```python
# Reference a specific entry
vq.Ref("$.power_consumption[nominal]")

# Reference multi-dimensional entry
vq.Ref("$.peak_power[launch,nominal]")
```

## Run the Example

```bash
veriq calc examples/tutorial/step5.py -i examples/tutorial/step5.in.toml -o step5.out.toml --verify
```

Output:

```
╭──────────────────── Verification Results ────────────────────╮
│  Verification                              Result            │
│  Power::verify_positive_margin[nominal]    ✓ PASS            │
│  Power::verify_positive_margin[safe]       ✓ PASS            │
│  Power::verify_positive_margin[mission]    ✓ PASS            │
╰───────────────────────────────────────────────────────────────╯

✓ Calculation complete
```

## Output File

```toml
[Power.model]
battery_capacity = 100.0

[Power.model.power_consumption]
nominal = 50.0
safe = 20.0
mission = 80.0

[Power.model.power_generation]
nominal = 60.0
safe = 30.0
mission = 100.0

[Power.calc.calculate_power_margin.margin]
nominal = 10.0
safe = 10.0
mission = 20.0

[Power.verification.verify_positive_margin]
nominal = true
safe = true
mission = true
```

## What You Learned

- **`vq.Table[K, V]`**: Define enum-indexed data
- **Table calculations**: Compute values for each mode
- **Table verifications**: Verify requirements across all modes
- **Multi-dimensional tables**: Use tuple keys for complex indexing
- **TOML format**: How to specify table data in input files

## Tutorial Complete!

Congratulations! You've learned the core concepts of veriq:

1. **Projects and Scopes** - Organize your engineering analysis
2. **Models** - Define typed input parameters
3. **Calculations** - Compute derived values with automatic dependency tracking
4. **Cross-Scope References** - Connect subsystems
5. **Verifications** - Check requirements
6. **Tables** - Handle multi-mode analysis

## Next Steps

- See [Concepts](../concepts.md) for a deeper understanding
- Check the [CLI Reference](../cli-reference.md) for all command options
- Explore the complete example in `examples/dummysat.py`
