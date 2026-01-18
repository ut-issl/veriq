---
icon: material/book-open-variant
---

# Core Concepts

This page explains the core concepts behind veriq and how they work together.

## The Spreadsheet Analogy

veriq is like a smart spreadsheet for engineering calculations:

| Spreadsheet | veriq | Description |
|-------------|-------|-------------|
| Workbook | Project | Top-level container |
| Sheet | Scope | Logical grouping (e.g., "Power", "Thermal") |
| Input cells | Model | Design parameters you provide |
| Formula cells | Calculation | Computed values |
| Conditional formatting | Verification | Requirement checks |

## Project

A **Project** is the top-level container for your engineering analysis:

```python
project = vq.Project("MySatellite")
```

A project contains one or more scopes and manages the overall dependency graph.

## Scope

A **Scope** groups related models, calculations, and verifications:

```python
power = vq.Scope("Power")
thermal = vq.Scope("Thermal")

project.add_scope(power)
project.add_scope(thermal)
```

Scopes typically represent subsystems like Power, Thermal, Structure, or AOCS.

## Model

A **Model** defines the input data structure using Pydantic:

```python
@power.root_model()
class PowerModel(BaseModel):
    battery_capacity: float
    solar_panel_area: float
```

Key points:

- Use `@scope.root_model()` to register a model
- Each scope has exactly one root model
- Models are loaded from TOML input files

## Calculation

A **Calculation** computes derived values from inputs:

```python
class SolarOutput(BaseModel):
    power: float
    heat: float


@power.calculation()
def calculate_solar(
    area: Annotated[float, vq.Ref("$.solar_panel_area")],
) -> SolarOutput:
    power = area * 1361.0 * 0.3
    heat = area * 1361.0 * 0.7
    return SolarOutput(power=power, heat=heat)
```

Key points:

- Use `@scope.calculation()` to register
- Parameters use `Annotated[Type, vq.Ref(...)]` to declare dependencies
- Return a Pydantic model with the results
- veriq automatically determines execution order

## Verification

A **Verification** checks that requirements are met:

```python
@power.verification()
def verify_power_margin(
    power: Annotated[float, vq.Ref("@calculate_solar.power")],
) -> bool:
    return power >= 500.0  # Minimum 500W
```

Key points:

- Use `@scope.verification()` to register
- Return `True` for pass, `False` for fail
- Run with `--verify` flag to execute verifications

## References

**References** (`vq.Ref`) declare where to find input values:

### Model References

```python
# Current scope's model field
vq.Ref("$.battery_capacity")

# Nested field
vq.Ref("$.design.solar_panel.area")

# Other scope's model field
vq.Ref("$.battery_capacity", scope="Power")
```

### Calculation References

```python
# Current scope's calculation output
vq.Ref("@calculate_solar.power")

# Other scope's calculation output
vq.Ref("@calculate_temperature.max_temp", scope="Thermal")
```

### Table References

```python
# Single-key table entry
vq.Ref("$.power_consumption[nominal]")

# Multi-key table entry
vq.Ref("$.peak_power[launch,nominal]")
```

### Reference Syntax Summary

| Pattern | Meaning |
|---------|---------|
| `$` | Root of current scope's model |
| `$.field` | Field in model |
| `$.field.subfield` | Nested field |
| `@calc` | Calculation output |
| `@calc.field` | Field in calculation output |
| `[key]` | Table entry |
| `scope="Name"` | Look in different scope |

## Tables

**Tables** handle multi-dimensional data indexed by enums:

```python
from enum import StrEnum

class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"


class PowerModel(BaseModel):
    consumption: vq.Table[Mode, float]
```

### Single-Key Tables

```python
# Definition
power: vq.Table[Mode, float]

# TOML
[Scope.model.power]
nominal = 100.0
safe = 50.0

# Access
power[Mode.NOMINAL]  # Returns 100.0
```

### Multi-Key Tables

```python
# Definition
power: vq.Table[tuple[Phase, Mode], float]

# TOML
[Scope.model.power]
"launch,nominal" = 100.0
"cruise,safe" = 50.0

# Access
power[(Phase.LAUNCH, Mode.NOMINAL)]  # Returns 100.0
```

### Table Verifications

When a verification returns `vq.Table[K, bool]`, each entry becomes a separate result:

```python
@power.verification()
def verify_margin(
    margin: Annotated[vq.Table[Mode, float], vq.Ref("@calc.margin")],
) -> vq.Table[Mode, bool]:
    return vq.Table({mode: margin[mode] > 0 for mode in Mode})
```

## External Data (FileRef)

**FileRef** allows you to reference external files in your models with automatic checksum tracking for reproducibility:

```python
from veriq import FileRef

class DataModel(BaseModel):
    config_file: FileRef
    calibration_data: FileRef
```

### Why Use FileRef?

- **Reproducibility** - Checksums ensure the same file content is used across runs
- **Change Detection** - veriq warns when referenced files change
- **Clean Separation** - Keep large data files (CSV, binary) separate from TOML input

### Using FileRef in TOML

```toml
[Scope.model.config_file]
path = "data/config.json"
checksum = "sha256:abc123..."  # Added by veriq after first run

[Scope.model.calibration_data]
path = "calibration/sensor_data.csv"
```

On the first run, veriq computes and stores the checksum. On subsequent runs, it validates that the file hasn't changed.

### Accessing File Content in Calculations

In calculations, you receive the `FileRef` object and access data via its `path` attribute:

```python
@scope.calculation()
def process_config(
    config_file: Annotated[FileRef, vq.Ref("$.config_file")],
) -> ConfigResult:
    # Read file content via path
    content = config_file.path.read_text()
    data = json.loads(content)
    return ConfigResult(...)
```

### Relative Paths

Relative paths in TOML are resolved relative to the TOML file's directory:

```
project/
├── input.toml           # Contains path = "data/config.json"
└── data/
    └── config.json      # This file is referenced
```

### Checksum Validation

| Scenario | Behavior |
|----------|----------|
| First run (no checksum) | Computes and stores checksum |
| Checksum matches | Proceeds normally |
| Checksum mismatch | Warns user that file changed |

## Cross-Scope Dependencies

When a calculation or verification references another scope, declare it with `imports`:

```python
@thermal.calculation(imports=["Power"])
def calculate_temperature(
    heat: Annotated[float, vq.Ref("@calculate_solar.heat", scope="Power")],
) -> ThermalOutput:
    ...
```

The `imports` parameter:

- Declares dependencies on other scopes
- Enables cross-scope references with `scope="Name"`
- Helps veriq build the correct dependency graph

## Dependency Graph

veriq builds a dependency graph from your references:

1. Parse all `vq.Ref` annotations
2. Build edges between calculations
3. Topologically sort for execution order
4. Execute in order, passing results forward

This means:

- Calculations run in the correct order automatically
- Circular dependencies are detected and reported
- Cross-scope dependencies work seamlessly

## Execution Flow

When you run `veriq calc`:

1. **Load** - Parse TOML input into Pydantic models
2. **Build** - Construct dependency graph from references
3. **Sort** - Topologically sort calculations
4. **Execute** - Run calculations in order
5. **Verify** - Run verifications (if `--verify`)
6. **Export** - Write results to output TOML
