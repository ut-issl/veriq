---
icon: material/numeric-5-circle
---

# Step 5: Using Tables

In this step, you'll use tables to handle data indexed by categories - similar to how spreadsheets organize data in rows and columns.

## Why Tables?

In spreadsheets, you often have data organized by categories:

| Mode    | Consumption | Generation |
|---------|-------------|------------|
| nominal | 50          | 60         |
| safe    | 20          | 30         |
| mission | 80          | 100        |

You might then calculate margins for each row and verify that all margins are positive.

`vq.Table` lets you represent this pattern in veriq. Instead of repeating calculations manually for each row, you define the calculation once and veriq applies it across all categories.

## Define Categories with an Enum

First, define your row categories using a `StrEnum`:

```python
from enum import StrEnum

class OperationMode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"
    MISSION = "mission"
```

## Use Tables in Models

Use `vq.Table[KeyType, ValueType]` to define a column of values indexed by category:

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
    # Single value (like a single cell)
    battery_capacity: float

    # Tables (like columns indexed by row category)
    power_consumption: vq.Table[OperationMode, float]
    power_generation: vq.Table[OperationMode, float]


class PowerMarginOutput(BaseModel):
    margin: vq.Table[OperationMode, float]


@power.calculation()
def calculate_power_margin(
    consumption: Annotated[vq.Table[OperationMode, float], vq.Ref("$.power_consumption")],
    generation: Annotated[vq.Table[OperationMode, float], vq.Ref("$.power_generation")],
) -> PowerMarginOutput:
    """Calculate margin for each row."""
    margin = vq.Table({mode: generation[mode] - consumption[mode] for mode in OperationMode})
    return PowerMarginOutput(margin=margin)


@power.verification()
def verify_positive_margin(
    margin: Annotated[vq.Table[OperationMode, float], vq.Ref("@calculate_power_margin.margin")],
) -> vq.Table[OperationMode, bool]:
    """Verify positive margin for each row."""
    return vq.Table({mode: margin[mode] > 0 for mode in OperationMode})
```

## Table Verification Returns

When a verification returns `vq.Table[K, bool]`, each entry becomes a separate verification result - like applying conditional formatting to each row:

```python
@power.verification()
def verify_positive_margin(
    margin: Annotated[vq.Table[OperationMode, float], vq.Ref("@calculate_power_margin.margin")],
) -> vq.Table[OperationMode, bool]:
    return vq.Table({mode: margin[mode] > 0 for mode in OperationMode})
```

This creates three verification results:

- `verify_positive_margin[nominal]`
- `verify_positive_margin[safe]`
- `verify_positive_margin[mission]`

## TOML Format for Tables

Tables are defined as TOML tables, where each key is a row category:

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

For data indexed by two categories (like a pivot table), use a tuple key:

```python
class Row(StrEnum):
    A = "a"
    B = "b"

class Column(StrEnum):
    X = "x"
    Y = "y"


class MyModel(BaseModel):
    values: vq.Table[tuple[Row, Column], float]
```

In TOML, use comma-separated keys:

```toml
[Scope.model.values]
"a,x" = 100.0
"a,y" = 200.0
"b,x" = 150.0
"b,y" = 250.0
```

Reference individual table entries:

```python
# Single-key table entry
vq.Ref("$.power_consumption[nominal]")

# Multi-key table entry
vq.Ref("$.values[a,x]")
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

- **`vq.Table[K, V]`**: Define data indexed by category (like spreadsheet columns)
- **Table calculations**: Compute values for each row
- **Table verifications**: Check requirements across all rows (like conditional formatting)
- **Multi-dimensional tables**: Use tuple keys (like pivot tables)
- **TOML format**: How to specify table data in input files

## Next Step

Continue to [Step 6: External Files](step6-external-files.md) to learn how to reference data files with automatic checksum tracking.
