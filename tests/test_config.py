"""Tests for the configuration module."""

from pathlib import Path

import pytest

from veriq._cli.config import (
    ConfigError,
    ModuleSource,
    ScriptSource,
    VeriqConfig,
    find_pyproject_toml,
    load_config,
)


class TestFindPyprojectToml:
    """Tests for find_pyproject_toml function."""

    def test_finds_in_current_directory(self, tmp_path: Path) -> None:
        """Should find pyproject.toml in current directory."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")

        result = find_pyproject_toml(tmp_path)

        assert result == pyproject

    def test_finds_in_parent_directory(self, tmp_path: Path) -> None:
        """Should find pyproject.toml in parent directory."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")

        subdir = tmp_path / "src" / "pkg"
        subdir.mkdir(parents=True)

        result = find_pyproject_toml(subdir)

        assert result == pyproject

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        """Should return None when no pyproject.toml is found."""
        result = find_pyproject_toml(tmp_path)

        assert result is None


class TestLoadConfigModulePath:
    """Tests for loading module path configuration."""

    def test_module_path_string(self, tmp_path: Path) -> None:
        """Should parse module path string format."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = "examples.dummysat:project"
""",
        )

        config = load_config(pyproject)

        assert config.project == ModuleSource(module_path="examples.dummysat:project")
        assert config.project_root == tmp_path

    def test_module_path_without_colon_raises_error(self, tmp_path: Path) -> None:
        """Should raise ConfigError for invalid module path."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = "examples.dummysat"
""",
        )

        with pytest.raises(ConfigError, match="Invalid module path"):
            load_config(pyproject)


class TestLoadConfigScriptPath:
    """Tests for loading script path configuration."""

    def test_script_path_inline_table(self, tmp_path: Path) -> None:
        """Should parse script path inline table format."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = { script = "examples/dummysat.py" }
""",
        )

        config = load_config(pyproject)

        assert isinstance(config.project, ScriptSource)
        assert config.project.script == tmp_path / "examples/dummysat.py"
        assert config.project.name is None

    def test_script_path_with_name(self, tmp_path: Path) -> None:
        """Should parse script path with explicit variable name."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = { script = "examples/dummysat.py", name = "my_project" }
""",
        )

        config = load_config(pyproject)

        assert isinstance(config.project, ScriptSource)
        assert config.project.script == tmp_path / "examples/dummysat.py"
        assert config.project.name == "my_project"

    def test_script_path_missing_script_key_raises_error(self, tmp_path: Path) -> None:
        """Should raise ConfigError when script key is missing."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = { name = "my_project" }
""",
        )

        with pytest.raises(ConfigError, match="'script' key"):
            load_config(pyproject)


class TestLoadConfigInputOutput:
    """Tests for loading input/output path configuration."""

    def test_input_path(self, tmp_path: Path) -> None:
        """Should parse input path."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = "pkg:project"
input = "data/input.toml"
""",
        )

        config = load_config(pyproject)

        assert config.input == tmp_path / "data/input.toml"

    def test_output_path(self, tmp_path: Path) -> None:
        """Should parse output path."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = "pkg:project"
output = "data/output.toml"
""",
        )

        config = load_config(pyproject)

        assert config.output == tmp_path / "data/output.toml"

    def test_full_configuration(self, tmp_path: Path) -> None:
        """Should parse full configuration with all fields."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = { script = "examples/dummysat.py", name = "project" }
input = "data/input.toml"
output = "data/output.toml"
""",
        )

        config = load_config(pyproject)

        assert isinstance(config.project, ScriptSource)
        assert config.project.script == tmp_path / "examples/dummysat.py"
        assert config.project.name == "project"
        assert config.input == tmp_path / "data/input.toml"
        assert config.output == tmp_path / "data/output.toml"
        assert config.project_root == tmp_path

    def test_invalid_input_type_raises_error(self, tmp_path: Path) -> None:
        """Should raise ConfigError when input is not a string."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = "pkg:project"
input = 123
""",
        )

        with pytest.raises(ConfigError, match="expected string path"):
            load_config(pyproject)


class TestLoadConfigEmptySection:
    """Tests for empty or missing configuration."""

    def test_no_tool_veriq_section(self, tmp_path: Path) -> None:
        """Should return empty config when no [tool.veriq] section."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[project]
name = "test"
""",
        )

        config = load_config(pyproject)

        assert config.project is None
        assert config.input is None
        assert config.output is None
        assert config.project_root == tmp_path

    def test_empty_tool_veriq_section(self, tmp_path: Path) -> None:
        """Should return empty config when [tool.veriq] is empty."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
""",
        )

        config = load_config(pyproject)

        assert config.project is None
        assert config.input is None
        assert config.output is None


class TestLoadConfigErrors:
    """Tests for configuration error handling."""

    def test_invalid_toml_raises_error(self, tmp_path: Path) -> None:
        """Should raise ConfigError for invalid TOML."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("invalid toml [[[")

        with pytest.raises(ConfigError, match="Invalid TOML"):
            load_config(pyproject)

    def test_invalid_project_type_raises_error(self, tmp_path: Path) -> None:
        """Should raise ConfigError for invalid project type."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.veriq]
project = 123
""",
        )

        with pytest.raises(ConfigError, match=r"Invalid.*project configuration"):
            load_config(pyproject)


class TestVeriqConfigDataclass:
    """Tests for the VeriqConfig dataclass."""

    def test_default_values(self) -> None:
        """Should have None as default values."""
        config = VeriqConfig()

        assert config.project is None
        assert config.input is None
        assert config.output is None
        assert config.project_root is None

    def test_frozen(self) -> None:
        """Should be frozen (immutable)."""
        config = VeriqConfig()

        with pytest.raises(AttributeError):
            config.project = ModuleSource("pkg:proj")  # type: ignore[misc]


class TestProjectSourceTypes:
    """Tests for ProjectSource type variants."""

    def test_module_source(self) -> None:
        """Should create ModuleSource correctly."""
        source = ModuleSource(module_path="pkg.sub:var")

        assert source.module_path == "pkg.sub:var"

    def test_script_source_minimal(self) -> None:
        """Should create ScriptSource with minimal args."""
        source = ScriptSource(script=Path("test.py"))

        assert source.script == Path("test.py")
        assert source.name is None

    def test_script_source_with_name(self) -> None:
        """Should create ScriptSource with name."""
        source = ScriptSource(script=Path("test.py"), name="my_var")

        assert source.script == Path("test.py")
        assert source.name == "my_var"
