---
icon: material/numeric-2-circle
---

# Step 2: Adding Calculations

In this step, you'll add calculations that derive values from your model inputs.

## What Are Calculations?

Calculations are like spreadsheet formulas. They:

- Take input values from your model
- Compute derived values
- Return a Pydantic model with the results

## Add a Calculation

Building on Step 1, let's calculate power generation from the solar panel:

```python title="examples/tutorial/step2.py"
import veriq as vq
from pydantic import BaseModel
from typing import Annotated

project = vq.Project("MySatellite")
power = vq.Scope("Power")
project.add_scope(power)


@power.root_model()
class PowerModel(BaseModel):
    battery_capacity: float  # in Watt-hours
    solar_panel_area: float  # in square meters
    solar_panel_efficiency: float  # 0.0 to 1.0


# Define the output structure
class SolarPanelOutput(BaseModel):
    power_generated: float  # in Watts
    heat_generated: float  # in Watts


# Create a calculation
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

    return SolarPanelOutput(
        power_generated=power_out,
        heat_generated=heat_out,
    )
```

## Understanding References

The `vq.Ref()` annotation tells veriq where to find input values:

- `"$"` - The root of the current scope's model
- `"$.solar_panel_area"` - The `solar_panel_area` field in the model

References are declared using Python's `Annotated` type:

```python
area: Annotated[float, vq.Ref("$.solar_panel_area")]
```

This means:

- The parameter `area` is a `float`
- Its value comes from `$.solar_panel_area` in the Power scope

## Update Your Input File

Add the new field to your input:

```toml title="examples/tutorial/step2.in.toml"
[Power.model]
battery_capacity = 100.0
solar_panel_area = 2.0
solar_panel_efficiency = 0.3
```

## Run the Calculation

```bash
veriq calc examples/tutorial/step2.py -i examples/tutorial/step2.in.toml -o step2.out.toml
```

The output file now includes calculated values:

```toml
[Power.model]
battery_capacity = 100.0
solar_panel_area = 2.0
solar_panel_efficiency = 0.3

[Power.calc.calculate_solar_panel]
power_generated = 816.6
heat_generated = 1905.4
```

Calculation outputs appear under `[ScopeName.calc.calculation_name]`.

## Multiple Calculations

You can add multiple calculations that depend on each other:

```python
class BatteryOutput(BaseModel):
    charge_time: float  # in hours


@power.calculation()
def calculate_battery_charge(
    capacity: Annotated[float, vq.Ref("$.battery_capacity")],
    power: Annotated[float, vq.Ref("@calculate_solar_panel.power_generated")],
) -> BatteryOutput:
    """Calculate time to charge battery from solar power."""
    charge_time = capacity / power if power > 0 else float("inf")
    return BatteryOutput(charge_time=charge_time)
```

Note the reference `@calculate_solar_panel.power_generated`:

- `@` prefix indicates a calculation (not a model field)
- `calculate_solar_panel` is the calculation name
- `power_generated` is a field in the calculation's output

veriq automatically determines the correct order to run calculations based on their dependencies.

## What You Learned

- **Calculation**: A function that computes derived values
- **`@scope.calculation()`**: Decorator to register a calculation
- **`vq.Ref("$.field")`**: Reference a model field
- **`vq.Ref("@calc.field")`**: Reference a calculation output
- **Automatic ordering**: veriq resolves dependencies automatically

## Next Step

In [Step 3](step3-cross-scope.md), you'll connect multiple scopes with cross-scope references.
