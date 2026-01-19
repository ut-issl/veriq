"""Utilities to discover veriq projects and modules.

This module was adapted from `fastapi_cli.discover` of package `fastapi-cli` version 0.0.8 (77e6d1f).
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from veriq._models import Project

    from .config import ProjectSource


@dataclass
class ModuleData:
    """Module data for a Python module."""

    module_import_str: str
    extra_sys_path: Path
    module_paths: list[Path]


def get_module_data_from_path(path: Path) -> ModuleData:
    """Get module data from a file path.

    Args:
        path: Path to a Python file or package

    Returns:
        ModuleData containing module import information

    """
    use_path = path.resolve()
    module_path = use_path
    if use_path.is_file() and use_path.stem == "__init__":
        module_path = use_path.parent
    module_paths = [module_path]
    extra_sys_path = module_path.parent
    for parent in module_path.parents:
        init_path = parent / "__init__.py"
        if init_path.is_file():
            module_paths.insert(0, parent)
            extra_sys_path = parent.parent
        else:
            break

    module_str = ".".join(p.stem for p in module_paths)
    return ModuleData(
        module_import_str=module_str,
        extra_sys_path=extra_sys_path.resolve(),
        module_paths=module_paths,
    )


def load_project_from_script(script_path: Path, project_name: str | None = None) -> Project:
    """Load a project from a Python script path.

    Args:
        script_path: Path to the Python script containing the project
        project_name: Name of the project variable. If None, infers from the script

    Returns:
        The loaded Project instance

    Raises:
        ImportError: If the module cannot be imported
        ValueError: If no project is found or specified project doesn't exist
        TypeError: If the specified variable is not a Project instance

    """
    import logging  # noqa: PLC0415

    from veriq._models import Project  # noqa: PLC0415

    logger = logging.getLogger(__name__)

    module_data = get_module_data_from_path(script_path)
    sys.path.insert(0, str(module_data.extra_sys_path))

    try:
        module = importlib.import_module(module_data.module_import_str)
    except (ImportError, ValueError):
        logger.exception("Import error")
        logger.warning("Ensure all the package directories have an __init__.py file")
        raise

    if project_name:
        if not hasattr(module, project_name):
            msg = f"Could not find project '{project_name}' in {module_data.module_import_str}"
            raise ValueError(msg)
        project = getattr(module, project_name)
        if not isinstance(project, Project):
            msg = f"'{project_name}' in {module_data.module_import_str} is not a Project instance"
            raise TypeError(msg)
        return project

    # Infer project from module
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, Project):
            logger.debug(f"Found project: {name}")
            return obj

    msg = "Could not find Project in module, try using --project"
    raise ValueError(msg)


def load_project_from_module_path(module_path: str) -> Project:
    """Load a project from a module path (e.g., 'examples.dummysat:project').

    Args:
        module_path: Module path in format 'module.path:variable_name'

    Returns:
        The loaded Project instance

    Raises:
        ValueError: If module path format is invalid
        TypeError: If the specified variable is not a Project instance

    """
    from veriq._models import Project  # noqa: PLC0415

    if ":" not in module_path:
        msg = "Module path must be in format 'module.path:variable_name'"
        raise ValueError(msg)

    module_name, project_name = module_path.split(":", 1)
    module = importlib.import_module(module_name)
    project = getattr(module, project_name)

    if not isinstance(project, Project):
        msg = f"'{project_name}' in module '{module_name}' is not a Project instance"
        raise TypeError(msg)

    return project


def load_project_from_source(source: ProjectSource) -> Project:
    """Load a project from a ProjectSource (script or module).

    Args:
        source: ProjectSource instance (ScriptSource or ModuleSource)

    Returns:
        The loaded Project instance

    """
    # Import here to avoid circular imports at module level
    from .config import ModuleSource, ScriptSource  # noqa: PLC0415

    match source:
        case ScriptSource(script=script, name=name):
            return load_project_from_script(script, name)
        case ModuleSource(module_path=module_path):
            return load_project_from_module_path(module_path)
