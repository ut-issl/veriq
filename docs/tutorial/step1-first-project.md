---
icon: material/numeric-1-circle
---

# Step 1: Your First Project

In this step, you'll create your first veriq project with a single scope and model.

## The Spreadsheet Analogy

If you've used spreadsheets like Excel, you already understand veriq's core concepts:

| Spreadsheet | veriq | Description |
|-------------|-------|-------------|
| Workbook | Project | The top-level container |
| Sheet | Scope | A logical grouping (e.g., "Power", "Thermal") |
| Input cells | Model | Design parameters you provide |
| Formula cells | Calculation | Computed values |
| Conditional formatting | Verification | Requirement checks |

## Create Your First Project

Create a file `step1.py`:

```python title="examples/tutorial/step1.py"
import veriq as vq
from pydantic import BaseModel

# Create a project (like a workbook)
project = vq.Project("MySatellite")

# Create a scope (like a sheet)
power = vq.Scope("Power")
project.add_scope(power)


# Define a model (input cells)
@power.root_model()
class PowerModel(BaseModel):
    battery_capacity: float  # in Watt-hours
    solar_panel_area: float  # in square meters
```

This defines:

- A **Project** named "MySatellite"
- A **Scope** named "Power" for the power subsystem
- A **Model** with two design parameters: battery capacity and solar panel area

## Create an Input File

Create `step1.in.toml` with your design values:

```toml title="examples/tutorial/step1.in.toml"
[Power.model]
battery_capacity = 100.0
solar_panel_area = 2.0
```

The TOML structure follows the pattern `[ScopeName.model]` for input data.

## Check Your Project

Verify that your project structure is valid:

```bash
veriq check examples/tutorial/step1.py
```

You should see:

```
Loading project from script: examples/tutorial/step1.py
Project: MySatellite

Validating dependencies...

╭───────────────────────── Project: MySatellite ─────────────────────────╮
│ ┏━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓                               │
│ ┃ Scope ┃ Calculations ┃ Verifications ┃                               │
│ ┡━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩                               │
│ │ Power │            0 │             0 │                               │
│ └───────┴──────────────┴───────────────┘                               │
╰─────────────────────────────────────────────────────── 1 scope ────────╯

✓ Project is valid
```

## Run Calculations

Even without calculations, you can run veriq to see the input/output flow:

```bash
veriq calc examples/tutorial/step1.py -i examples/tutorial/step1.in.toml -o step1.out.toml
```

The output file `step1.out.toml` will contain your input values:

```toml
[Power.model]
battery_capacity = 100.0
solar_panel_area = 2.0
```

## What You Learned

- **Project**: Top-level container for your engineering analysis
- **Scope**: Logical grouping for a subsystem
- **Model**: Pydantic BaseModel defining input parameters
- **`@scope.root_model()`**: Decorator to register a model with a scope

## Next Step

In [Step 2](step2-calculations.md), you'll add calculations to compute derived values from your model.
