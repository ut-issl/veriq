---
icon: material/numeric-4-circle
---

# Step 4: Verifications

In this step, you'll add verifications to check that your design meets requirements.

## What Are Verifications?

Verifications are like conditional formatting in spreadsheets. They:

- Check if calculated values meet specified requirements
- Return `True` (pass) or `False` (fail)
- Can reference both model inputs and calculation outputs

## Add a Temperature Verification

Building on Step 3, let's verify that the solar panel temperature stays within limits:

```python title="examples/tutorial/step4.py"
import veriq as vq
from pydantic import BaseModel
from typing import Annotated

project = vq.Project("MySatellite")

power = vq.Scope("Power")
thermal = vq.Scope("Thermal")
project.add_scope(power)
project.add_scope(thermal)


# --- Power Scope ---
@power.root_model()
class PowerModel(BaseModel):
    solar_panel_area: float
    solar_panel_efficiency: float
    max_temperature: float  # Maximum allowable temperature


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
    thermal_coefficient: float


class ThermalOutput(BaseModel):
    solar_panel_temperature: float


@thermal.calculation(imports=["Power"])
def calculate_temperature(
    heat: Annotated[float, vq.Ref("@calculate_solar_panel.heat_generated", scope="Power")],
    coefficient: Annotated[float, vq.Ref("$.thermal_coefficient")],
) -> ThermalOutput:
    temperature = heat * coefficient
    return ThermalOutput(solar_panel_temperature=temperature)


# --- Verification ---
@thermal.verification(imports=["Power"])
def verify_temperature_limit(
    temperature: Annotated[float, vq.Ref("@calculate_temperature.solar_panel_temperature")],
    max_temp: Annotated[float, vq.Ref("$.max_temperature", scope="Power")],
) -> bool:
    """Verify that solar panel temperature is within limits."""
    return temperature <= max_temp
```

## Verification Syntax

Verifications use `@scope.verification()` and return a `bool`:

```python
@thermal.verification(imports=["Power"])
def verify_temperature_limit(
    temperature: Annotated[float, vq.Ref("@calculate_temperature.solar_panel_temperature")],
    max_temp: Annotated[float, vq.Ref("$.max_temperature", scope="Power")],
) -> bool:
    return temperature <= max_temp
```

Key points:

- Use `@scope.verification()` decorator
- Declare cross-scope dependencies with `imports=`
- Return `True` for pass, `False` for fail

## Update Your Input File

Add the maximum temperature limit:

```toml title="examples/tutorial/step4.in.toml"
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.3
max_temperature = 85.0

[Thermal.model]
thermal_coefficient = 0.05
```

## Run with Verification

Use the `--verify` flag to run verifications:

```bash
veriq calc examples/tutorial/step4.py -i examples/tutorial/step4.in.toml -o step4.out.toml --verify
```

Output:

```
Loading project from script: examples/tutorial/step4.py
Project: MySatellite

Loading input from: examples/tutorial/step4.in.toml
Evaluating project...

╭──────────────────── Verification Results ────────────────────╮
│  Verification                        Result                  │
│  Thermal::verify_temperature_limit   ✗ FAIL                  │
╰───────────────────────────────────────────────────────────────╯

✗ Verification failed
```

The verification fails because the calculated temperature (95.27°C) exceeds the limit (85°C).

## Fix the Design

Increase panel efficiency to reduce heat:

```toml title="examples/tutorial/step4.in.toml (updated)"
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.35  # Increased from 0.3
max_temperature = 85.0

[Thermal.model]
thermal_coefficient = 0.05
```

Run again:

```bash
veriq calc examples/tutorial/step4.py -i examples/tutorial/step4.in.toml -o step4.out.toml --verify
```

Now it passes:

```
╭──────────────────── Verification Results ────────────────────╮
│  Verification                        Result                  │
│  Thermal::verify_temperature_limit   ✓ PASS                  │
╰───────────────────────────────────────────────────────────────╯

✓ Calculation complete
```

## Output File with Verification Results

The output TOML includes verification results:

```toml
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.35
max_temperature = 85.0

[Power.calc.calculate_solar_panel]
power_generated = 952.7
heat_generated = 1769.3

[Thermal.model]
thermal_coefficient = 0.05

[Thermal.calc.calculate_temperature]
solar_panel_temperature = 88.465

[Thermal.verification]
verify_temperature_limit = true
```

## Multiple Verifications

You can add multiple verifications per scope:

```python
@power.verification()
def verify_minimum_power(
    power: Annotated[float, vq.Ref("@calculate_solar_panel.power_generated")],
) -> bool:
    """Verify minimum power generation requirement."""
    min_power = 500.0  # Watts
    return power >= min_power


@power.verification()
def verify_efficiency_reasonable(
    efficiency: Annotated[float, vq.Ref("$.solar_panel_efficiency")],
) -> bool:
    """Verify efficiency is within realistic bounds."""
    return 0.1 <= efficiency <= 0.5
```

## What You Learned

- **Verification**: A function that checks requirements
- **`@scope.verification()`**: Decorator to register a verification
- **`--verify` flag**: Run verifications and report results
- **Exit codes**: veriq exits with code 1 if any verification fails

## Next Step

In [Step 5](step5-tables.md), you'll use tables to handle multi-dimensional data like operating modes.
