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


@power.verification()
def verify_minimum_power(
    power: Annotated[float, vq.Ref("@calculate_solar_panel.power_generated")],
) -> bool:
    """Verify minimum power generation requirement."""
    min_power = 500.0  # Watts
    return power >= min_power


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

## Input File

Create an input file with the design parameters:

```toml title="examples/tutorial/step4.in.toml"
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.40
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
╭──────────────────── Verification Results ────────────────────╮
│  Verification                         Result                 │
│  Power::?verify_minimum_power         ✓ PASS                 │
│  Thermal::?verify_temperature_limit   ✓ PASS                 │
╰───────────────────────────────────────────────────────────────╯

✓ Calculation complete
```

Both verifications pass:

- Power generation (1088.8 W) exceeds minimum (500 W)
- Temperature (81.66°C) is within limit (85°C)

## When Verification Fails

If you lower the efficiency to 0.30, the temperature will exceed the limit:

```toml
solar_panel_efficiency = 0.30  # Lower efficiency = more heat
```

Running verification shows:

```
╭──────────────────── Verification Results ────────────────────╮
│  Verification                         Result                 │
│  Power::?verify_minimum_power         ✓ PASS                 │
│  Thermal::?verify_temperature_limit   ✗ FAIL                 │
╰───────────────────────────────────────────────────────────────╯

✗ Some verifications failed
```

The verification fails because the calculated temperature (95.27°C) exceeds the limit (85°C).

## Output File with Verification Results

The output TOML includes verification results:

```toml
[Power.model]
solar_panel_area = 2.0
solar_panel_efficiency = 0.4
max_temperature = 85.0

[Power.calc.calculate_solar_panel]
power_generated = 1088.8
heat_generated = 1633.2

[Power.verification]
verify_minimum_power = true

[Thermal.model]
thermal_coefficient = 0.05

[Thermal.calc.calculate_temperature]
solar_panel_temperature = 81.66

[Thermal.verification]
verify_temperature_limit = true
```

## What You Learned

- **Verification**: A function that checks requirements
- **`@scope.verification()`**: Decorator to register a verification
- **`--verify` flag**: Run verifications and report results
- **Exit codes**: veriq exits with code 1 if any verification fails

## Next Step

In [Step 5](step5-tables.md), you'll use tables to handle multi-dimensional data like operating modes.
