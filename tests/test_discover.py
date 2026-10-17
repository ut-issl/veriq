import sys
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

from veriq import Project
from veriq._cli.discover import load_project_from_module_path, load_project_from_script

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def script_path(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "discovery_test_project.py"
    yield path
    sys.modules.pop(path.stem, None)


@pytest.mark.parametrize("project_name", [None, "project"])
def test_script_restores_sys_path(script_path: Path, project_name: str | None):
    script_path.write_text(
        "from veriq import Project\nproject = Project(name='discovery')\n",
        encoding="utf-8",
    )
    original_sys_path = sys.path.copy()
    original_path_list = sys.path

    project = load_project_from_script(script_path, project_name)
    assert project.name == "discovery"
    assert sys.path == original_sys_path
    assert sys.path is original_path_list


@pytest.mark.parametrize(
    ("source", "error"),
    [
        ("raise ImportError('test import failure')\n", ImportError),
        ("raise RuntimeError('test runtime failure')\n", RuntimeError),
        ("value = 1\n", ValueError),
    ],
)
def test_script_restores_sys_path_on_failure(script_path: Path, source: str, error: type[Exception]):
    script_path.write_text(source, encoding="utf-8")
    original_sys_path = sys.path.copy()

    with pytest.raises(error):
        load_project_from_script(script_path)

    assert sys.path == original_sys_path


def test_script_restores_sys_path_when_project_is_missing(script_path: Path):
    script_path.write_text("value = 1\n", encoding="utf-8")
    original_sys_path = sys.path.copy()

    with pytest.raises(ValueError, match="Could not find project 'missing'"):
        load_project_from_script(script_path, "missing")

    assert sys.path == original_sys_path


def test_module_missing_project_has_friendly_error(monkeypatch: pytest.MonkeyPatch):
    module = ModuleType("discovery_test_module")
    monkeypatch.setitem(sys.modules, module.__name__, module)

    with pytest.raises(ValueError, match="Could not find project 'missing' in discovery_test_module"):
        load_project_from_module_path(f"{module.__name__}:missing")


def test_module_loads_project(monkeypatch: pytest.MonkeyPatch):
    module = ModuleType("discovery_test_module")
    project = Project(name="discovery")
    monkeypatch.setattr(module, "project", project, raising=False)
    monkeypatch.setitem(sys.modules, module.__name__, module)

    assert load_project_from_module_path(f"{module.__name__}:project") is project


def test_module_rejects_non_project(monkeypatch: pytest.MonkeyPatch):
    module = ModuleType("discovery_test_module")
    monkeypatch.setattr(module, "project", 1, raising=False)
    monkeypatch.setitem(sys.modules, module.__name__, module)

    with pytest.raises(TypeError, match="is not a Project instance"):
        load_project_from_module_path(f"{module.__name__}:project")
