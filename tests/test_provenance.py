"""Tests for per-field metadata (vq.Meta) and input-TOML provenance."""

import subprocess
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated

import jsonschema
import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._ir import NodeKind, build_graph_spec
from veriq._path import ModelPath, ProjectPath, parse_project_path
from veriq._provenance import build_provenance_model, collect_field_metadata, strip_provenance

if TYPE_CHECKING:
    from pathlib import Path


class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"


class Phase(StrEnum):
    LAUNCH = "launch"
    ORBIT = "orbit"


class Battery(BaseModel):
    capacity: Annotated[float, vq.Meta({"unit": "Wh"})]
    min_capacity: float


class Design(BaseModel):
    battery: Annotated[Battery, vq.Meta(owner="power-team", unit="Ah")]
    area: Annotated[float, vq.Meta({"source_doc": "SP-001"})]
    plain: float
    power: Annotated[vq.Table[Mode, Annotated[float, vq.Meta(unit="W")]], vq.Meta(owner="eps")]
    matrix: vq.Table[tuple[Phase, Mode], float]


def _make_project() -> vq.Project:
    project = vq.Project(name="P")
    scope = vq.Scope(name="Power")
    project.add_scope(scope)
    scope.root_model()(Design)

    other = vq.Scope(name="Thermal")
    project.add_scope(other)

    @other.root_model()
    class ThermalModel(BaseModel):
        temp: float

    return project


def _mp(scope: str, path: str) -> ProjectPath:
    return parse_project_path(f"{scope}::{path}")


# =============================================================================
# Code side: vq.Meta
# =============================================================================


def test_meta_accepts_mapping_and_kwargs_and_copies() -> None:
    src = {"a": 1}
    meta = vq.Meta(src, b=2)
    src["a"] = 99
    assert meta.data == {"a": 1, "b": 2}
    assert vq.Meta().data == {}


def test_collect_field_metadata_inherits_and_overrides() -> None:
    by_leaf = collect_field_metadata(Design)
    leaf = ModelPath.parse

    # Leaf-level Meta overrides the nested-model Meta for the same key, other keys inherited
    assert by_leaf[leaf("$.battery.capacity").parts] == {"owner": "power-team", "unit": "Wh"}
    # Sibling without own Meta inherits from the nested-model field
    assert by_leaf[leaf("$.battery.min_capacity").parts] == {"owner": "power-team", "unit": "Ah"}
    assert by_leaf[leaf("$.area").parts] == {"source_doc": "SP-001"}
    # Fields without any Meta along their path are omitted
    assert leaf("$.plain").parts not in by_leaf
    assert leaf("$.matrix[launch,nominal]").parts not in by_leaf


def test_collect_field_metadata_table_value_meta_applies_to_items() -> None:
    by_leaf = collect_field_metadata(Design)
    leaf = ModelPath.parse
    assert by_leaf[leaf("$.power").parts] == {"owner": "eps", "unit": "W"}
    assert by_leaf[leaf("$.power[nominal]").parts] == {"owner": "eps", "unit": "W"}
    assert by_leaf[leaf("$.power[safe]").parts] == {"owner": "eps", "unit": "W"}


def test_node_spec_field_metadata_separate_from_user_metadata() -> None:
    project = vq.Project(name="P")
    scope = vq.Scope(name="Power")
    project.add_scope(scope)
    scope.root_model(metadata={"team": "eps"})(Design)

    spec = build_graph_spec(project)
    cap = spec.get_node(_mp("Power", "$.battery.capacity"))
    plain = spec.get_node(_mp("Power", "$.plain"))

    assert cap.kind == NodeKind.MODEL
    assert cap.field_metadata == {"owner": "power-team", "unit": "Wh"}
    assert plain.field_metadata == {}
    # user_metadata is the root model's shared dict, untouched by vq.Meta
    assert cap.user_metadata == {"team": "eps"}
    assert cap.user_metadata is plain.user_metadata


def test_non_model_nodes_have_empty_field_metadata() -> None:
    project = _make_project()
    scope = project.scopes["Power"]

    @scope.calculation()
    def double(area: Annotated[float, vq.Ref("$.area")]) -> float:
        return area * 2

    spec = build_graph_spec(project)
    assert spec.get_node(_mp("Power", "@double")).field_metadata == {}


# =============================================================================
# Input-TOML side: provenance table
# =============================================================================


def test_toml_to_provenance_leaf_and_inheritance() -> None:
    project = _make_project()
    toml = {
        "Power": {
            "model": {},
            "provenance": {
                "$.battery": {"source": "datasheet rev.C"},
                "$.battery.capacity": {"rationale": "20% EOL margin", "source": "test report"},
                "$.area": {"rationale": "deployable panel baseline"},
            },
        },
    }
    prov = vq.toml_to_provenance(project, toml)

    assert prov[_mp("Power", "$.battery.capacity")] == {"source": "test report", "rationale": "20% EOL margin"}
    assert prov[_mp("Power", "$.battery.min_capacity")] == {"source": "datasheet rev.C"}
    assert prov[_mp("Power", "$.area")] == {"rationale": "deployable panel baseline"}
    assert _mp("Power", "$.plain") not in prov
    assert not any(p.scope == "Thermal" for p in prov)


def test_toml_to_provenance_inheritance_does_not_depend_on_entry_order() -> None:
    project = _make_project()
    provenance = {
        "$.battery.capacity": {"source": "test report"},
        "$.battery": {"source": "datasheet rev.C"},
        "$": {"source": "PDR", "baseline": "PDR"},
    }
    prov = vq.toml_to_provenance(project, {"Power": {"provenance": provenance}})

    assert prov[_mp("Power", "$.battery.capacity")] == {"source": "test report", "baseline": "PDR"}
    assert prov[_mp("Power", "$.battery.min_capacity")] == {"source": "datasheet rev.C", "baseline": "PDR"}
    assert prov[_mp("Power", "$.plain")] == {"source": "PDR", "baseline": "PDR"}


def test_toml_to_provenance_table_keys_single_and_multi() -> None:
    project = _make_project()
    toml = {
        "Power": {
            "provenance": {
                "$.power": {"source": "budget v3"},
                "$.power[safe]": {"rationale": "heaters off"},
                "$.matrix[launch,nominal]": {"note": "n/a during launch"},
            },
        },
    }
    prov = vq.toml_to_provenance(project, toml)

    assert prov[_mp("Power", "$.power")] == {"source": "budget v3"}
    assert prov[_mp("Power", "$.power[nominal]")] == {"source": "budget v3"}
    assert prov[_mp("Power", "$.power[safe]")] == {"source": "budget v3", "rationale": "heaters off"}
    assert prov[_mp("Power", "$.matrix[launch,nominal]")] == {"note": "n/a during launch"}
    assert _mp("Power", "$.matrix[orbit,nominal]") not in prov


def test_toml_to_provenance_root_level_metadata_applies_to_all_leaves() -> None:
    project = _make_project()
    prov = vq.toml_to_provenance(project, {"Thermal": {"provenance": {"$": {"baseline": "PDR"}}}})
    assert prov == {_mp("Thermal", "$.temp"): {"baseline": "PDR"}}


def test_toml_to_provenance_metadata_key_may_equal_a_field_name() -> None:
    """Paths and metadata keys live in separate namespaces, so a field name is a valid metadata key."""
    project = _make_project()
    provenance = {
        "$": {"area": "whole design", "battery": "see EPS-ICD-001"},
        "$.battery": {"capacity": "sized for eclipse"},
    }
    prov = vq.toml_to_provenance(project, {"Power": {"provenance": provenance}})

    assert prov[_mp("Power", "$.area")] == {"area": "whole design", "battery": "see EPS-ICD-001"}
    assert prov[_mp("Power", "$.battery.capacity")] == {
        "area": "whole design",
        "battery": "see EPS-ICD-001",
        "capacity": "sized for eclipse",
    }


def test_toml_to_provenance_absent_or_empty() -> None:
    project = _make_project()
    assert vq.toml_to_provenance(project, {"Power": {"model": {}}}) == {}
    assert vq.toml_to_provenance(project, {"Power": {"provenance": {}}}) == {}
    assert vq.toml_to_provenance(project, {"Power": {"provenance": {"$.area": {}}}}) == {}
    # Scopes unknown to the project are ignored, like model data
    assert vq.toml_to_provenance(project, {"Nope": {"provenance": {"x": {"y": 1}}}}) == {}


@pytest.mark.parametrize(
    ("provenance", "match"),
    [
        ({"$.batery": {"source": "typo"}}, r"Power::\$\.batery' does not exist"),
        ({"$.battery.capacitty": {"source": "typo"}}, r"Power::\$\.battery\.capacitty' does not exist"),
        ({"$.power[mission]": {"source": "no such key"}}, r"Power::\$\.power\[mission\]' does not exist"),
        ({"$.power.safe": {"source": "table keys use brackets"}}, r"Power::\$\.power\.safe' does not exist"),
        ({"$.area.unit": {"source": "below a leaf"}}, r"Power::\$\.area\.unit' does not exist"),
        ({"$.matrix[launch": {"source": "unbalanced"}}, r"Power::\$\.matrix\[launch' does not exist"),
        # Bare names are not paths; this is also what a file in the former nested layout looks like
        ({"battery": {"source": "x"}}, r"'battery' of scope 'Power' is not a model path"),
        ({"baseline": "PDR"}, r"'baseline' of scope 'Power' is not a model path"),
        ({"@calc": {"source": "x"}}, r"'@calc' of scope 'Power' is not a model path"),
        # Only the spelling that veriq prints is accepted, so that one path has one entry
        ({"$.matrix[launch, nominal]": {"note": "x"}}, r'must be written as "\$\.matrix\[launch,nominal\]"'),
        ({" $.area": {"note": "x"}}, r"' \$\.area' of scope 'Power' is not a model path"),
        ({"$.area ": {"note": "x"}}, r'must be written as "\$\.area"'),
        ({"$.battery": "not a table"}, r"'Power::\$\.battery' must be a table of metadata, got str"),
        ({"$": 1}, r"'Power::\$' must be a table of metadata, got int"),
    ],
)
def test_toml_to_provenance_invalid_entry_is_error(provenance: dict, match: str) -> None:
    project = _make_project()
    with pytest.raises(vq.ProvenanceError, match=match):
        vq.toml_to_provenance(project, {"Power": {"provenance": provenance}})


def test_toml_to_provenance_table_valued_metadata_is_allowed() -> None:
    project = _make_project()
    review = {"board": "PDR", "actions": [{"id": 12, "closed": True}]}
    prov = vq.toml_to_provenance(project, {"Power": {"provenance": {"$.area": {"review": review}}}})
    assert prov == {_mp("Power", "$.area"): {"review": review}}


def test_toml_to_provenance_table_under_a_path_is_metadata_not_a_sub_path() -> None:
    """Only the keys of the provenance table are paths; a table below an entry is metadata, whatever its name."""
    project = _make_project()
    provenance = {"$.battery": {"capacity": {"rationale": "this describes $.battery"}}}
    prov = vq.toml_to_provenance(project, {"Power": {"provenance": provenance}})

    expected = {"capacity": {"rationale": "this describes $.battery"}}
    assert prov[_mp("Power", "$.battery.capacity")] == expected
    assert prov[_mp("Power", "$.battery.min_capacity")] == expected


def test_toml_to_provenance_table_valued_metadata_is_replaced_not_merged() -> None:
    project = _make_project()
    provenance = {
        "$.battery": {"review": {"board": "PDR", "status": "open"}, "source": "datasheet"},
        "$.battery.capacity": {"review": {"board": "CDR"}},
    }
    prov = vq.toml_to_provenance(project, {"Power": {"provenance": provenance}})

    assert prov[_mp("Power", "$.battery.capacity")] == {"review": {"board": "CDR"}, "source": "datasheet"}
    assert prov[_mp("Power", "$.battery.min_capacity")] == {
        "review": {"board": "PDR", "status": "open"},
        "source": "datasheet",
    }


def test_toml_to_provenance_array_metadata_is_allowed() -> None:
    project = _make_project()
    prov = vq.toml_to_provenance(project, {"Power": {"provenance": {"$.area": {"refs": ["A", "B"]}}}})
    assert prov == {_mp("Power", "$.area"): {"refs": ["A", "B"]}}


def test_toml_to_provenance_non_table_provenance_is_error() -> None:
    project = _make_project()
    with pytest.raises(vq.ProvenanceError, match="must be a table"):
        vq.toml_to_provenance(project, {"Power": {"provenance": "oops"}})


def test_load_provenance_from_toml(tmp_path: Path) -> None:
    project = _make_project()
    toml_file = tmp_path / "in.toml"
    toml_file.write_text(
        """
[Power.model]

[Power.provenance]
"$" = { baseline = "PDR" }
"$.power[safe]" = { rationale = "heaters off" }

[Power.provenance."$.battery"]
source = "datasheet"

[Power.provenance."$.battery.capacity"]
rationale = "margin"
""",
    )
    prov = vq.load_provenance_from_toml(project, toml_file)
    assert prov[_mp("Power", "$.battery.capacity")] == {
        "baseline": "PDR",
        "source": "datasheet",
        "rationale": "margin",
    }
    assert prov[_mp("Power", "$.battery.min_capacity")] == {"baseline": "PDR", "source": "datasheet"}
    assert prov[_mp("Power", "$.power[safe]")] == {"baseline": "PDR", "rationale": "heaters off"}


def test_strip_provenance() -> None:
    toml = {"Power": {"model": {"a": 1}, "provenance": {"$.a": {"s": 1}}}, "Thermal": {"model": {}}}
    assert strip_provenance(toml) == {"Power": {"model": {"a": 1}}, "Thermal": {"model": {}}}
    assert "provenance" in toml["Power"]  # original untouched


# =============================================================================
# JSON schema
# =============================================================================


def test_input_model_default_excludes_provenance() -> None:
    project = _make_project()
    plain = project.input_model().model_json_schema()
    with_prov = project.input_model(include_provenance=True).model_json_schema()
    assert "provenance" not in plain["$defs"]["PowerInput"]["properties"]
    assert "provenance" in with_prov["$defs"]["PowerInput"]["properties"]
    assert "model" in with_prov["$defs"]["PowerInput"]["required"]
    assert "provenance" not in with_prov["$defs"]["PowerInput"].get("required", [])


def _valid_input_with_provenance() -> dict:
    return {
        "Power": {
            "model": {
                "battery": {"capacity": 1.0, "min_capacity": 0.5},
                "area": 1.0,
                "plain": 1.0,
                "power": {"nominal": 1.0, "safe": 1.0},
                "matrix": {
                    "launch,nominal": 1.0,
                    "launch,safe": 1.0,
                    "orbit,nominal": 1.0,
                    "orbit,safe": 1.0,
                },
            },
            "provenance": {
                "$": {"source": "root-level"},
                "$.battery": {"source": "x", "area": "a metadata key named like a field"},
                "$.battery.capacity": {"rationale": "y", "refs": ["A", "B"], "review": {"board": "PDR"}},
                "$.power[safe]": {"note": "z"},
                "$.matrix[launch,nominal]": {"note": "w"},
            },
        },
        "Thermal": {"model": {"temp": 1.0}},
    }


def test_provenance_json_schema_validates_structure() -> None:
    project = _make_project()
    schema = project.input_model(include_provenance=True).model_json_schema()

    valid = _valid_input_with_provenance()
    jsonschema.validate(valid, schema)

    # provenance is optional
    without = _valid_input_with_provenance()
    del without["Power"]["provenance"]
    jsonschema.validate(without, schema)


@pytest.mark.parametrize(
    "provenance",
    [
        {"$.battery": "not a table"},
        {"$.batery": {"source": "typo"}},
        {"battery": {"source": "not a path"}},
        {"source": "metadata outside a path entry"},
        {"$.power[mission]": {"source": "no such key"}},
    ],
)
def test_provenance_json_schema_rejects_what_the_loader_rejects(provenance: dict) -> None:
    project = _make_project()
    schema = project.input_model(include_provenance=True).model_json_schema()
    data = _valid_input_with_provenance()
    data["Power"]["provenance"] = provenance

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema)
    with pytest.raises(vq.ProvenanceError):
        vq.toml_to_provenance(project, data)


def test_provenance_json_schema_lists_every_model_path() -> None:
    schema = build_provenance_model(Design, "DesignProvenance").model_json_schema()

    assert schema["additionalProperties"] is False
    assert "required" not in schema
    assert list(schema["properties"]) == [
        "$",
        "$.battery",
        "$.battery.capacity",
        "$.battery.min_capacity",
        "$.area",
        "$.plain",
        "$.power",
        "$.power[nominal]",
        "$.power[safe]",
        "$.matrix",
        "$.matrix[launch,nominal]",
        "$.matrix[launch,safe]",
        "$.matrix[orbit,nominal]",
        "$.matrix[orbit,safe]",
    ]
    assert schema["properties"]["$.area"]["type"] == "object"


def test_build_provenance_model_entries_are_free_form() -> None:
    model = build_provenance_model(Design, "DesignProvenance")
    data = {"$": {"free": 1}, "$.area": {"anything": [1, 2], "nested": {"table": True}}}
    instance = model.model_validate(data)
    assert instance.model_dump(exclude_defaults=True) == data


# =============================================================================
# CLI integration
# =============================================================================

CLI_PROJECT_CODE = """
from typing import Annotated

from pydantic import BaseModel

import veriq as vq


class Design(BaseModel):
    voltage: float
    capacity: float = 100.0


project = vq.Project(name="TestProject")
scope = vq.Scope(name="Power")
project.add_scope(scope)
scope.root_model()(Design)


@scope.verification()
def voltage_ok(voltage: Annotated[float, vq.Ref("$.voltage")]) -> bool:
    return voltage > 0
"""

CLI_INPUT_TOML = """[Power.model]
voltage = 3.3  # bus voltage

[Power.provenance]
"$" = { baseline = "PDR" }  # applies to every input of the scope

[Power.provenance."$.voltage"]
source = "EPS-ICD-001"
"""


def _run_veriq(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["uv", "run", "veriq", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_update_preserves_provenance_without_warning(tmp_path: Path) -> None:
    project_file = tmp_path / "project.py"
    project_file.write_text(CLI_PROJECT_CODE)
    input_file = tmp_path / "input.toml"
    input_file.write_text(CLI_INPUT_TOML)

    result = _run_veriq("update", str(project_file), "-i", str(input_file))

    assert result.returncode == 0, result.stderr
    assert "provenance" not in result.stderr  # no "no longer exists" warning for the reserved table
    updated = input_file.read_text()
    assert "capacity = " in updated  # new field added with a generated default
    assert '[Power.provenance]\n"$" = { baseline = "PDR" }  # applies to every input of the scope' in updated
    assert '[Power.provenance."$.voltage"]\nsource = "EPS-ICD-001"' in updated

    check = _run_veriq("update", str(project_file), "-i", str(input_file), "--check")
    assert check.returncode == 0, check.stderr


def test_cli_calc_rejects_unknown_provenance_path(tmp_path: Path) -> None:
    project_file = tmp_path / "project.py"
    project_file.write_text(CLI_PROJECT_CODE)
    input_file = tmp_path / "input.toml"
    input_file.write_text(CLI_INPUT_TOML + '\n[Power.provenance."$.voltag"]\nsource = "typo"\n')
    output_file = tmp_path / "output.toml"

    result = _run_veriq("calc", str(project_file), "-i", str(input_file), "-o", str(output_file))

    assert result.returncode == 1
    assert "Invalid provenance" in result.stderr
    assert "Power::$.voltag" in result.stderr
    assert not output_file.exists()


def test_cli_calc_accepts_valid_provenance(tmp_path: Path) -> None:
    project_file = tmp_path / "project.py"
    project_file.write_text(CLI_PROJECT_CODE)
    input_file = tmp_path / "input.toml"
    input_file.write_text(CLI_INPUT_TOML)
    output_file = tmp_path / "output.toml"

    result = _run_veriq("calc", str(project_file), "-i", str(input_file), "-o", str(output_file), "--verify")

    assert result.returncode == 0, result.stderr
    assert output_file.is_file()
