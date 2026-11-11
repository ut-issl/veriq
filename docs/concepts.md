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
| Cell comments | Requirement | Engineering constraints with traceability |

## Project

A **Project** is the top-level container for your engineering analysis:

```python
project = vq.Project("MySatellite")
```

A project contains one or more scopes and manages the overall dependency graph.

To load a project defined in another file the way the CLI does, use `vq.load_project()` with either a script path or a `module.path:variable` string:

```python
project = vq.load_project("examples/compute_time.py")
project = vq.load_project("examples.compute_time:project")
project = vq.load_project()  # [tool.veriq].project from the nearest pyproject.toml
```

The CLI's defaults from `[tool.veriq]` (project, input and output paths, resolved against the project root) are available through `vq.get_config()`, so tools built on veriq can honour the same configuration:

```python
config = vq.get_config()  # or vq.get_config(start_dir)
project = vq.load_project(config=config)
provenance = vq.load_provenance_from_toml(project, config.input) if config.input else {}
```

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

## Requirements

**Requirements** define engineering constraints that your design must satisfy. They form the traceability link between what must be achieved and how it's verified:

```python
# Define a requirement
power.requirement(
    "REQ-PWR-001",
    "Battery capacity must be at least 100 Wh.",
    verified_by=[vq.Ref("?verify_battery")],
)
```

Key points:

- Use `scope.requirement()` to define requirements
- Each requirement has an ID and description
- Link verifications with `verified_by` using `vq.Ref("?verification_name")`
- Use context managers for hierarchical requirements

### Hierarchical Requirements

Real engineering projects have requirements at multiple levels:

```python
# Parent requirement with children
with system.requirement("REQ-SYS-001", "System requirements."):
    power.requirement("REQ-PWR-001", "Power requirement.", verified_by=[vq.Ref("?verify_power")])
    thermal.requirement("REQ-TH-001", "Thermal requirement.", verified_by=[vq.Ref("?verify_temp")])
```

### Requirement Statuses

| Status | Symbol | Meaning |
|--------|--------|---------|
| VERIFIED | ✓ | Has direct verifications, all passed |
| SATISFIED | ○ | No direct verifications, all children pass |
| FAILED | ✗ | Some verification or child failed |
| NOT_VERIFIED | ? | Leaf requirement with no verifications |

### Cross-Scope Requirements

Add children to existing requirements from different scopes:

```python
# Fetch existing requirement and add children
with system.fetch_requirement("REQ-SYS-001"):
    power.requirement("REQ-PWR-002", "Another power requirement.", verified_by=[vq.Ref("?verify")])
```

You can also reference verifications from other scopes:

```python
# Reference a verification in another scope
system.requirement(
    "REQ-SYS-002",
    "Cross-scope requirement.",
    verified_by=[vq.Ref("?verify_power", scope="Power")],
)
```

### Requirement Dependencies

Declare that one requirement depends on another:

```python
req_parent = power.requirement("REQ-PWR-001", "Parent requirement.")

with power.requirement("REQ-PWR-002", "Child requirement."):
    vq.depends(req_parent)  # If REQ-PWR-001 fails, REQ-PWR-002 also fails
```

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

## Input Provenance

Input values rarely come from nowhere: a capacity comes from a datasheet, a margin from a review decision. veriq lets you record this **per input field**, in two complementary places. veriq does not interpret the contents; it only stores them and makes them retrievable per leaf path.

### Field definition metadata (`vq.Meta`)

Properties of the field itself (unit, governing document, owner) belong next to the field definition:

```python
from typing import Annotated


class Battery(BaseModel):
    capacity: Annotated[float, vq.Meta({"unit": "Wh", "source_doc": "EPS-ICD-001"})]
    min_capacity: float


class PowerModel(BaseModel):
    battery: Annotated[Battery, vq.Meta(owner="power-team")]  # inherited by battery.*
```

The resolved metadata appears as `NodeSpec.field_metadata` on the corresponding MODEL leaf nodes of the dependency graph. It is kept separate from `@scope.root_model(metadata=...)`, which is shared by all leaves of the root model.

### Value provenance (`provenance` table)

The rationale for a *concrete value* belongs next to the value, in the reserved `provenance` table of the input TOML file. Each entry is keyed by the path of the input it describes, in the same syntax as `vq.Ref`, and holds the metadata for that path:

```toml
[Power.model.battery]
capacity = 100.0
min_capacity = 50.0

[Power.provenance."$.battery"]
source = "vendor datasheet rev.C"      # applies to capacity and min_capacity

[Power.provenance."$.battery.capacity"]
rationale = "20% EOL degradation applied"   # adds to the entry above
```

Short entries can also be written inline, in one table:

```toml
[Power.provenance]
"$" = { baseline = "PDR-2026-03" }                    # the whole root model
"$.power_consumption[safe]" = { rationale = "heaters off" }   # one Table entry
```

Rules:

- A key is the path of a leaf, a nested model, a whole `Table`, or `"$"` for the root model. Table entries use brackets (`"$.power[safe]"`, `"$.matrix[launch,nominal]"`). The quotes are required by TOML.
- Metadata is free-form: any key, with a scalar, array or table as its value. Because paths and metadata keys are kept apart, a metadata key may have the same name as a model field.
- Only the keys of the `provenance` table are paths. A table below an entry is metadata of that entry, never a sub-path, so `"$.battery" = { capacity = { ... } }` describes `$.battery`.
- Metadata is inherited along the path from the root model to each leaf. The nearest path wins per key; a table value is replaced as a whole, not merged.
- A key that is not a path of the root model is an error, so typos are never silently dropped. The error names the entries of the `Table` the key points into, or else the closest existing path.
- `veriq update` never generates or removes `provenance` tables; `veriq schema` describes them in the JSON schema, so an editor can complete the path keys.

Load provenance separately from model data:

```python
provenance = vq.load_provenance_from_toml(project, "input.toml")
# {ProjectPath(Power::$.battery.capacity): {"source": "vendor datasheet rev.C", "rationale": "..."}, ...}
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
) -> ThermalOutput: ...
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

### Upstream Subgraph

Internally the graph has one node per *output leaf*, so a calculation returning a model with three fields is three nodes. For questions like "what does this verification ultimately depend on?" that granularity double-counts. `vq.upstream_subgraph()` reduces the graph to **definition granularity** (one node per root model, calculation or verification) while keeping the parameter-level wiring:

```python
sub = vq.upstream_subgraph(project, "Power::?verify_margin")

sub.nodes  # {DefinitionId: DefinitionNode}, target included, each definition once
sub.data_edges  # producer -> consumer, with the parameter bindings of the consumer
sub.assume_edges  # @vq.assume references, kept separate from data flow
sub.inputs_of(node_id)  # which parameter reads which path, and the leaf paths it expands to
sub.input_leaves()  # root-model leaves at the start of every chain (join key for provenance)
sub.topological_order()  # producers before consumers (data edges only)

# Set-style aggregation over definitions, no double counting:
total = sum(n.user_metadata.get("compute_time_s", 0.0) for n in sub.nodes.values())
```

`follow_assumes=True` (default) also walks through assumed verifications, so the result contains the full assumption closure. With `follow_assumes=False` the assume edges and the assumed verifications are present but their own upstream is not. Assume edges are premises, not data flow: an assumed verification may itself read the assuming calculation's output, so they never take part in ordering.

A definition without any leaf, such as an empty root model that another scope reads as a whole, is still a node; its `outputs` are empty. An unknown target raises `vq.DefinitionNotFoundError` (a `KeyError`).

### Propagating Values Along the Graph

Some aggregations depend on the *shape* of the DAG, not only on the node set. The parallel makespan of computation time, for example, is the longest path: a node can start only when all its inputs are ready. `propagate()` evaluates such recurrences in topological order:

```python
# value(node) = own(node) + combine(value(p) for p in predecessors(node))
parallel = sub.propagate("compute_time_s", combine=max, default=0.0)  # critical path, at the target
per_node = sub.propagate_all("compute_time_s", combine=max)  # {DefinitionId: value}
```

`own(node)` is `user_metadata[key]`, or `default` when the key is absent. Only data edges propagate: an assumed verification is a premise rather than an input, so it is a node of the subgraph (and counts in set-style totals) but does not feed the recurrence.

`propagate` is a recurrence along paths, not a reduction over nodes: with `combine=sum` a dependency shared by several paths is counted once per path. For a sequential total, sum over `sub.nodes` as shown above.

See [Metadata & Provenance](metadata.md) for a complete worked example.

## Execution Flow

When you run `veriq calc`:

1. **Load** - Parse TOML input into Pydantic models
2. **Build** - Construct dependency graph from references
3. **Sort** - Topologically sort calculations
4. **Execute** - Run calculations in order
5. **Verify** - Run verifications (if `--verify`)
6. **Export** - Write results to output TOML
