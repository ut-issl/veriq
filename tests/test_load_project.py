"""Tests for the public vq.load_project() entry point."""

import sys
from pathlib import Path
from types import ModuleType

import pytest

import veriq as vq

SCRIPT = "import veriq as vq\nproject = vq.Project(name='from-script')\n"


def test_load_project_from_script_path(tmp_path: Path) -> None:
    script = tmp_path / "proj_single.py"
    script.write_text(SCRIPT)

    assert vq.load_project(script).name == "from-script"
    assert vq.load_project(str(script)).name == "from-script"
    assert vq.load_project(script, project_var="project").name == "from-script"


def test_load_project_from_script_with_explicit_variable(tmp_path: Path) -> None:
    script = tmp_path / "proj_two_projects.py"  # distinct module name: scripts are imported as modules
    script.write_text("import veriq as vq\nfirst = vq.Project(name='a')\nsecond = vq.Project(name='b')\n")

    assert vq.load_project(script, project_var="second").name == "b"
    with pytest.raises(ValueError, match="missing"):
        vq.load_project(script, project_var="missing")


def test_load_project_from_module_path(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("load_project_test_module")
    project = vq.Project(name="from-module")
    monkeypatch.setattr(module, "project", project, raising=False)
    monkeypatch.setitem(sys.modules, module.__name__, module)

    assert vq.load_project(f"{module.__name__}:project") is project


def test_load_project_missing_script_raises(tmp_path: Path) -> None:
    with pytest.raises((FileNotFoundError, ValueError, ImportError)):
        vq.load_project(tmp_path / "nope.py")


def test_cli_discover_module_still_importable() -> None:
    from veriq._cli.discover import load_project, load_project_from_script

    assert load_project is vq.load_project
    assert callable(load_project_from_script)


def test_load_project_reads_repository_example() -> None:
    example = Path(__file__).resolve().parent.parent / "examples" / "compute_time.py"
    project = vq.load_project(example)
    assert project.name == "ComputeTime"
    assert set(project.scopes) == {"Power", "Thermal"}


PYPROJECT = """[tool.veriq]
project = {{ script = "{script}", name = "project" }}
input = "inputs/design.toml"
output = "out/result.toml"
"""


def test_get_config_resolves_paths_from_start_dir(tmp_path: Path) -> None:
    (tmp_path / "proj_cfg.py").write_text(SCRIPT)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT.format(script="proj_cfg.py"))
    nested = tmp_path / "sub" / "dir"
    nested.mkdir(parents=True)

    config = vq.get_config(nested)  # walks up to tmp_path/pyproject.toml
    assert isinstance(config, vq.VeriqConfig)
    assert config.project_root == tmp_path.resolve()
    assert config.input == (tmp_path / "inputs" / "design.toml").resolve()
    assert config.output == (tmp_path / "out" / "result.toml").resolve()
    assert isinstance(config.project, vq.ScriptSource)


def test_get_config_without_pyproject_is_empty(tmp_path: Path) -> None:
    config = vq.get_config(tmp_path)
    assert config == vq.VeriqConfig()
    assert config.input is None


def test_load_project_falls_back_to_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "proj_fallback.py").write_text(SCRIPT)
    (tmp_path / "pyproject.toml").write_text(PYPROJECT.format(script="proj_fallback.py"))

    # explicit config
    config = vq.get_config(tmp_path)
    assert vq.load_project(config=config).name == "from-script"

    # implicit: nearest pyproject.toml from the current directory
    monkeypatch.chdir(tmp_path)
    assert vq.load_project().name == "from-script"


def test_load_project_without_source_or_config_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # no pyproject.toml here
    with pytest.raises(vq.ConfigError, match="No project specified"):
        vq.load_project()
    with pytest.raises(vq.ConfigError, match="No project specified"):
        vq.load_project(config=vq.VeriqConfig())


def test_cli_config_module_still_importable() -> None:
    from veriq._cli.config import VeriqConfig, get_config

    assert VeriqConfig is vq.VeriqConfig
    assert get_config is vq.get_config
