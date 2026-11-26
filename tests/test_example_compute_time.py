"""End-to-end check of examples/compute_time.py: the node-metadata foundation working together."""

import json
import runpy
import subprocess
from pathlib import Path

import pytest

import veriq as vq
from veriq._io import load_model_data_from_toml
from veriq._path import parse_project_path

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SCRIPT = EXAMPLES / "compute_time.py"
INPUT = EXAMPLES / "compute_time.in.toml"


@pytest.fixture(scope="module")
def project() -> vq.Project:
    return runpy.run_path(str(SCRIPT))["project"]


def _did(s: str) -> vq.DefinitionId:
    scope, root = s.split("::")
    return vq.DefinitionId(scope=scope, root=root)


def test_pipeline_evaluates_and_verifications_pass(project: vq.Project) -> None:
    model_data = load_model_data_from_toml(project, INPUT)
    result = vq.evaluate_project(project, model_data)
    assert result.success
    assert result.get_value(parse_project_path("Power::?margin_positive")) is True
    assert result.get_value(parse_project_path("Thermal::?panel_within_limit")) is True


def test_sequential_total_and_critical_path_differ(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_positive")

    sequential = sum(n.user_metadata.get("compute_time_s", 0.0) for n in sub.nodes.values())
    parallel = sub.propagate("compute_time_s", combine=max)

    assert len(sub) == 8  # diamond deduplicated; assumption closure included
    assert sequential == 203.0  # 30 + 120 + 5 + 2 + 45 + 1 (+ two root models at 0)
    assert parallel == 127.0  # $ -> battery_sizing (120) -> power_margin (125) -> margin_positive (127)
    assert parallel < sequential

    # Assume edges are premises: present, but not part of the recurrence
    assert sub.assume_edges == (
        vq.AssumeEdge(source=_did("Thermal::?panel_within_limit"), target=_did("Power::@solar_generation")),
    )
    data_only = vq.upstream_subgraph(project, "Power::?margin_positive", follow_assumes=False)
    assert data_only.propagate("compute_time_s", combine=max) == 127.0
    assert sum(n.user_metadata.get("compute_time_s", 0.0) for n in data_only.nodes.values()) == 158.0


def test_field_metadata_and_provenance_for_inputs(project: vq.Project) -> None:
    sub = vq.upstream_subgraph(project, "Power::?margin_positive")
    spec = vq.build_graph_spec(project)
    provenance = vq.load_provenance_from_toml(project, INPUT)

    efficiency = parse_project_path("Power::$.solar_panel.efficiency")
    assert efficiency in sub.input_leaves()
    assert spec.get_node(efficiency).field_metadata == {"unit": "-", "source_doc": "SP-DS-004"}
    assert provenance[efficiency] == {
        "baseline": "PDR-2026-03",
        "source": "vendor datasheet SP-DS-004 rev.B",
        "rationale": "BOL 0.31 derated by 2 points for 5-year EOL",
    }
    # Root-level provenance is inherited by every Power input
    assert all(provenance[leaf]["baseline"] == "PDR-2026-03" for leaf in sub.input_leaves() if leaf.scope == "Power")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["uv", "run", "veriq", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=EXAMPLES.parent,
    )


def test_cli_check_calc_and_upstream(tmp_path: Path) -> None:
    assert _run("check", str(SCRIPT)).returncode == 0

    out = tmp_path / "out.toml"
    calc = _run("calc", str(SCRIPT), "-i", str(INPUT), "-o", str(out), "--verify")
    assert calc.returncode == 0, calc.stderr
    assert "2/2 passed" in calc.stderr

    upstream = _run(
        "upstream",
        "Power::?margin_positive",
        "-p",
        str(SCRIPT),
        "--key",
        "compute_time_s",
        "-i",
        str(INPUT),
        "--json",
    )
    assert upstream.returncode == 0, upstream.stderr
    data = json.loads(upstream.stdout)
    assert data["aggregation"]["total"] == 203.0
    assert data["aggregation"]["propagated"] == 127.0
    capacity = next(i for i in data["inputs"] if i["path"] == "Power::$.battery.capacity_ah")
    assert capacity["field_metadata"] == {"unit": "Ah"}
    assert capacity["provenance"]["source"] == "cell datasheet"


def test_committed_schema_is_up_to_date() -> None:
    result = _run("schema", str(SCRIPT), "-o", str(EXAMPLES / "compute_time.in.schema.json"), "--check")
    assert result.returncode == 0, result.stderr


def test_example_main_runs() -> None:
    result = subprocess.run(  # noqa: S603
        ["uv", "run", "python", str(SCRIPT)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        cwd=EXAMPLES.parent,
    )
    assert result.returncode == 0, result.stderr
    assert "Sequential total :  203.0 s" in result.stdout
    assert "Critical path    :  127.0 s" in result.stdout
