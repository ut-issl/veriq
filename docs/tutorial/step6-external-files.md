---
icon: material/numeric-6-circle
---

# Step 6: External Files

In this step, you'll learn how to reference external files in your models using `FileRef`, with automatic checksum tracking for reproducibility.

## Why External Files?

Engineering projects often involve data that doesn't fit well in TOML:

- Large datasets (sensor calibration, orbit ephemeris)
- Binary files (lookup tables, coefficient matrices)
- Structured data (CSV, JSON configuration)

Embedding this data directly in TOML would be impractical. `FileRef` lets you:

- Reference external files from your model
- Track file changes with checksums
- Keep your TOML input clean and focused

## Define a FileRef in Your Model

Use `vq.FileRef` as a field type in your Pydantic model:

```python title="examples/tutorial/step6.py"
import csv
from typing import Annotated

from pydantic import BaseModel

import veriq as vq

project = vq.Project("MySatellite")
power = vq.Scope("Power")
project.add_scope(power)


@power.root_model()
class PowerModel(BaseModel):
    # Reference to an external CSV file with power profiles
    power_profile: vq.FileRef

    # Regular scalar values work alongside FileRef
    battery_capacity: float


class PowerAnalysisOutput(BaseModel):
    peak_power: float
    average_power: float
    total_energy: float


@power.calculation()
def analyze_power_profile(
    power_profile: Annotated[vq.FileRef, vq.Ref("$.power_profile")],
    battery_capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> PowerAnalysisOutput:
    """Analyze power profile from external CSV file."""
    # Read CSV file via the path attribute
    with power_profile.path.open() as f:
        reader = csv.DictReader(f)
        powers = [float(row["power"]) for row in reader]

    peak = max(powers)
    average = sum(powers) / len(powers)
    total = sum(powers)  # Simplified: assuming 1-hour intervals

    return PowerAnalysisOutput(
        peak_power=peak,
        average_power=average,
        total_energy=total,
    )


@power.verification()
def verify_battery_sufficient(
    total_energy: Annotated[float, vq.Ref("@analyze_power_profile.total_energy")],
    battery_capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> bool:
    """Verify battery can supply the total energy needed."""
    return battery_capacity >= total_energy
```

## Create the External Data File

Create a CSV file with your power profile data:

```csv title="examples/tutorial/power_profile.csv"
time,power
0,50.0
1,55.0
2,80.0
3,45.0
4,60.0
```

## Reference Files in TOML

In your input TOML, use a table to specify the file path:

```toml title="examples/tutorial/step6.in.toml"
[Power.model]
battery_capacity = 300.0

[Power.model.power_profile]
path = "power_profile.csv"
```

Note: Relative paths are resolved relative to the TOML file's directory.

## Run the Example

```bash
veriq calc examples/tutorial/step6.py -i examples/tutorial/step6.in.toml -o step6.out.toml --verify
```

Output:

```
╭──────────────────── Verification Results ────────────────────╮
│  Verification                              Result            │
│  Power::verify_battery_sufficient          ✓ PASS            │
╰──────────────────────────────────────────────────────────────╯

✓ Calculation complete
```

## Checksum Tracking

After the first run, veriq warns about new external data references and computes checksums:

```
⚠ New external data references detected (no stored checksum):
  • Power::$.power_profile
    Computed: sha256:47beef29cf99a42d...
```

You can add the checksum to your input TOML to track data changes:

```toml title="step6.in.toml (with checksum)"
[Power.model]
battery_capacity = 300.0

[Power.model.power_profile]
path = "power_profile.csv"
checksum = "sha256:47beef29cf99a42d1e0361f5d0ac0659c2d6b49b2a2656f8f5c30b41373cfab7"
```

The output file contains the calculation results:

```toml title="step6.out.toml"
[Power.model]
battery_capacity = 300.0

[Power.model.power_profile]
path = "power_profile.csv"

[Power.calc.analyze_power_profile]
peak_power = 80.0
average_power = 58.0
total_energy = 290.0

[Power.verification]
verify_battery_sufficient = true
```

### What Happens When Files Change?

| Scenario | Behavior |
|----------|----------|
| First run (no checksum) | Computes and stores checksum |
| File unchanged | Proceeds normally |
| File changed | Warns that file content differs from stored checksum |

This ensures reproducibility - you'll know if results might differ because input data changed.

## Accessing File Content

In calculations, `FileRef` provides a `path` attribute that returns a `pathlib.Path`:

```python
@scope.calculation()
def process_data(
    data_file: Annotated[vq.FileRef, vq.Ref("$.data_file")],
) -> Result:
    # Read as text
    text_content = data_file.path.read_text()

    # Read as bytes (for binary files)
    binary_content = data_file.path.read_bytes()

    # Use with libraries that accept paths
    import json
    with data_file.path.open() as f:
        data = json.load(f)

    return Result(...)
```

## Multiple File References

You can have multiple `FileRef` fields in a model:

```python
@scope.root_model()
class CalibrationModel(BaseModel):
    sensor_calibration: vq.FileRef
    thermal_coefficients: vq.FileRef
    orbit_ephemeris: vq.FileRef
```

```toml
[Scope.model.sensor_calibration]
path = "data/sensor_cal.json"

[Scope.model.thermal_coefficients]
path = "data/thermal_coeff.csv"

[Scope.model.orbit_ephemeris]
path = "data/orbit.txt"
```

## Project Structure

A typical project with external files:

```
my_project/
├── project.py           # veriq project definition
├── input.toml           # References external files
└── data/
    ├── power_profile.csv
    ├── thermal_data.json
    └── calibration.bin
```

## What You Learned

- **`vq.FileRef`**: Reference external files in your models
- **File access**: Use `.path` attribute to read file content
- **Checksum tracking**: Automatic change detection for reproducibility
- **TOML syntax**: How to specify file references in input files

## Tutorial Complete

You've now learned all the core features of veriq:

1. **Projects and Scopes** - Organize your analysis
2. **Models** - Define input parameters
3. **Calculations** - Compute derived values
4. **Cross-Scope References** - Connect scopes
5. **Verifications** - Check requirements
6. **Tables** - Handle category-indexed data
7. **External Files** - Reference data files with checksums

## Next Steps

- See [Concepts](../concepts.md) for a deeper understanding
- Check the [CLI Reference](../cli-reference.md) for all command options
- Explore the complete example in `examples/dummysat.py`
