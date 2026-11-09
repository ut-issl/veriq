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
