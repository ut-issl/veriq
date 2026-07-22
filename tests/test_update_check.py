"""Tests for the `veriq update --check` CLI mode (CI gate for input drift/validity)."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

EXIT_OK = 0
EXIT_STALE = 1
EXIT_INVALID = 2

PROJECT_CODE = """
from pydantic import BaseModel

import veriq as vq


class Design(BaseModel):
    voltage: float
    capacity: float = 100.0


project = vq.Project(name="TestProject")
scope = vq.Scope(name="Power")
project.add_scope(scope)
scope.root_model()(Design)
"""

UP_TO_DATE_TOML = """[Power.model]
voltage = 3.3
capacity = 200.0
"""


@pytest.fixture
def project_file(tmp_path: Path) -> Path:
    """Write a minimal project script for CLI invocation."""
    path = tmp_path / "test_project.py"
    path.write_text(PROJECT_CODE)
    return path


def run_update_check(project_file: Path, input_file: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    """Run `veriq update --check` as a subprocess and return the completed process."""
    return subprocess.run(  # noqa: S603
        ["uv", "run", "veriq", "update", str(project_file), "-i", str(input_file), "--check", *extra_args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_up_to_date_input_exits_zero(project_file: Path, tmp_path: Path) -> None:
    """An input matching the current schema exits 0."""
    input_file = tmp_path / "input.toml"
    input_file.write_text(UP_TO_DATE_TOML)

    result = run_update_check(project_file, input_file)

    assert result.returncode == EXIT_OK, f"stderr: {result.stderr}"


def test_check_is_semantic_not_textual(project_file: Path, tmp_path: Path) -> None:
    """Comments, key order, whitespace, and int-for-float values do not fail the check."""
    input_file = tmp_path / "input.toml"
    input_file.write_text(
        """# Design parameters for the Power scope

[Power.model]
capacity = 200   # int stored for a float field, keys out of schema order
voltage  = 3.3
""",
    )

    result = run_update_check(project_file, input_file)

    assert result.returncode == EXIT_OK, f"stderr: {result.stderr}"


def test_check_missing_field_exits_stale_and_reports_field(project_file: Path, tmp_path: Path) -> None:
    """An input missing a schema field (with model default) is stale: exit 1, field named."""
    input_file = tmp_path / "input.toml"
    input_file.write_text("[Power.model]\nvoltage = 3.3\n")

    result = run_update_check(project_file, input_file)

    assert result.returncode == EXIT_STALE, f"stderr: {result.stderr}"
    assert "capacity" in result.stderr


def test_check_obsolete_field_exits_stale_and_reports_field(project_file: Path, tmp_path: Path) -> None:
    """An input carrying a field removed from the schema is stale: exit 1, field named."""
    input_file = tmp_path / "input.toml"
    input_file.write_text(UP_TO_DATE_TOML + "obsolete_field = 1.0\n")

    result = run_update_check(project_file, input_file)

    assert result.returncode == EXIT_STALE, f"stderr: {result.stderr}"
    assert "obsolete_field" in result.stderr


def test_check_invalid_type_exits_invalid(project_file: Path, tmp_path: Path) -> None:
    """An input failing schema validation exits 2 (takes precedence over stale)."""
    input_file = tmp_path / "input.toml"
    input_file.write_text('[Power.model]\nvoltage = "high"\ncapacity = 200.0\n')

    result = run_update_check(project_file, input_file)

    assert result.returncode == EXIT_INVALID, f"stderr: {result.stderr}"
    assert "voltage" in result.stderr


def test_check_missing_scope_exits_invalid(project_file: Path, tmp_path: Path) -> None:
    """An input missing a whole scope fails validation: exit 2."""
    input_file = tmp_path / "input.toml"
    input_file.write_text("")

    result = run_update_check(project_file, input_file)

    assert result.returncode == EXIT_INVALID, f"stderr: {result.stderr}"


def test_check_never_writes(project_file: Path, tmp_path: Path) -> None:
    """--check must not modify the input file even when it is stale."""
    input_file = tmp_path / "input.toml"
    original_content = "[Power.model]\nvoltage = 3.3\n"
    input_file.write_text(original_content)

    run_update_check(project_file, input_file)

    assert input_file.read_text() == original_content


def test_check_rejects_output_option(project_file: Path, tmp_path: Path) -> None:
    """--check writes nothing, so combining it with -o/--output is an error."""
    input_file = tmp_path / "input.toml"
    input_file.write_text(UP_TO_DATE_TOML)
    output_file = tmp_path / "out.toml"

    result = run_update_check(project_file, input_file, "-o", str(output_file))

    assert result.returncode != EXIT_OK
    assert not output_file.exists()


def test_dry_run_option_is_removed(project_file: Path, tmp_path: Path) -> None:
    """--dry-run is replaced by --check and no longer accepted."""
    input_file = tmp_path / "input.toml"
    input_file.write_text(UP_TO_DATE_TOML)

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "veriq", "update", str(project_file), "-i", str(input_file), "--dry-run"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != EXIT_OK
