"""Tests for transient calculations.

A transient calculation is computed and passed to dependent calculations in
Python (in-memory), but is NOT written to the exported TOML. This lets a calc
return a large/complex analysis result (saved elsewhere by the function itself,
e.g. to CSV) and feed it to downstream calcs without bloating output.toml.
"""

import tomllib
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._io import export_to_toml, results_to_dict
from veriq._path import CalcPath, ProjectPath

if TYPE_CHECKING:
    from pathlib import Path


def _build_project() -> tuple[vq.Project, type[BaseModel]]:
    project = vq.Project(name="P")
    scope = vq.Scope(name="S")
    project.add_scope(scope)

    @scope.root_model()
    class M(BaseModel):
        x: float

    @scope.calculation(transient=True)
    def heavy(x: Annotated[float, vq.Ref("$.x")]) -> float:
        return x * 10.0

    @scope.calculation()
    def summary(h: Annotated[float, vq.Ref("@heavy")]) -> float:
        return h + 1.0

    return project, M


def test_transient_calc_feeds_dependent_calc() -> None:
    """A transient calc still passes its value to dependent calcs in Python."""
    project, model = _build_project()
    result = evaluate_project(project, {"S": model(x=2.0)})

    heavy_path = ProjectPath(scope="S", path=CalcPath(root="@heavy", parts=()))
    summary_path = ProjectPath(scope="S", path=CalcPath(root="@summary", parts=()))
    assert result.get_value(heavy_path) == 20.0
    assert result.get_value(summary_path) == 21.0


def test_results_to_dict_excludes_listed_calcs() -> None:
    """results_to_dict drops calcs named in exclude_calcs, keeps the rest."""
    project, model = _build_project()
    result = evaluate_project(project, {"S": model(x=2.0)})

    data = results_to_dict(result, exclude_calcs={("S", "heavy")})
    calc_section = data["S"]["calc"]
    assert "heavy" not in calc_section
    assert calc_section["summary"] == 21.0


def test_export_to_toml_skips_transient_calc(tmp_path: Path) -> None:
    """export_to_toml derives the exclusion set from the project's transient calcs."""
    project, model = _build_project()
    result = evaluate_project(project, {"S": model(x=2.0)})

    out = tmp_path / "out.toml"
    export_to_toml(project, {"S": model(x=2.0)}, result, out)

    parsed = tomllib.loads(out.read_text())
    assert "heavy" not in parsed["S"]["calc"]
    assert parsed["S"]["calc"]["summary"] == 21.0
