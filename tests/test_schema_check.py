"""Tests for the `veriq schema --check` CLI mode (CI gate for schema-artifact drift)."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

EXIT_OK = 0
EXIT_STALE = 1

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


@pytest.fixture
def project_file(tmp_path: Path) -> Path:
    """Write a minimal project script for CLI invocation."""
    path = tmp_path / "test_project.py"
    path.write_text(PROJECT_CODE)
    return path


def run_schema(project_file: Path, schema_file: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    """Run `veriq schema` as a subprocess and return the completed process."""
    return subprocess.run(  # noqa: S603
        ["uv", "run", "veriq", "schema", str(project_file), "-o", str(schema_file), *extra_args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def generated_schema_file(project_file: Path, tmp_path: Path) -> Path:
    """Generate a schema file that is in sync with the project."""
    schema_file = tmp_path / "schema.json"
    result = run_schema(project_file, schema_file)
    assert result.returncode == EXIT_OK, f"schema generation failed: {result.stderr}"
    return schema_file


def test_check_in_sync_schema_exits_zero(project_file: Path, generated_schema_file: Path) -> None:
    """A freshly generated schema file passes the check."""
    result = run_schema(project_file, generated_schema_file, "--check")

    assert result.returncode == EXIT_OK, f"stderr: {result.stderr}"


def test_check_is_semantic_not_textual(project_file: Path, generated_schema_file: Path) -> None:
    """Cosmetic differences (indentation, key order) do not fail the check."""
    schema = json.loads(generated_schema_file.read_text())
    # Re-dump with different indentation, sorted keys, and no trailing newline
    generated_schema_file.write_text(json.dumps(schema, indent=4, sort_keys=True))

    result = run_schema(project_file, generated_schema_file, "--check")

    assert result.returncode == EXIT_OK, f"stderr: {result.stderr}"


def test_check_stale_schema_exits_nonzero(project_file: Path, generated_schema_file: Path) -> None:
    """A schema file that no longer matches the models fails the check."""
    schema = json.loads(generated_schema_file.read_text())
    # Simulate an outdated artifact: drop a property the current model has
    del schema["$defs"]["Design"]["properties"]["capacity"]
    generated_schema_file.write_text(json.dumps(schema))

    result = run_schema(project_file, generated_schema_file, "--check")

    assert result.returncode == EXIT_STALE, f"stderr: {result.stderr}"
    assert "capacity" in result.stderr


def test_check_missing_schema_file_exits_nonzero(project_file: Path, tmp_path: Path) -> None:
    """A missing schema file fails the check."""
    missing_file = tmp_path / "missing.json"

    result = run_schema(project_file, missing_file, "--check")

    assert result.returncode == EXIT_STALE, f"stderr: {result.stderr}"
    assert not missing_file.exists()


def test_check_malformed_schema_file_exits_nonzero(project_file: Path, tmp_path: Path) -> None:
    """A schema file that is not valid JSON fails the check."""
    schema_file = tmp_path / "schema.json"
    schema_file.write_text("{ not json")

    result = run_schema(project_file, schema_file, "--check")

    assert result.returncode == EXIT_STALE, f"stderr: {result.stderr}"


def test_check_non_object_json_exits_nonzero_without_traceback(project_file: Path, tmp_path: Path) -> None:
    """A schema file containing valid JSON that is not an object fails cleanly."""
    schema_file = tmp_path / "schema.json"
    schema_file.write_text("[1, 2, 3]")

    result = run_schema(project_file, schema_file, "--check")

    assert result.returncode == EXIT_STALE, f"stderr: {result.stderr}"
    assert "Traceback" not in result.stderr


def test_check_output_is_directory_exits_nonzero_without_traceback(project_file: Path, tmp_path: Path) -> None:
    """Pointing --output at a directory fails cleanly instead of crashing."""
    schema_dir = tmp_path / "schema.json"
    schema_dir.mkdir()

    result = run_schema(project_file, schema_dir, "--check")

    assert result.returncode == EXIT_STALE, f"stderr: {result.stderr}"
    assert "Traceback" not in result.stderr


def test_check_detects_numeric_type_drift(project_file: Path, generated_schema_file: Path) -> None:
    """An int-for-float value (100 vs 100.0) is drift, not equality."""
    content = generated_schema_file.read_text()
    assert "100.0" in content, "expected the capacity default in the generated schema"
    generated_schema_file.write_text(content.replace("100.0", "100"))

    result = run_schema(project_file, generated_schema_file, "--check")

    assert result.returncode == EXIT_STALE, f"stderr: {result.stderr}"


def test_check_never_writes(project_file: Path, generated_schema_file: Path) -> None:
    """--check must not modify the schema file even when it is stale."""
    stale_content = json.dumps({"outdated": True})
    generated_schema_file.write_text(stale_content)

    run_schema(project_file, generated_schema_file, "--check")

    assert generated_schema_file.read_text() == stale_content
