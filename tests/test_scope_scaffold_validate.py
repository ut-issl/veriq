"""Tests for per-scope input validation and scaffolding.

SSOT view: a scope's ``input`` TOML (e.g. data.toml) is the single source of
input data; the scope's root model is the single source of schema. ``validate``
checks the data against the schema without evaluating; ``scaffold`` generates /
refreshes the data file from the schema defaults without creating a competing
source (existing values and comments are preserved).
"""

import tomllib
from pathlib import Path  # noqa: TC003 - used in runtime annotations via tmp_path fixture

import tomli_w
from pydantic import BaseModel

import veriq as vq


class PowerModel(BaseModel):
    battery_capacity: float
    label: str = "default-label"


def _project(power_input: Path) -> vq.Project:
    project = vq.Project("Sat")
    power = vq.Scope("Power", input=power_input)
    project.add_scope(power)
    power.root_model()(PowerModel)
    return project


def _write(path: Path, data: dict) -> None:
    with path.open("wb") as f:
        tomli_w.dump(data, f)


# ── validate ─────────────────────────────────────────────────────────────


def test_validate_ok(tmp_path: Path) -> None:
    f = tmp_path / "power.toml"
    _write(f, {"battery_capacity": 150.0, "label": "x"})

    report = vq.validate_model_data(_project(f))

    assert report.ok
    assert len(report.results) == 1
    r = report.results[0]
    assert r.scope == "Power"
    assert r.ok
    assert r.source == f
    assert r.error is None


def test_validate_detects_type_error(tmp_path: Path) -> None:
    f = tmp_path / "power.toml"
    _write(f, {"battery_capacity": "not-a-number"})

    report = vq.validate_model_data(_project(f))

    assert not report.ok
    r = report.results[0]
    assert not r.ok
    assert r.error is not None
    assert "battery_capacity" in r.error


def test_validate_combined_input(tmp_path: Path) -> None:
    combined = tmp_path / "input.toml"
    _write(combined, {"Power": {"model": {"battery_capacity": 1.0}}})

    project = vq.Project("Sat")
    power = vq.Scope("Power")  # no per-scope file
    project.add_scope(power)
    power.root_model()(PowerModel)

    report = vq.validate_model_data(project, input=combined)
    assert report.ok
    assert report.results[0].source == combined


# ── scaffold ─────────────────────────────────────────────────────────────


def test_scaffold_creates_missing_file(tmp_path: Path) -> None:
    f = tmp_path / "power.toml"
    project = _project(f)

    results = vq.scaffold_input(project)

    assert f.exists()
    assert len(results) == 1
    assert results[0].created is True
    # The generated file must validate against the schema.
    assert vq.validate_model_data(project).ok


def test_scaffold_preserves_existing_and_adds_missing(tmp_path: Path) -> None:
    f = tmp_path / "power.toml"
    _write(f, {"battery_capacity": 999.0})  # label missing

    results = vq.scaffold_input(_project(f))

    data = tomllib.loads(f.read_text())
    assert data["battery_capacity"] == 999.0  # preserved
    # veriq's default() emits type-zero placeholders, so a missing str field is
    # added as "" (the user fills the real value). The point: it gets added.
    assert "label" in data
    assert data["label"] == ""
    assert results[0].created is False


def test_scaffold_overwrite_resets_to_defaults(tmp_path: Path) -> None:
    f = tmp_path / "power.toml"
    _write(f, {"battery_capacity": 999.0})

    vq.scaffold_input(_project(f), overwrite=True)

    data = tomllib.loads(f.read_text())
    assert data["battery_capacity"] == 0.0  # reset to default


def test_scaffold_dry_run_writes_nothing(tmp_path: Path) -> None:
    f = tmp_path / "power.toml"
    results = vq.scaffold_input(_project(f), dry_run=True)

    assert not f.exists()
    assert results[0].created is True  # would have created
