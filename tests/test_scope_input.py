"""Tests for per-scope input TOML files (Scope(input=...)).

A scope can own its input file. ``load_model_data`` composes per-scope files
into the combined model data, with a project-level ``input`` filling only the
scopes that do not declare their own file. The per-scope file holds the scope's
root model directly (no ``[Scope.model]`` prefix), since the scope identity is
already known at registration time.
"""

from pathlib import Path

import tomli_w
from pydantic import BaseModel

import veriq as vq
from veriq._io import load_model_data, load_model_data_from_toml


def _build_project(
    *,
    power_input: str | Path | None = None,
    thermal_input: str | Path | None = None,
) -> vq.Project:
    project = vq.Project("Sat")

    power = vq.Scope("Power", input=power_input)
    project.add_scope(power)

    @power.root_model()
    class PowerModel(BaseModel):
        battery_capacity: float

    thermal = vq.Scope("Thermal", input=thermal_input)
    project.add_scope(thermal)

    @thermal.root_model()
    class ThermalModel(BaseModel):
        radiator_area: float

    return project


def _write_toml(path: Path, data: dict) -> None:
    with path.open("wb") as f:
        tomli_w.dump(data, f)


def test_per_scope_file_is_loaded(tmp_path: Path) -> None:
    """A scope with its own input file loads the model directly from it."""
    power_file = tmp_path / "power.toml"
    _write_toml(power_file, {"battery_capacity": 150.0})

    project = _build_project(power_input=power_file)
    data = load_model_data(project)

    assert data["Power"].battery_capacity == 150.0  # ty: ignore[unresolved-attribute]
    assert "Thermal" not in data  # no file, no combined input -> skipped


def test_combined_input_fills_scopes_without_file(tmp_path: Path) -> None:
    """Project-level -i fills scopes that do not declare their own file."""
    combined = tmp_path / "input.toml"
    _write_toml(
        combined,
        {
            "Power": {"model": {"battery_capacity": 99.0}},
            "Thermal": {"model": {"radiator_area": 2.0}},
        },
    )

    project = _build_project()  # no per-scope files
    data = load_model_data(project, input=combined)

    assert data["Power"].battery_capacity == 99.0  # ty: ignore[unresolved-attribute]
    assert data["Thermal"].radiator_area == 2.0  # ty: ignore[unresolved-attribute]


def test_scope_file_takes_precedence_combined_fills_rest(tmp_path: Path) -> None:
    """Scope file is authoritative; combined -i only fills the other scopes."""
    power_file = tmp_path / "power.toml"
    _write_toml(power_file, {"battery_capacity": 150.0})

    combined = tmp_path / "input.toml"
    _write_toml(
        combined,
        {
            # This Power value must be ignored in favor of the per-scope file.
            "Power": {"model": {"battery_capacity": 0.0}},
            "Thermal": {"model": {"radiator_area": 3.0}},
        },
    )

    project = _build_project(power_input=power_file)
    data = load_model_data(project, input=combined)

    assert data["Power"].battery_capacity == 150.0  # ty: ignore[unresolved-attribute]
    assert data["Thermal"].radiator_area == 3.0  # ty: ignore[unresolved-attribute]


def test_load_model_data_from_toml_backward_compatible(tmp_path: Path) -> None:
    """The existing single-file loader keeps working unchanged."""
    combined = tmp_path / "input.toml"
    _write_toml(
        combined,
        {
            "Power": {"model": {"battery_capacity": 12.0}},
            "Thermal": {"model": {"radiator_area": 4.0}},
        },
    )

    project = _build_project()
    data = load_model_data_from_toml(project, combined)

    assert data["Power"].battery_capacity == 12.0  # ty: ignore[unresolved-attribute]
    assert data["Thermal"].radiator_area == 4.0  # ty: ignore[unresolved-attribute]


def test_input_path_resolves_relative_to_definition_dir() -> None:
    """A relative scope input resolves against the defining module's directory."""
    scope = vq.Scope("Power", input="data/power.toml")
    resolved = scope.input_path
    assert resolved is not None
    assert resolved.is_absolute()
    # Defined in this test file, so it resolves next to it.
    assert resolved == (Path(__file__).resolve().parent / "data/power.toml")


def test_scope_without_input_has_none_path() -> None:
    """A scope without an input file exposes input_path is None."""
    scope = vq.Scope("Power")
    assert scope.input_path is None
