---
icon: material/console
---

# CLI Reference

veriq provides a command-line interface for managing projects, running calculations, and working with input files.

## Global Options

```bash
veriq [OPTIONS] COMMAND
```

| Option | Description |
|--------|-------------|
| `--verbose` / `--no-verbose` | Enable verbose output |
| `--version` | Show version and exit |
| `--install-completion` | Install shell completion |
| `--show-completion` | Show shell completion script |
| `--help` | Show help and exit |

## Commands Overview

| Command | Description |
|---------|-------------|
| `check` | Validate project structure |
| `calc` | Run calculations and verifications |
| `schema` | Generate JSON schema for input |
| `init` | Generate sample input TOML file |
| `update` | Update existing input with new schema |
| `diff` | Compare two TOML files |
| `edit` | Edit input with interactive TUI |
| `trace` | Display requirement-verification traceability |
| `scopes` | List all scopes in the project |
| `list` | List nodes in the dependency graph |
| `show` | View detailed information about a node |
| `tree` | Show dependency tree for a node |

---

## `veriq check`

Validate project structure without running calculations.

```bash
veriq check PROJECT_PATH [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PROJECT_PATH` | Path to Python script or module path (required) |

**Options:**

| Option | Description |
|--------|-------------|
| `--project NAME` | Name of the project variable (for script paths) |

**Examples:**

```bash
# Check a Python script
veriq check my_project.py

# Check with explicit project variable
veriq check my_project.py --project my_project

# Check a module path
veriq check my_package.module:project
```

---

## `veriq calc`

Run calculations and optionally verify requirements.

```bash
veriq calc PROJECT_PATH -i INPUT -o OUTPUT [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PROJECT_PATH` | Path to Python script or module path (required) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--input PATH` | `-i` | Path to input TOML file (required) |
| `--output PATH` | `-o` | Path to output TOML file (required) |
| `--verify` | | Run verifications and report results |
| `--project NAME` | | Name of the project variable |

**Examples:**

```bash
# Basic calculation
veriq calc my_project.py -i input.toml -o output.toml

# With verification
veriq calc my_project.py -i input.toml -o output.toml --verify

# Using module path
veriq calc my_package.module:project -i input.toml -o output.toml
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Success (all verifications passed if `--verify` used) |
| `1` | Failure (verification failed or error occurred) |

---

## `veriq schema`

Generate JSON schema for the project input model.

```bash
veriq schema PROJECT_PATH -o OUTPUT [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PROJECT_PATH` | Path to Python script or module path (required) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Path to output JSON schema file (required) |
| `--project NAME` | | Name of the project variable |
| `--indent N` | | JSON indentation spaces (default: 2) |

**Examples:**

```bash
# Generate schema
veriq schema my_project.py -o schema.json

# With custom indentation
veriq schema my_project.py -o schema.json --indent 4
```

The generated schema can be used for:

- IDE autocompletion in TOML files
- Input validation
- Documentation generation

---

## `veriq init`

Generate a sample input TOML file with default values.

```bash
veriq init PROJECT_PATH -o OUTPUT [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PROJECT_PATH` | Path to Python script or module path (required) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Path to output TOML file (required) |
| `--project NAME` | | Name of the project variable |

**Examples:**

```bash
# Generate sample input file
veriq init my_project.py -o input.toml
```

This creates a TOML file with all required fields populated with default values, which you can then edit with your actual data.

---

## `veriq update`

Update an existing input TOML file with new schema defaults.

```bash
veriq update PROJECT_PATH -i INPUT [OPTIONS]
```

This command intelligently merges your existing input file with the current project schema:

- Preserves all existing values
- Adds new fields with default values
- Warns about removed fields

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PROJECT_PATH` | Path to Python script or module path (required) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--input PATH` | `-i` | Path to existing input TOML file (required) |
| `--output PATH` | `-o` | Path to output TOML file (defaults to input file) |
| `--project NAME` | | Name of the project variable |
| `--dry-run` | | Preview changes without writing to file |

**Examples:**

```bash
# Update input file in place
veriq update my_project.py -i input.toml

# Update to a new file
veriq update my_project.py -i input.toml -o updated_input.toml

# Preview changes without writing
veriq update my_project.py -i input.toml --dry-run
```

---

## `veriq diff`

Compare two TOML files and check if they are identical.

```bash
veriq diff FILE1 FILE2
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `FILE1` | Path to the first TOML file (required) |
| `FILE2` | Path to the second TOML file (required) |

**Examples:**

```bash
# Compare two output files
veriq diff output_v1.toml output_v2.toml

# Compare input and output
veriq diff input.toml output.toml
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Files are identical |
| `1` | Files differ |

---

## `veriq edit`

Edit input TOML file with an interactive TUI (terminal user interface).

```bash
veriq edit PROJECT_PATH -i INPUT [OPTIONS]
```

Opens a spreadsheet-like interface for editing Table fields in the input file. Supports 2D and 3D tables with dimension slicing.

![veriq edit TUI](https://github.com/user-attachments/assets/5218825e-9046-44fa-8f98-e67250872030)

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PROJECT_PATH` | Path to Python script or module path (required) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--input PATH` | `-i` | Path to input TOML file to edit (required) |
| `--project NAME` | | Name of the project variable |

**Controls:**

| Key | Action |
|-----|--------|
| Arrow keys | Navigate cells |
| Enter | Edit selected cell |
| Tab | Switch to next table |
| S | Save changes |
| Q | Quit (prompts to save if unsaved changes) |

**Examples:**

```bash
# Edit input file interactively
veriq edit my_project.py -i input.toml
```

---

## `veriq trace`

Display requirement-verification traceability.

```bash
veriq trace [PATH] [OPTIONS]
```

Shows the requirement tree with verification status for each requirement. This is useful for tracking which requirements are verified, satisfied, or failing.

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PATH` | Path to Python script or module path (optional if configured in pyproject.toml) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--input PATH` | `-i` | Path to input TOML file (enables verification evaluation) |
| `--project NAME` | | Name of the project variable |

**Examples:**

```bash
# Show requirement tree with pass/fail status
veriq trace examples/dummysat.py -i examples/dummysat.in.toml
```

**Example output:**

```
 Requirement          Description                              Status          Verifications
 REQ-SYS-001          System-level requirement (status         ✗ FAILED        -
                      propagates fro...
 ├── REQ-SYS-002      Thermal subsystem requirements.          ✗ FAILED        -
 │   └── REQ-TH-001   Solar panel temperature must be within   ✗ FAILED        ✗ Power::?solar_panel_max_temperature
                      limits.
 ├── REQ-SYS-003      Power subsystem requirements.            ○ SATISFIED     -
 │   └── REQ-PWR-001  Battery and power budget requirements.   ✓ VERIFIED      ✓ Power::?verify_battery
 │                                                                             ✓ Power::?verify_power_budget[nominal]
 │                                                                             ✓ Power::?verify_power_budget[safe]
 │                                                                             ✓ Power::?verify_power_budget[mission]
 └── REQ-SYS-004      Future requirement (not yet verified).   ? NOT_VERIFIED  -

╭───────────────────────────────────────────────────── Summary ──────────────────────────────────────────────────────╮
│ Total requirements: 6                                                                                              │
│ ✓ Verified: 1                                                                                                      │
│ ○ Satisfied: 1                                                                                                     │
│ ✗ Failed: 3                                                                                                        │
│ ? Not verified: 1                                                                                                  │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | All requirements pass (or only expected failures) |
| `1` | Some requirements failed unexpectedly |

---

## `veriq scopes`

List all scopes in the project with summary information.

```bash
veriq scopes [PATH] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PATH` | Path to Python script or module path (optional if configured in pyproject.toml) |

**Options:**

| Option | Description |
|--------|-------------|
| `--project NAME` | Name of the project variable |
| `--json` | Output as JSON |

**Examples:**

```bash
# List all scopes
veriq scopes examples/dummysat.py
```

**Example output:**

```
┏━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Scope   ┃ Models ┃ Calcs ┃ Verifications ┃
┡━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━┩
│ System  │      0 │     0 │             1 │
│ AOCS    │      0 │     0 │             0 │
│ Power   │     17 │     1 │             6 │
│ Thermal │      0 │     1 │             0 │
│ RWA     │     25 │     0 │             4 │
└─────────┴────────┴───────┴───────────────┘
```

---

## `veriq list`

List nodes in the dependency graph with optional filtering.

```bash
veriq list [PATH] [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PATH` | Path to Python script or module path (optional if configured in pyproject.toml) |

**Options:**

| Option | Description |
|--------|-------------|
| `--project NAME` | Name of the project variable |
| `--kind KIND` | Filter by kind: `model`, `calc`, `verification` (repeatable) |
| `--scope NAME` | Filter by scope name (repeatable) |
| `--leaves` | Show only leaf nodes (nothing depends on them) |
| `--json` | Output as JSON |

**Examples:**

```bash
# List only calculations
veriq list examples/dummysat.py --kind calc
```

**Example output:**

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━┓
┃ Path                                                        ┃ Kind        ┃ Deps ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━┩
│ Power::@calculate_solar_panel_heat.heat_generation          │ CALCULATION │    5 │
│ Thermal::@calculate_temperature.solar_panel_temperature_max │ CALCULATION │    2 │
└─────────────────────────────────────────────────────────────┴─────────────┴──────┘

Total: 2 nodes
```

You can also combine filters:

```bash
# List nodes in a specific scope
veriq list examples/dummysat.py --scope Power

# List leaf nodes only (nothing depends on them)
veriq list examples/dummysat.py --leaves
```

---

## `veriq show`

View detailed information about a specific node.

```bash
veriq show NODE_PATH [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `NODE_PATH` | Node path in format `Scope::path` (required) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--path PATH` | `-p` | Path to Python script or module path |
| `--project NAME` | | Name of the project variable |
| `--json` | | Output as JSON |

**Node path format:**

- Model fields: `Scope::$.field` or `Scope::$.nested.field`
- Calculations: `Scope::@calculation_name.output_field`
- Verifications: `Scope::?verification_name`

**Examples:**

```bash
# Show details of a calculation output
veriq show "Power::@calculate_solar_panel_heat.heat_generation" -p examples/dummysat.py
```

**Example output:**

```
Node: Power::@calculate_solar_panel_heat.heat_generation

Kind:         CALCULATION
Scope:        Power
Output Type:  float

Dependencies (5 direct):
  Power::$.design.config_file
  Power::$.design.solar_panel.area
  Power::$.design.solar_panel.efficiency
  Power::$.design.solar_panel.max_temperature
  Power::$.design.solar_panel.thermal_coefficient

Dependents (1 direct):
  Thermal::@calculate_temperature.solar_panel_temperature_max

Metadata:
  root_output_type: SolarPanelResult
  assumed_verification_paths: [Power::?solar_panel_max_temperature]
```

---

## `veriq tree`

Show dependency tree for a node.

```bash
veriq tree NODE_PATH [OPTIONS]
```

By default, shows what the node depends on. Use `--invert` to show what depends on the node (impact analysis).

**Arguments:**

| Argument | Description |
|----------|-------------|
| `NODE_PATH` | Node path in format `Scope::path` (required) |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--path PATH` | `-p` | Path to Python script or module path |
| `--project NAME` | | Name of the project variable |
| `--invert` | `-i` | Show reverse dependencies (what depends on this node) |
| `--depth N` | | Maximum tree depth (default: unlimited) |
| `--json` | | Output as JSON |

**Examples:**

```bash
# Show what a calculation depends on
veriq tree "Power::@calculate_solar_panel_heat.heat_generation" -p examples/dummysat.py
```

**Example output:**

```
Power::@calculate_solar_panel_heat.heat_generation
├── Power::$.design.config_file
├── Power::$.design.solar_panel.area
├── Power::$.design.solar_panel.efficiency
├── Power::$.design.solar_panel.max_temperature
└── Power::$.design.solar_panel.thermal_coefficient
```

Use `--invert` for impact analysis (what depends on this node):

```bash
# Show what depends on a model field
veriq tree "Power::$.design.solar_panel.area" -p examples/dummysat.py --invert
```

**Example output (inverted):**

```
Power::$.design.solar_panel.area
├── Power::?solar_panel_max_temperature
├── Power::@calculate_solar_panel_heat.heat_generation
│   └── Thermal::@calculate_temperature.solar_panel_temperature_max
└── System::?power_thermal_compatibility
```

---

## Configuration in pyproject.toml

You can configure default project, input, and output paths in your `pyproject.toml` file. This allows you to omit these arguments when running CLI commands.

```toml
[tool.veriq]
# Option 1: Module path format (for installed packages)
project = "my_package.satellite:project"

# Option 2: Script path format (variable name auto-inferred)
project = { script = "examples/dummysat.py" }

# Option 3: Script path with explicit variable name
project = { script = "examples/dummysat.py", name = "project" }

# Optional: Default input/output TOML files
input = "data/input.toml"
output = "data/output.toml"
```

**Notes:**

- All paths are relative to the project root (directory containing `pyproject.toml`)
- CLI arguments always override config defaults
- Invalid config fails immediately with a clear error message

**Examples with config:**

```bash
# With [tool.veriq] configured, project argument is optional
veriq calc                              # Uses all defaults from config
veriq calc -o custom_output.toml        # Partial override
veriq calc other.py -i in.toml -o out.toml  # CLI args override config

# trace command also uses config defaults
veriq trace                             # Uses configured project and input
```

---

## Project Path Formats

veriq supports two formats for specifying projects:

### Script Path

```bash
veriq check path/to/my_project.py
```

veriq will:

1. Load the Python script
2. Find a `Project` instance (or use `--project` to specify)

### Module Path

```bash
veriq check my_package.module:project_variable
```

Format: `module.path:variable_name`

veriq will:

1. Import the module
2. Get the specified variable

---

## Input/Output File Format

### Input TOML

```toml
[ScopeName.model]
field = value
nested.field = value

[ScopeName.model.table_field]
key1 = value1
key2 = value2
```

### Output TOML

```toml
# Input values (preserved)
[ScopeName.model]
field = value

# Calculation results
[ScopeName.calc.calculation_name]
output_field = computed_value

# Verification results (if --verify)
[ScopeName.verification]
verification_name = true
```
