"""Utilities to discover veriq projects and modules.

This module was adapted from `fastapi_cli.discover` of package `fastapi-cli` version 0.0.8 (77e6d1f).
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from veriq._config import ConfigError, ModuleSource, ScriptSource, VeriqConfig, get_config

if TYPE_CHECKING:
    from types import ModuleType

    from veriq._models import Project

DEFAULT_PROJECT_VARIABLE = "project"


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


def is_module_path(source: str) -> bool:
    """True for ``package.module:variable``, False for a script path.

    The check is syntactic, so a script path that contains ``:`` (a Windows drive such as
    ``C:/proj/design.py``) is not mistaken for a module path.
    """
    module_name, separator, variable = source.partition(":")
    return bool(separator) and variable.isidentifier() and all(part.isidentifier() for part in module_name.split("."))


def _check_module_origin(module: ModuleType, script_path: Path, module_name: str) -> None:
    """Make sure `module` really is the script at `script_path`.

    A script is imported under a module name derived from its file name, and Python caches
    modules by name. If that name is already taken (another script with the same file name
    was loaded before, or the name shadows an imported library such as ``json``), the import
    returns the other module and its project, if any, would be returned silently.
    """
    expected = script_path.resolve()
    if expected.is_dir():
        expected /= "__init__.py"
    module_file = getattr(module, "__file__", None)
    if module_file is not None and Path(module_file).resolve() == expected:
        return
    origin = f"'{module_file}'" if module_file is not None else "a built-in module or a namespace package"
    msg = (
        f"Cannot load '{script_path}': it is imported as module '{module_name}', "
        f"but that name already refers to {origin}. "
        "Rename the script so that its module name is unique in this process."
    )
    raise ImportError(msg)


def _infer_project(module: ModuleType, module_name: str) -> Project:
    """Pick the project of a module when no variable name was given.

    A single `Project` is used whatever it is called. With several, the one bound to the
    variable ``project`` is used; otherwise the choice is ambiguous and an error.
    """
    from veriq._models import Project  # noqa: PLC0415

    found = {name: obj for name, obj in vars(module).items() if isinstance(obj, Project)}
    if not found:
        msg = f"Could not find a Project in {module_name}"
        raise ValueError(msg)
    # Several names may be bound to the same object (aliases); that is not ambiguous
    if len({id(obj) for obj in found.values()}) == 1:
        return next(iter(found.values()))
    if DEFAULT_PROJECT_VARIABLE in found:
        return found[DEFAULT_PROJECT_VARIABLE]
    msg = (
        f"Found several Projects in {module_name} ({', '.join(sorted(found))}) and none is named "
        f"'{DEFAULT_PROJECT_VARIABLE}'. Name the one to load (project_var, or --project on the command line)."
    )
    raise ValueError(msg)


def load_project_from_script(script_path: Path, project_name: str | None = None) -> Project:
    """Load a project from a Python script path.

    The script is imported as a regular module named after the file, so it is cached like
    any other import: loading the same path again returns the same `Project` object, and
    later edits to the file are not picked up within the process.

    Args:
        script_path: Path to the Python script containing the project
        project_name: Name of the project variable. If None, the script's only `Project`
            is used; if it defines several, the one named ``project``.

    Returns:
        The loaded Project instance

    Raises:
        FileNotFoundError: If the script does not exist
        ImportError: If the module cannot be imported, or its module name is already taken
            by a different module
        ValueError: If no project is found, the choice between several projects is ambiguous,
            or the specified project doesn't exist
        TypeError: If the specified variable is not a Project instance

    """
    import logging  # noqa: PLC0415

    from veriq._models import Project  # noqa: PLC0415

    logger = logging.getLogger(__name__)

    if not script_path.exists():
        msg = f"Project script not found: {script_path}"
        raise FileNotFoundError(msg)

    module_data = get_module_data_from_path(script_path)
    original_sys_path = sys.path.copy()
    sys.path.insert(0, str(module_data.extra_sys_path))

    try:
        module = importlib.import_module(module_data.module_import_str)
    except ImportError, ValueError:
        logger.exception("Import error")
        logger.warning("Ensure all the package directories have an __init__.py file")
        raise
    finally:
        sys.path[:] = original_sys_path

    _check_module_origin(module, script_path, module_data.module_import_str)

    if project_name:
        if not hasattr(module, project_name):
            msg = f"Could not find project '{project_name}' in {module_data.module_import_str}"
            raise ValueError(msg)
        project = getattr(module, project_name)
        if not isinstance(project, Project):
            msg = f"'{project_name}' in {module_data.module_import_str} is not a Project instance"
            raise TypeError(msg)
        return project

    return _infer_project(module, module_data.module_import_str)


def load_project_from_module_path(module_path: str) -> Project:
    """Load a project from a module path (e.g., 'examples.dummysat:project').

    Args:
        module_path: Module path in format 'module.path:variable_name'

    Returns:
        The loaded Project instance

    Raises:
        ValueError: If module path format is invalid or the specified project doesn't exist
        TypeError: If the specified variable is not a Project instance

    """
    from veriq._models import Project  # noqa: PLC0415

    if ":" not in module_path:
        msg = "Module path must be in format 'module.path:variable_name'"
        raise ValueError(msg)

    module_name, project_name = module_path.split(":", 1)
    module = importlib.import_module(module_name)
    if not hasattr(module, project_name):
        msg = f"Could not find project '{project_name}' in {module_name}"
        raise ValueError(msg)
    project = getattr(module, project_name)

    if not isinstance(project, Project):
        msg = f"'{project_name}' in module '{module_name}' is not a Project instance"
        raise TypeError(msg)

    return project


def load_project(
    source: str | Path | None = None,
    *,
    project_var: str | None = None,
    config: VeriqConfig | None = None,
) -> Project:
    """Load a `Project` the same way the CLI does.

    Args:
        source: Either a path to a Python script that defines the project, or a module
            path of the form ``"package.module:variable"`` (dotted identifiers, a colon and
            an identifier; any other string is a script path). If None, the project
            configured in ``[tool.veriq].project`` of the nearest pyproject.toml is used
            (see `get_config`).
        project_var: Name of the project variable in the script. If None, the script's only
            `Project` is used; if it defines several, the one named ``project``, and it is
            an error if there is none. Ignored for module paths, which name the variable
            explicitly. Overrides the configured name when falling back to the configuration.
        config: Configuration to use when `source` is None. Defaults to `get_config()`.

    A script is imported as a regular module named after its file, so it is cached like any
    other import: loading the same path again returns the same object and does not re-read
    the file, and two scripts with the same file name cannot both be loaded in one process
    (the second raises `ImportError` rather than returning the first one's project).

    Returns:
        The loaded `Project`.

    Raises:
        ConfigError: If `source` is None and no project is configured (or the config is invalid).
        FileNotFoundError: If the script does not exist.
        ImportError: If the script or module cannot be imported, or the script's module name
            is already taken by a different module.
        ValueError: If no project (or no unambiguous project) is found in the script/module.
        TypeError: If the named variable is not a `Project`.

    Example:
        >>> project = vq.load_project("examples/compute_time.py")
        >>> project = vq.load_project("examples.compute_time:project")
        >>> project = vq.load_project()  # [tool.veriq].project from pyproject.toml

    """
    if source is None:
        if config is None:
            config = get_config()
        match config.project:
            case ScriptSource(script=script, name=name):
                return load_project_from_script(script, project_var or name)
            case ModuleSource(module_path=module_path):
                return load_project_from_module_path(module_path)
            case _:
                msg = "No project specified. Pass a source or configure [tool.veriq].project in pyproject.toml."
                raise ConfigError(msg)
    if isinstance(source, str) and is_module_path(source):
        return load_project_from_module_path(source)
    return load_project_from_script(Path(source), project_var)
