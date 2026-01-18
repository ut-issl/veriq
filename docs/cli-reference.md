---
icon: material/console
---

# CLI Reference

veriq provides a command-line interface for checking projects and running calculations.

## Global Options

```bash
veriq [OPTIONS] COMMAND
```

| Option | Description |
|--------|-------------|
| `--verbose` | Show detailed debug information |
| `--version` | Show version and exit |
| `--help` | Show help and exit |

## Commands

### `veriq check`

Validate project structure without running calculations.

```bash
veriq check PROJECT_PATH [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PROJECT_PATH` | Path to Python script or module path |

**Options:**

| Option | Description |
|--------|-------------|
| `--project NAME` | Name of the project variable (default: auto-detect) |

**Examples:**

```bash
# Check a Python script
veriq check my_project.py

# Check with explicit project variable
veriq check my_project.py --project my_project

# Check a module path
veriq check my_package.module:project

# Verbose output
veriq --verbose check my_project.py
```

**Output:**

```
Loading project from script: my_project.py
Project: MySatellite

Validating dependencies...

╭───────────────────────── Project: MySatellite ─────────────────────────╮
│ ┏━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓                             │
│ ┃ Scope   ┃ Calculations ┃ Verifications ┃                             │
│ ┡━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩                             │
│ │ Power   │            2 │             1 │                             │
│ │ Thermal │            1 │             1 │                             │
│ └─────────┴──────────────┴───────────────┘                             │
╰─────────────────────────────────────────────────────── 2 scopes ───────╯

✓ Project is valid
```

### `veriq calc`

Run calculations and optionally verify requirements.

```bash
veriq calc PROJECT_PATH -i INPUT -o OUTPUT [OPTIONS]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `PROJECT_PATH` | Path to Python script or module path |

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

# Module path
veriq calc my_package.module:project -i input.toml -o output.toml

# Verbose output
veriq --verbose calc my_project.py -i input.toml -o output.toml
```

**Output (without --verify):**

```
Loading project from script: my_project.py
Project: MySatellite

Loading input from: input.toml
Evaluating project...
Exporting results to: output.toml

✓ Calculation complete
```

**Output (with --verify, all pass):**

```
Loading project from script: my_project.py
Project: MySatellite

Loading input from: input.toml
Evaluating project...

╭──────────────────── Verification Results ────────────────────╮
│  Verification                        Result                  │
│  Power::verify_power_margin          ✓ PASS                  │
│  Thermal::verify_temperature         ✓ PASS                  │
╰───────────────────────────────────────────────────────────────╯

Exporting results to: output.toml

✓ Calculation complete
```

**Output (with --verify, some fail):**

```
╭──────────────────── Verification Results ────────────────────╮
│  Verification                        Result                  │
│  Power::verify_power_margin          ✓ PASS                  │
│  Thermal::verify_temperature         ✗ FAIL                  │
╰───────────────────────────────────────────────────────────────╯

✗ Verification failed
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (all verifications passed if `--verify` used) |
| `1` | Failure (verification failed or error occurred) |

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
