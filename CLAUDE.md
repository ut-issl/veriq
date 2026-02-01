# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**veriq** is a Python library for requirements verification and design calculation management in engineering projects. It enables engineers to define hierarchical system requirements, associate verification functions with requirements, model design specifications using Pydantic BaseModels, and calculate derived values automatically through a dependency graph.

**Spreadsheet Analogy:**

- Project = Workbook
- Scope = Sheet (logical grouping like "Power", "Thermal")
- Model = Input cells (design parameters)
- Calculation = Formula cells (computed values)
- Verification = Conditional formatting (requirement checks)

**Current Version:** 0.1.4 (Alpha - under active development)

## Development Commands

### Testing

```bash
# Run all tests with coverage
just test

# Run a single test file
uv run pytest tests/test_table.py

# Run a specific test
uv run pytest tests/test_table.py::test_function_name -v
```

### Linting and Type Checking

```bash
# Run all checks (ruff, ty, license check)
just lint

# Run individual checks
just ruff          # Ruff linter
just typecheck     # Run ty
just license       # Check dependency licenses
```

### Build and Install

```bash
# Install in development mode with all dev dependencies
uv sync

# Build the package
uv build
```

### CLI Usage

```bash
# Check project structure validity
veriq check examples/dummysat.py

# Run calculations with verification
veriq calc examples/dummysat.py -i input.toml -o output.toml --verify

# Use module path instead of script path
veriq calc my_package.module:project -i input.toml -o output.toml
```

## High-Level Architecture

### Core Design Patterns

#### 1. Decorator Pattern for Registration

- `@scope.root_model()` - Register Pydantic model as scope input
- `@scope.calculation()` - Convert functions into Calculation objects
- `@scope.verification()` - Convert functions into Verification objects
- Decorators automatically extract dependencies from function signatures

#### 2. Context Manager Pattern for Hierarchy

- `Scope` and `Requirement` use context managers for hierarchical structure
- Automatic registration when entering contexts
- Example: `with scope: [define contents]`

#### 3. Dependency Injection via References

- Function parameters use `Annotated[Type, vq.Ref(path)]` to declare dependencies
- Reference syntax:
  - `"$"` - Root model of current scope
  - `"$.field"` - Nested field access
  - `"@calculation_name"` - Reference calculation output
  - `"$.table[key]"` - Table indexing
  - `scope="ScopeName"` - Cross-scope reference
- Automatic dependency resolution during evaluation

#### 4. Lazy Evaluation with Dependency Graph

- Dependency graph built at check time via `build_dependencies_graph()`
- Evaluation deferred until `evaluate_project()` call
- Topological sort ensures correct evaluation order
- Results stored in `dict[ProjectPath, Any]`

### Key Components and Their Roles

**Core Data Structures** (in `_models.py`):

- `Project` - Top-level container, manages scopes
- `Scope` - Subsystem grouping, contains models/calculations/verifications
- `Calculation` - Computed value function with dependency tracking
- `Verification` - Requirement check function returning bool
- `Requirement` - Engineering requirement with hierarchical decomposition
- `Ref` - Data reference (path string + optional scope)
- `Table` - Enum-indexed mapping (single or multi-dimensional)

**Evaluation Pipeline**:

1. Load TOML → `load_model_data_from_toml()` → dict[scope_name, BaseModel]
2. Build dependency graph → `build_dependencies_graph()` → DirectedGraph
3. Topological sort → `topological_sort()` → evaluation order
4. Evaluate in order:
   - Calculations: resolve inputs, call func, store leaf outputs
   - Verifications: resolve inputs, call func, store bool result
5. Export → `export_to_toml()` → Output TOML

**Path System** (in `_path.py`):

- `ProjectPath` = tuple of (scope_name, path_within_scope)
- Paths have "root" + "parts" structure
- Parts are `AttributePart` (`.field`) or `ItemPart` (`[key]`)
- Three path types: `ModelPath`, `CalcPath`, `VerificationPath`

**Reference Resolution**:

1. Parse `Ref(path, scope=...)` string into `ProjectPath`
2. At evaluation time, look up values from results dict using leaf paths
3. If reference points to Pydantic model, reconstruct full object from leaf values
4. Pass as keyword argument to calculation/verification function

### Code Organization

```
src/veriq/
├── __init__.py          # Public API exports (Project, Scope, Ref, Table, etc.)
├── __main__.py          # CLI entry point
├── _models.py           # Core: Project, Scope, Calculation, Verification, Requirement
├── _decorators.py       # @assume decorator for assumed verifications
├── _build.py            # Dependency graph construction
├── _eval.py             # Project evaluation (main computation engine)
├── _io.py               # TOML load/export
├── _path.py             # Path parsing and navigation
├── _table.py            # Table[K, V] enum-indexed mapping type
├── _relations.py        # depends() for requirement relationships
├── _utils.py            # topological_sort() for DAG ordering
├── _exceptions.py       # Custom exceptions
├── _cli/
│   ├── main.py          # typer CLI commands (calc, check)
│   └── discover.py      # Module/script discovery utilities
└── py.typed             # PEP 561 marker for type checking
```

## Important Conventions

### Reference Syntax Patterns

When writing calculations or verifications:

```python
# Reference current scope's model field
Annotated[float, vq.Ref("$.battery_capacity")]

# Reference nested field
Annotated[float, vq.Ref("$.design.mass")]

# Reference calculation output
Annotated[float, vq.Ref("@calculate_power.max_power")]

# Cross-scope reference (must declare imports=["ScopeName"])
Annotated[float, vq.Ref("$.field", scope="Power")]
Annotated[float, vq.Ref("@calc.output", scope="Thermal")]

# Table indexing
Annotated[float, vq.Ref("$.power_table[nominal]")]
Annotated[float, vq.Ref("$.matrix[launch,nominal]")]
```

### Code Style Rules

All code follows strict type checking and linting:

- **Line length:** 120 characters
- **Type checking:** `ty`
- **Linting:** Ruff with `select = ["ALL"]` (many rules enabled)
- **Dataclasses:** Use `@dataclass(slots=True)` for efficiency
- **Frozen types:** Use frozen dataclasses for immutable types

Key ignored rules (see `pyproject.toml` for full list):

- `PLR2004` - Magic numbers allowed
- `S101` - Assert statements allowed
- `D203/D213` - Specific docstring formats
- `ANN401` - `typing.Any` allowed
- `TD001/TD002/TD003` - TODO comment requirements relaxed

Per-file ignores:

- `tests/\*\*: Docstrings, INP001, ANN201 ignored
- `examples/\*\*: Docstrings, print statements, magic numbers allowed

### Testing Patterns

Pytest options are already configured in `pyproject.toml`, so you can just run:

```bash
uv run pytest
```

Or with coverage:

```bash
just test
```

Common test pattern:

1. Create Pydantic models for test data
2. Define Project, Scope, Calculations, Verifications
3. Use `evaluate_project()` to run the pipeline
4. Assert on the results dict

Example test files:

- `test_table.py` - Table functionality (13KB)
- `test_table_pydantic.py` - Pydantic integration (6.2KB)
- `test_models.py` - Core model tests
- `test_path.py` - Path parsing tests

## Known Limitations

1. **One Instance Per Model Class**
   - Cannot have multiple instances of same Pydantic model in a scope
   - Uses `model.__name__` as unique identifier (causes key collision)
   - Workaround: Create separate scopes or nest models in parent

2. **No Calculation Caching**
   - If multiple verifications depend on same calculation, it re-evaluates
   - Could be inefficient for expensive operations

3. **Limited Verification Result Details**
   - Returns only boolean, not detailed failure info
   - No indication of which requirements failed or why

4. **Partial Requirement Traceability**
   - Requirement decomposition implemented
   - Requirement-verification mapping partial
   - Verification index shown in command output

## Key Files for Common Tasks

**Adding a new feature:**

1. Modify `_models.py` for new core types
2. Update `__init__.py` to export new public API
3. Add tests in `tests/test_*.py`
4. Update examples if needed

**Fixing evaluation bugs:**

- Check `_eval.py` (evaluation logic)
- Check `_build.py` (dependency graph construction)
- Check `_utils.py` (topological sort)

**CLI changes:**

- Modify `_cli/main.py` (typer commands)
- Update `_cli/discover.py` for module discovery

**Path/reference bugs:**

- Check `_path.py` (path parsing and navigation)
- Check how `Ref` objects are resolved in `_eval.py`

**TOML import/export:**

- Modify `_io.py` for serialization logic

## Example Project Structure

The canonical example is `examples/dummysat.py` which demonstrates:

- Multi-scope projects (Power, Thermal subsystems)
- Cross-scope references with `imports=["ScopeName"]`
- Table usage for multi-dimensional data (indexed by enums)
- Requirement decomposition and verification
- Complete workflow from model → calculation → verification

To understand any feature, read the example usage in `dummysat.py` first, then trace back to the implementation.
