"""Tests for the `veriq upstream` command and metadata exposure in `show` / `list`."""

import json
from typing import TYPE_CHECKING, Annotated
from unittest.mock import patch

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

import veriq as vq
from veriq._cli.config import VeriqConfig
from veriq._cli.main import app
from veriq._cli.upstream_query import Combine, build_upstream_report, report_to_dict

if TYPE_CHECKING:
    from pathlib import Path


class Battery(BaseModel):
    capacity: Annotated[float, vq.Meta(unit="Wh")]
    min_capacity: float


class Design(BaseModel):
    battery: Battery
    area: float
    unused: float


class Env(BaseModel):
    max_temp: float


@pytest.fixture
def project() -> vq.Project:
    """Power::$ -> @gen (10), @heat (20) -> @budget (5) -> ?ok (2); @budget assumes Thermal::?temp_ok (1)."""
    project = vq.Project(name="Sat")
    power = vq.Scope(name="Power")
    thermal = vq.Scope(name="Thermal")
    project.add_scope(power)
    project.add_scope(thermal)
    power.root_model(metadata={"owner": "eps"})(Design)
    thermal.root_model()(Env)

    @thermal.verification(metadata={"compute_time_s": 1.0})
    def temp_ok(max_temp: Annotated[float, vq.Ref("$.max_temp")]) -> bool:
        return max_temp < 100

    @power.calculation(metadata={"compute_time_s": 10.0})
    def gen(area: Annotated[float, vq.Ref("$.area")]) -> float:
        return area

    @power.calculation(metadata={"compute_time_s": 20.0})
    def heat(battery: Annotated[Battery, vq.Ref("$.battery")]) -> float:
        return battery.capacity

    @power.calculation(imports=["Thermal"], metadata={"compute_time_s": 5.0})
    @vq.assume(vq.Ref("?temp_ok", scope="Thermal"))
    def budget(g: Annotated[float, vq.Ref("@gen")], h: Annotated[float, vq.Ref("@heat")]) -> float:
        return g - h

    @power.verification(metadata={"compute_time_s": 2.0})
    def ok(b: Annotated[float, vq.Ref("@budget")]) -> bool:
        return b > 0

    return project


def _run(project: vq.Project, *args: str, config: VeriqConfig | None = None):  # noqa: ANN202
    with (
        patch("veriq._cli.main._load_project", return_value=project),
        patch("veriq._cli.main.get_config", return_value=config or VeriqConfig()),
    ):
        return CliRunner().invoke(app, list(args))


# --- functional core ---


def test_report_aggregation_and_inputs(project: vq.Project) -> None:
    report = build_upstream_report(project, "Power::?ok", key="compute_time_s", combine=Combine.MAX)
    assert report.aggregation is not None
    assert report.aggregation.total == 38.0  # 0 + 1 + 10 + 20 + 5 + 2 (+ Thermal::$ 0)
    assert report.propagated_at_target == 27.0  # $ -> heat (20) -> budget (25) -> ok (27)
    assert [str(i.path) for i in report.inputs] == [
        "Power::$.area",
        "Power::$.battery.capacity",
        "Power::$.battery.min_capacity",
        "Thermal::$.max_temp",
    ]
    assert report.inputs[1].field_metadata == {"unit": "Wh"}
    assert report.inputs[1].provenance == {}
    assert report.provenance_loaded is False


def test_report_without_key_has_no_aggregation(project: vq.Project) -> None:
    report = build_upstream_report(project, "Power::?ok")
    assert report.aggregation is None
    assert report.propagated_at_target is None
    data = report_to_dict(report)
    assert "aggregation" not in data
    assert "value" not in data["nodes"][0]


def test_report_with_provenance(project: vq.Project, tmp_path: Path) -> None:
    toml = tmp_path / "in.toml"
    toml.write_text(
        '[Power.model]\n[Power.provenance."$.battery"]\nsource = "datasheet"\n'
        '[Power.provenance."$.battery.capacity"]\nrationale = "EOL margin"\n'
        '[Power.provenance."$.unused"]\nnote = "not read by ?ok"\n',
    )
    report = build_upstream_report(project, "Power::?ok", input_path=toml)
    assert report.provenance_loaded is True
    by_path = {str(i.path): i for i in report.inputs}
    assert by_path["Power::$.battery.capacity"].provenance == {"source": "datasheet", "rationale": "EOL margin"}
    assert by_path["Power::$.battery.min_capacity"].provenance == {"source": "datasheet"}
    assert "Power::$.unused" not in by_path  # only inputs the target reads


# --- CLI: json ---


def test_upstream_json_structure(project: vq.Project) -> None:
    result = _run(project, "upstream", "Power::?ok", "--json", "--key", "compute_time_s")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)

    assert data["target"] == "Power::?ok"
    ids = [n["id"] for n in data["nodes"]]
    assert set(ids) == {
        "Power::$",
        "Power::@gen",
        "Power::@heat",
        "Power::@budget",
        "Power::?ok",
        "Thermal::$",
        "Thermal::?temp_ok",
    }
    assert ids.index("Power::@budget") < ids.index("Power::?ok")  # topological order
    budget = next(n for n in data["nodes"] if n["id"] == "Power::@budget")
    assert budget["kind"] == "calculation"
    assert budget["user_metadata"] == {"compute_time_s": 5.0}
    assert budget["value"] == 5.0
    assert budget["propagated"] == 25.0

    heat_edge = next(e for e in data["data_edges"] if e["source"] == "Power::$" and e["target"] == "Power::@heat")
    assert heat_edge["bindings"] == [
        {
            "param": "battery",
            "ref": "Power::$.battery",
            "leaves": ["Power::$.battery.capacity", "Power::$.battery.min_capacity"],
        },
    ]
    assert data["assume_edges"] == [{"source": "Thermal::?temp_ok", "target": "Power::@budget"}]
    assert data["aggregation"] == {
        "key": "compute_time_s",
        "combine": "max",
        "default": 0.0,
        "total": 38.0,
        "propagated": 27.0,
    }
    capacity = next(i for i in data["inputs"] if i["path"] == "Power::$.battery.capacity")
    assert capacity == {"path": "Power::$.battery.capacity", "field_metadata": {"unit": "Wh"}, "provenance": {}}
    assert data["provenance_loaded"] is False


def test_upstream_json_combine_sum_and_no_assumes(project: vq.Project) -> None:
    result = _run(project, "upstream", "Power::?ok", "--json", "--key", "compute_time_s", "--combine", "sum")
    data = json.loads(result.stdout)
    # sum recurrence over data edges: budget = 5 + (10 + 20) = 35, ok = 37 (assumed ?temp_ok is not an input)
    assert data["aggregation"]["propagated"] == 37.0

    result = _run(project, "upstream", "Power::?ok", "--json", "--key", "compute_time_s", "--no-follow-assumes")
    data = json.loads(result.stdout)
    assert "Thermal::?temp_ok" in [n["id"] for n in data["nodes"]]  # edge kept
    assert "Thermal::$" not in [n["id"] for n in data["nodes"]]  # not traversed past
    assert data["aggregation"]["propagated"] == 27.0


def test_upstream_json_with_input_provenance(project: vq.Project, tmp_path: Path) -> None:
    toml = tmp_path / "in.toml"
    toml.write_text('[Power.model]\n[Power.provenance."$.area"]\nsource = "CAD"\n')
    result = _run(project, "upstream", "Power::?ok", "--json", "-i", str(toml))
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["provenance_loaded"] is True
    area = next(i for i in data["inputs"] if i["path"] == "Power::$.area")
    assert area["provenance"] == {"source": "CAD"}


def test_upstream_uses_config_input_when_present(project: vq.Project, tmp_path: Path) -> None:
    toml = tmp_path / "in.toml"
    toml.write_text('[Power.model]\n[Power.provenance."$.area"]\nsource = "config"\n')
    result = _run(project, "upstream", "Power::?ok", "--json", config=VeriqConfig(input=toml))
    data = json.loads(result.stdout)
    assert data["provenance_loaded"] is True

    # A configured input that does not exist is skipped with a note, not an error
    result = _run(project, "upstream", "Power::?ok", "--json", config=VeriqConfig(input=tmp_path / "missing.toml"))
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["provenance_loaded"] is False
    assert "skipping provenance" in result.stderr


def test_upstream_ignores_config_input_when_project_is_given_with_path(project: vq.Project, tmp_path: Path) -> None:
    # The configured input belongs to the configured project; its provenance table does
    # not have to match a project given with -p (here it names a path this model lacks).
    toml = tmp_path / "in.toml"
    toml.write_text('[Power.provenance."$.not_in_this_model"]\nsource = "other project"\n')
    config = VeriqConfig(input=toml)

    result = _run(project, "upstream", "Power::?ok", "-p", "other.py", "--json", config=config)
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["provenance_loaded"] is False

    # An explicit -i is still honoured together with -p
    result = _run(project, "upstream", "Power::?ok", "-p", "other.py", "-i", str(toml), config=config)
    assert result.exit_code == 1
    assert "Invalid provenance" in result.stderr

    # Without -p the configured input is used, and its error is reported
    result = _run(project, "upstream", "Power::?ok", config=config)
    assert result.exit_code == 1
    assert "Invalid provenance" in result.stderr


# --- CLI: human-readable ---


def test_upstream_table_and_bindings(project: vq.Project) -> None:
    result = _run(project, "upstream", "Power::?ok", "--key", "compute_time_s", "--bindings")
    assert result.exit_code == 0, result.output
    out = result.stderr
    assert "Upstream of Power::?ok" in out
    assert "7 definitions" in out
    assert "Sequential total" in out
    assert "38" in out
    assert "critical path" in out
    assert "27" in out
    assert "battery <- Power::$.battery" in out
    assert "assumes Thermal::?temp_ok" in out
    assert "field unit: 'Wh'" in out
    assert "Pass -i/--input" in out


def test_upstream_without_key_has_no_aggregation_columns(project: vq.Project) -> None:
    result = _run(project, "upstream", "Power::?ok")
    assert result.exit_code == 0, result.output
    assert "Sequential total" not in result.stderr
    assert "Bindings" not in result.stderr


# --- CLI: errors ---


def test_upstream_unknown_definition(project: vq.Project) -> None:
    result = _run(project, "upstream", "Power::?nope")
    assert result.exit_code == 1
    assert "Definition not found" in result.stderr


def test_upstream_does_not_report_unrelated_key_error_as_missing_definition(project: vq.Project) -> None:
    with patch("veriq._cli.upstream_query.upstream_subgraph", side_effect=KeyError("boom")):
        result = _run(project, "upstream", "Power::?ok")
    assert isinstance(result.exception, KeyError)
    assert "Definition not found" not in result.stderr


def test_upstream_with_empty_root_model() -> None:
    class Empty(BaseModel): ...

    project = vq.Project(name="P")
    a = vq.Scope(name="A")
    b = vq.Scope(name="B")
    project.add_scope(a)
    project.add_scope(b)
    a.root_model(metadata={"owner": "a"})(Empty)
    b.root_model()(Env)

    @b.verification(imports=["A"])
    def ok(m: Annotated[Empty, vq.Ref("$", scope="A")], t: Annotated[float, vq.Ref("$.max_temp")]) -> bool:  # noqa: ARG001
        return t > 0

    result = _run(project, "upstream", "B::?ok", "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    nodes = {node["id"]: node for node in data["nodes"]}
    assert nodes["A::$"]["outputs"] == []
    assert nodes["A::$"]["user_metadata"] == {"owner": "a"}


def test_upstream_unknown_scope(project: vq.Project) -> None:
    result = _run(project, "upstream", "Nope::?ok")
    assert result.exit_code == 1
    assert "Unknown scope" in result.stderr


def test_upstream_non_numeric_metadata(project: vq.Project) -> None:
    project.scopes["Power"].calculations["gen"].metadata["compute_time_s"] = "slow"
    result = _run(project, "upstream", "Power::?ok", "--key", "compute_time_s")
    assert result.exit_code == 1
    assert "must be a number" in result.stderr


def test_upstream_invalid_combine(project: vq.Project) -> None:
    result = _run(project, "upstream", "Power::?ok", "--key", "k", "--combine", "avg")
    assert result.exit_code != 0


def test_upstream_missing_explicit_input(project: vq.Project, tmp_path: Path) -> None:
    result = _run(project, "upstream", "Power::?ok", "-i", str(tmp_path / "nope.toml"))
    assert result.exit_code == 1
    assert "Input file not found" in result.stderr


def test_upstream_invalid_provenance(project: vq.Project, tmp_path: Path) -> None:
    toml = tmp_path / "in.toml"
    toml.write_text('[Power.provenance."$.typo"]\nsource = "x"\n')
    result = _run(project, "upstream", "Power::?ok", "-i", str(toml))
    assert result.exit_code == 1
    assert "Invalid provenance" in result.stderr


# --- show / list expose metadata ---


def test_show_json_includes_user_and_field_metadata(project: vq.Project) -> None:
    result = _run(project, "show", "Power::$.battery.capacity", "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["user_metadata"] == {"owner": "eps"}
    assert data["field_metadata"] == {"unit": "Wh"}

    result = _run(project, "show", "Power::@budget", "--json")
    data = json.loads(result.stdout)
    assert data["user_metadata"] == {"compute_time_s": 5.0}
    assert data["field_metadata"] == {}


def test_show_renders_metadata_sections(project: vq.Project) -> None:
    result = _run(project, "show", "Power::$.battery.capacity")
    assert result.exit_code == 0, result.output
    assert "User Metadata:" in result.stderr
    assert "owner: 'eps'" in result.stderr
    assert "Field Metadata:" in result.stderr
    assert "unit: 'Wh'" in result.stderr


def test_list_json_includes_user_metadata(project: vq.Project) -> None:
    result = _run(project, "list", "--json", "--kind", "calc")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    by_path = {n["path"]: n for n in data}
    assert by_path["Power::@gen"]["user_metadata"] == {"compute_time_s": 10.0}


def test_list_json_serializes_non_json_metadata(project: vq.Project) -> None:
    project.scopes["Power"].calculations["gen"].metadata["type"] = float  # not JSON-serializable
    result = _run(project, "list", "--json", "--kind", "calc")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert "float" in {n["path"]: n for n in data}["Power::@gen"]["user_metadata"]["type"]
