---
icon: material/numeric-3-circle
---

# Step 3: Cross-Scope References

In this step, you'll connect multiple scopes so calculations in one scope can use values from another.

## Why Multiple Scopes?

Real engineering projects have interdependent subsystems:

- The **Thermal** subsystem needs to know heat generation from **Power**
- The **Power** subsystem needs mass estimates from **Structure**
- The **AOCS** subsystem needs power budgets from **Power**

Scopes let you organize these subsystems while maintaining their connections.

## Add a Thermal Scope

Building on Step 2, let's add a Thermal scope that calculates temperature based on heat from the Power scope:

```python title="examples/tutorial/step3.py"
import veriq as vq
from pydantic import BaseModel
from typing import Annotated

project = vq.Project("MySatellite")

# Create two scopes
power = vq.Scope("Power")
thermal = vq.Scope("Thermal")
project.add_scope(power)
project.add_scope(thermal)


# --- Power Scope ---
@power.root_model()
class PowerModel(BaseModel):
    solar_panel_area: float
    solar_panel_efficiency: float


class SolarPanelOutput(BaseModel):
    power_generated: float
    heat_generated: float


@power.calculation()
def calculate_solar_panel(
    area: Annotated[float, vq.Ref("$.solar_panel_area")],
    efficiency: Annotated[float, vq.Ref("$.solar_panel_efficiency")],
) -> SolarPanelOutput:
    solar_flux = 1361.0
    power_in = area * solar_flux
    power_out = power_in * efficiency
    heat_out = power_in - power_out
    return SolarPanelOutput(power_generated=power_out, heat_generated=heat_out)


# --- Thermal Scope ---
@thermal.root_model()
class ThermalModel(BaseModel):
    thermal_coefficient: float  # °C per Watt


class ThermalOutput(BaseModel):
    solar_panel_temperature: float  # in °C


@thermal.calculation(imports=["Power"])  # (1)!
def calculate_temperature(
    heat: Annotated[float, vq.Ref("@calculate_solar_panel.heat_generated", scope="Power")],  # (2)!
    coefficient: Annotated[float, vq.Ref("$.thermal_coefficient")],
) -> ThermalOutput:
    """Calculate solar panel temperature from heat generation."""
    temperature = heat * coefficient
    return ThermalOutput(solar_panel_temperature=temperature)
```

1. `imports=["Power"]` declares that this calculation depends on the Power scope
2. `scope="Power"` specifies where to find the referenced calculation

## Key Concepts

### Declaring Imports

When a calculation references another scope, you must declare it with `imports`:

```python
@thermal.calculation(imports=["Power"])
def calculate_temperature(...):
```

This tells veriq that the Thermal scope depends on the Power scope.

### Cross-Scope References

To reference a value from another scope, add `scope="ScopeName"`:

```python
# Reference a calculation from Power scope
vq.Ref("@calculate_solar_panel.heat_generated", scope="Power")

# Reference a model field from Power scope
vq.Ref("$.solar_panel_area", scope="Power")
```

Without `scope=`, references look in the current scope.

## Update Your Input File

Add the Thermal model inputs:

```toml title="examples/tutorial/step3.in.toml"
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.3

[Thermal.model]
thermal_coefficient = 0.05
```

## Run the Calculation

```bash
veriq calc examples/tutorial/step3.py -i examples/tutorial/step3.in.toml -o step3.out.toml
```

Output:

```toml
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.3

[Power.calc.calculate_solar_panel]
power_generated = 816.6
heat_generated = 1905.4

[Thermal.model]
thermal_coefficient = 0.05

[Thermal.calc.calculate_temperature]
solar_panel_temperature = 95.27
```

veriq automatically runs Power calculations before Thermal calculations because of the dependency.

## Dependency Graph

veriq builds a dependency graph from your references:

```
PowerModel
    ↓
calculate_solar_panel
    ↓
ThermalModel + calculate_solar_panel.heat_generated
    ↓
calculate_temperature
```

This ensures calculations run in the correct order, regardless of how you define them in code.

## What You Learned

- **Multiple scopes**: Organize subsystems independently
- **`imports=["ScopeName"]`**: Declare scope dependencies
- **`scope="ScopeName"`**: Reference values from other scopes
- **Automatic ordering**: veriq resolves cross-scope dependencies

## Next Step

In [Step 4](step4-verifications.md), you'll add verifications to check that your design meets requirements.
