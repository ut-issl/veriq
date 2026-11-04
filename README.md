# veriq

[![PyPI](https://img.shields.io/pypi/v/veriq)](https://pypi.org/project/veriq/)
![PyPI - License](https://img.shields.io/pypi/l/veriq)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/veriq)
[![Test Status](https://github.com/ut-issl/veriq/actions/workflows/ci.yaml/badge.svg)](https://github.com/ut-issl/veriq/actions)
[![codecov](https://codecov.io/gh/ut-issl/veriq/graph/badge.svg?token=to2H6ZCztP)](https://codecov.io/gh/ut-issl/veriq)
[![Documentation](https://img.shields.io/badge/docs-veriq-blue)](https://www.space.t.u-tokyo.ac.jp/veriq/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> [!WARNING]
> This project is in early development. The API may change in future releases.

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

Create an input file `input.toml`:

```toml
[Power.model]
battery_capacity = 150.0
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

## License

MIT License

## Acknowledgement

veriq originated in the `shunichironomura/veriq` repository, and its early development up to version v0.0.1 was supported by ArkEdge Space Inc.
