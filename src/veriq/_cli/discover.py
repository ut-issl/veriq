"""Backward-compatible re-export; the implementation lives in `veriq._discover`."""

from veriq._discover import (
    ModuleData,
    get_module_data_from_path,
    load_project,
    load_project_from_module_path,
    load_project_from_script,
)

__all__ = [
    "ModuleData",
    "get_module_data_from_path",
    "load_project",
    "load_project_from_module_path",
    "load_project_from_script",
]
