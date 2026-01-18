---
icon: material/school
---

# Tutorial Overview

This tutorial teaches you veriq step by step. Each step builds on the previous one, introducing new concepts incrementally.

## What You'll Build

By the end of this tutorial, you'll have built a satellite power-thermal analysis system that:

- Defines design parameters for power and thermal subsystems
- Calculates derived values like heat generation and temperature
- Verifies that temperatures stay within limits
- Uses tables for multi-mode analysis

## Tutorial Steps

| Step | Topic | What You'll Learn |
|------|-------|-------------------|
| [Step 1](step1-first-project.md) | Your First Project | Create a project, define a scope, and add a model |
| [Step 2](step2-calculations.md) | Adding Calculations | Define calculations that derive values from your model |
| [Step 3](step3-cross-scope.md) | Cross-Scope References | Connect multiple scopes with dependencies |
| [Step 4](step4-verifications.md) | Verifications | Add requirement checks to your calculations |
| [Step 5](step5-tables.md) | Using Tables | Handle multi-dimensional data with enum-indexed tables |

## Running the Examples

All tutorial examples are available in the `examples/tutorial/` directory of the veriq repository. You can run them directly:

```bash
# Clone the repository
git clone https://github.com/ut-issl/veriq.git
cd veriq

# Install dependencies
uv sync

# Run a tutorial example
uv run veriq check examples/tutorial/step1.py
```

## Prerequisites

Before starting, make sure you have:

- [Installed veriq](../installation.md)
- Basic familiarity with Python
- Basic familiarity with [Pydantic](https://docs.pydantic.dev/) (helpful but not required)

Ready? Let's start with [Step 1: Your First Project](step1-first-project.md).
