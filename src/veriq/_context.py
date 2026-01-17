"""Context variables for veriq.

This module contains context variables used across the library.
It is kept separate to avoid circular imports.
"""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path  # noqa: TC003 - Used at runtime for ContextVar type

# Base directory for resolving relative paths in input data (e.g., FileRef paths).
# Typically set to the directory containing the input TOML file.
_input_base_dir_var: ContextVar[Path | None] = ContextVar("input_base_dir", default=None)


def get_input_base_dir() -> Path | None:
    """Get the current input base directory from context.

    Returns None if no base directory is set.
    """
    return _input_base_dir_var.get()


def set_input_base_dir(path: Path | None) -> object:
    """Set the input base directory in context.

    Returns a token that can be used to reset the value.
    """
    return _input_base_dir_var.set(path)


def reset_input_base_dir(token: object) -> None:
    """Reset the input base directory using a token from set_input_base_dir."""
    _input_base_dir_var.reset(token)  # type: ignore[arg-type]
