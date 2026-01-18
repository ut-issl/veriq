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
