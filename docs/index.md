---
icon: material/home
---

# Welcome to veriq

veriq is a Python library for requirements verification and design calculation management in engineering projects. Think of it as a smart spreadsheet that tracks dependencies between calculations and automatically verifies that requirements are met.

## What Does veriq Do?

When you define your engineering project with veriq, it:

1. **Organizes your design parameters** - Define input data using Pydantic models
2. **Tracks calculation dependencies** - Automatically resolves the order of calculations
3. **Verifies requirements** - Checks that your design meets all specified requirements
4. **Exports results** - Saves all inputs, calculations, and verification results to TOML files

## Quick Example

Define your project in Python:

```python
import veriq as vq
from pydantic import BaseModel
from typing import Annotated

project = vq.Project("MySatellite")
power = vq.Scope("Power")
project.add_scope(power)

@power.root_model()
class PowerModel(BaseModel):
    battery_capacity: float  # in Watt-hours

@power.verification()
def verify_capacity(
    capacity: Annotated[float, vq.Ref("$.battery_capacity")],
) -> bool:
    return capacity >= 100.0  # Minimum 100 Wh
```

Run verification:

```bash
veriq calc my_project.py -i input.toml -o output.toml --verify
```

## Why Use veriq?

- **Type Safety** - Leverage Pydantic for validated, typed design parameters
- **Dependency Tracking** - Automatic resolution of calculation order
- **Requirement Traceability** - Link verifications to engineering requirements
- **Reproducibility** - TOML-based input/output for version control

## Getting Started

<div class="grid cards" markdown>

- :material-download:{ .lg .middle } **Installation**

    ---

    Install veriq using pip or uv.

    [:octicons-arrow-right-24: Install veriq](installation.md)

- :material-rocket-launch:{ .lg .middle } **Tutorial**

    ---

    Learn veriq step by step with hands-on examples.

    [:octicons-arrow-right-24: Start the tutorial](tutorial/index.md)

- :material-book-open-variant:{ .lg .middle } **Concepts**

    ---

    Understand the core concepts behind veriq.

    [:octicons-arrow-right-24: Core concepts](concepts.md)

- :material-console:{ .lg .middle } **CLI Reference**

    ---

    Complete command-line interface documentation.

    [:octicons-arrow-right-24: CLI commands](cli-reference.md)

</div>
