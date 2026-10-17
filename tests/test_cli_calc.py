"""Regression tests for calculation CLI verification reporting."""

import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("passed", "xfail", "expected_exit", "status"),
    [
        (True, False, 0, "PASS"),
        (False, False, 1, "FAIL"),
        (False, True, 0, "expected failure"),
        (True, True, 1, "unexpected pass"),
    ],
)
def test_verification_reporting(
    tmp_path: Path,
    *,
    passed: bool,
    xfail: bool,
    expected_exit: int,
    status: str,
) -> None:
    project_file = tmp_path / "verification_project.py"
    project_file.write_text(
        f"""from typing import Annotated
from pydantic import BaseModel
import veriq as vq

project = vq.Project("TestProject")
scope = vq.Scope("TestScope")
project.add_scope(scope)

@scope.root_model()
class Design(BaseModel):
    passed: bool

@scope.verification(xfail={xfail})
def verify(passed: Annotated[bool, vq.Ref("$.passed")]) -> bool:
    return passed
""",
    )
    input_file = tmp_path / "input.toml"
    input_file.write_text(f"[TestScope.model]\npassed = {str(passed).lower()}\n")
    output_file = tmp_path / "output.toml"

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "veriq",
            "calc",
            str(project_file),
            "-i",
            str(input_file),
            "-o",
            str(output_file),
            "--verify",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == expected_exit, result.stderr
    assert status in result.stderr
    assert ("Some verifications" in result.stderr) == bool(expected_exit)
    if passed and xfail:
        assert "passed unexpectedly" in result.stderr
    assert output_file.is_file()
