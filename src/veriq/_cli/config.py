"""Configuration loading from pyproject.toml."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast


class ConfigError(Exception):
    """Error in veriq configuration."""


@dataclass(slots=True, frozen=True)
class ScriptSource:
    """Script path with optional variable name."""

    script: Path
    name: str | None = None


@dataclass(slots=True, frozen=True)
class ModuleSource:
    """Module path with variable name (e.g., 'examples.dummysat:project')."""

    module_path: str


ProjectSource = ScriptSource | ModuleSource


@dataclass(slots=True, frozen=True)
class VeriqConfig:
    """Configuration loaded from pyproject.toml.

    All relative paths are resolved from the project root (directory containing pyproject.toml).
    """

    project: ProjectSource | None = None
    input: Path | None = None
    output: Path | None = None
    project_root: Path | None = None


def find_pyproject_toml(start_dir: Path | None = None) -> Path | None:
    """Find pyproject.toml by walking up from start_dir.

    Args:
        start_dir: Starting directory. Defaults to current working directory.

    Returns:
        Path to pyproject.toml if found, None otherwise.

    """
    if start_dir is None:
        start_dir = Path.cwd()

    current = start_dir.resolve()

    while True:
        candidate = current / "pyproject.toml"
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            return None
        current = parent


def _parse_project_source(value: object, project_root: Path) -> ProjectSource:
    """Parse the project field from config.

    Args:
        value: The raw value from TOML (string or dict)
        project_root: Project root directory for resolving relative paths

    Returns:
        Parsed ProjectSource

    Raises:
        ConfigError: If the value format is invalid

    """
    if isinstance(value, str):
        # Module path format: "module.path:variable"
        if ":" not in value:
            msg = (
                f"Invalid module path '{value}'. "
                "Expected format: 'module.path:variable_name'"
            )
            raise ConfigError(msg)
        return ModuleSource(module_path=value)

    if isinstance(value, dict):
        # Script path format: { script = "path.py", name = "project" }
        value_dict = cast("dict[str, object]", value)
        if "script" not in value_dict:
            msg = (
                "Invalid [tool.veriq].project configuration. "
                "Expected string or table with 'script' key."
            )
            raise ConfigError(msg)

        script_value = value_dict["script"]
        if not isinstance(script_value, str):
            msg = "Invalid [tool.veriq].project.script: expected string path"
            raise ConfigError(msg)
        script_path = Path(script_value)
        # Resolve relative to project root
        if not script_path.is_absolute():
            script_path = project_root / script_path

        name = value_dict.get("name")
        if name is not None and not isinstance(name, str):
            msg = "Invalid [tool.veriq].project.name: expected string"
            raise ConfigError(msg)

        return ScriptSource(script=script_path, name=name)

    msg = (
        "Invalid [tool.veriq].project configuration. "
        "Expected string or table with 'script' key."
    )
    raise ConfigError(msg)


def load_config(pyproject_path: Path) -> VeriqConfig:
    """Load and validate [tool.veriq] config from pyproject.toml.

    Args:
        pyproject_path: Path to pyproject.toml

    Returns:
        Parsed VeriqConfig

    Raises:
        ConfigError: If the configuration is invalid

    """
    project_root = pyproject_path.parent

    with pyproject_path.open("rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            msg = f"Invalid TOML in {pyproject_path}: {e}"
            raise ConfigError(msg) from e

    # Extract [tool.veriq] section
    tool_section = data.get("tool", {})
    veriq_section = tool_section.get("veriq", {})

    if not veriq_section:
        # No [tool.veriq] section - return empty config
        return VeriqConfig(project_root=project_root)

    # Parse project
    project_source: ProjectSource | None = None
    if "project" in veriq_section:
        project_source = _parse_project_source(veriq_section["project"], project_root)

    # Parse input path
    input_path: Path | None = None
    if "input" in veriq_section:
        input_value = veriq_section["input"]
        if not isinstance(input_value, str):
            msg = "Invalid [tool.veriq].input: expected string path"
            raise ConfigError(msg)
        input_path = Path(input_value)
        if not input_path.is_absolute():
            input_path = project_root / input_path

    # Parse output path
    output_path: Path | None = None
    if "output" in veriq_section:
        output_value = veriq_section["output"]
        if not isinstance(output_value, str):
            msg = "Invalid [tool.veriq].output: expected string path"
            raise ConfigError(msg)
        output_path = Path(output_value)
        if not output_path.is_absolute():
            output_path = project_root / output_path

    return VeriqConfig(
        project=project_source,
        input=input_path,
        output=output_path,
        project_root=project_root,
    )


def get_config() -> VeriqConfig:
    """Get config from pyproject.toml in current directory or parents.

    Returns:
        VeriqConfig (may be empty if no pyproject.toml or no [tool.veriq] section)

    """
    pyproject_path = find_pyproject_toml()
    if pyproject_path is None:
        return VeriqConfig()
    return load_config(pyproject_path)
