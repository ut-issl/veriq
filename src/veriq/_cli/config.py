"""Backward-compatible re-export; the implementation lives in `veriq._config`."""

from veriq._config import (
    ConfigError,
    ModuleSource,
    ProjectSource,
    ScriptSource,
    VeriqConfig,
    find_pyproject_toml,
    get_config,
    load_config,
)

__all__ = [
    "ConfigError",
    "ModuleSource",
    "ProjectSource",
    "ScriptSource",
    "VeriqConfig",
    "find_pyproject_toml",
    "get_config",
    "load_config",
]
