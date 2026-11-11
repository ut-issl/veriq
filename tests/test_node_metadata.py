"""Tests for user-defined metadata on graph nodes."""

from typing import Annotated

from pydantic import BaseModel

import veriq as vq
from veriq._eval import evaluate_project
from veriq._ir import NodeKind, build_graph_spec
from veriq._path import CalcPath, ProjectPath, VerificationPath


class Inner(BaseModel):
    a: float
    b: float


def _make_project(
    *,
    model_metadata: dict | None = None,
    calc_metadata: dict | None = None,
    verif_metadata: dict | None = None,
) -> vq.Project:
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="S")
    project.add_scope(scope)

    @scope.root_model(metadata=model_metadata)
    class Model(BaseModel):
        x: float
        y: float

    @scope.calculation(metadata=calc_metadata)
    def calc(x: Annotated[float, vq.Ref("$.x")], y: Annotated[float, vq.Ref("$.y")]) -> Inner:
        return Inner(a=x, b=y)

    @scope.verification(metadata=verif_metadata)
    def verif(a: Annotated[float, vq.Ref("@calc.a")]) -> bool:
        return a > 0

    return project


def test_defaults_to_empty_dict() -> None:
    """Without `metadata=`, every definition and every node carries an empty dict, never None."""
    project = _make_project()
    scope = project.scopes["S"]

    assert scope.root_model_metadata == {}
    assert scope.calculations["calc"].metadata == {}
    assert scope.verifications["verif"].metadata == {}

    spec = build_graph_spec(project)
    assert all(node.user_metadata == {} for node in spec.nodes.values())


def test_root_model_metadata_on_all_model_leaves() -> None:
    """A root model expands to one node per field; all of them refer to the scope's one dict."""
    project = _make_project(model_metadata={"owner": "power-team"})
    scope = project.scopes["S"]
    assert scope.root_model_metadata == {"owner": "power-team"}
    # The model class itself is not modified.
    assert not hasattr(scope.get_root_model(), "metadata")

    spec = build_graph_spec(project)
    model_nodes = spec.get_nodes_by_kind(NodeKind.MODEL)
    assert len(model_nodes) == 2
    assert all(node.user_metadata == {"owner": "power-team"} for node in model_nodes)
    # Leaves expanded from one definition share the same dict.
    assert model_nodes[0].user_metadata is model_nodes[1].user_metadata


def test_calculation_metadata_shared_across_output_leaves() -> None:
    """A calculation returning a model expands to one node per field; all refer to its one dict."""
    project = _make_project(calc_metadata={"compute_time_s": 120.0})
    assert project.scopes["S"].calculations["calc"].metadata == {"compute_time_s": 120.0}

    spec = build_graph_spec(project)
    calc_nodes = spec.get_nodes_by_kind(NodeKind.CALCULATION)
    assert len(calc_nodes) == 2  # @calc.a and @calc.b
    assert all(node.user_metadata == {"compute_time_s": 120.0} for node in calc_nodes)
    assert calc_nodes[0].user_metadata is calc_nodes[1].user_metadata


def test_verification_metadata() -> None:
    project = _make_project(verif_metadata={"compute_time_s": 5.0})
    assert project.scopes["S"].verifications["verif"].metadata == {"compute_time_s": 5.0}

    spec = build_graph_spec(project)
    verif_node = spec.get_node(ProjectPath(scope="S", path=VerificationPath(root="?verif", parts=())))
    assert verif_node.user_metadata == {"compute_time_s": 5.0}


def test_metadata_is_shallow_copied_at_registration() -> None:
    model_md = {"k": 1}
    calc_md = {"k": 2}
    verif_md = {"k": 3}
    project = _make_project(model_metadata=model_md, calc_metadata=calc_md, verif_metadata=verif_md)

    model_md["k"] = 10
    calc_md["k"] = 20
    verif_md["new"] = 30

    scope = project.scopes["S"]
    assert scope.root_model_metadata == {"k": 1}
    assert scope.calculations["calc"].metadata == {"k": 2}
    assert scope.verifications["verif"].metadata == {"k": 3}


def test_user_metadata_does_not_collide_with_internal_metadata() -> None:
    project = _make_project(
        calc_metadata={"root_output_type": "user-value", "assumed_verification_paths": ["user"]},
        verif_metadata={"xfail": True},
    )
    spec = build_graph_spec(project)

    calc_node = spec.get_node(ProjectPath(scope="S", path=CalcPath.parse("@calc.a")))
    assert calc_node.metadata["root_output_type"] is Inner
    assert "assumed_verification_paths" not in calc_node.metadata
    assert calc_node.user_metadata["root_output_type"] == "user-value"

    verif_node = spec.get_node(ProjectPath(scope="S", path=VerificationPath(root="?verif", parts=())))
    assert verif_node.metadata["xfail"] is False
    assert verif_node.user_metadata == {"xfail": True}
    assert project.scopes["S"].verifications["verif"].xfail is False


def test_user_xfail_key_does_not_affect_evaluation() -> None:
    project = _make_project(verif_metadata={"xfail": True})
    model_cls = project.scopes["S"].get_root_model()

    result = evaluate_project(project, {"S": model_cls.model_validate({"x": -1.0, "y": 0.0})})

    verif_path = ProjectPath(scope="S", path=VerificationPath(root="?verif", parts=()))
    assert result.get_value(verif_path) is False
    assert project.scopes["S"].verifications["verif"].xfail is False
