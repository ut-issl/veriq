"""Tests for graph query CLI commands."""

from typing import Annotated

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._cli.graph_query import (
    NodeInfo,
    NonLeafPathError,
    ScopeSummary,
    get_available_scopes,
    get_dependency_tree,
    get_node_detail,
    get_scope_summaries,
    list_nodes,
)
from veriq._ir import NodeKind
from veriq._path import CalcPath, ModelPath, ProjectPath, VerificationPath, parse_project_path

# --- Fixtures ---


@pytest.fixture
def simple_project() -> vq.Project:
    """Create a simple project for testing."""
    project = vq.Project("TestProject")
    scope_a = vq.Scope("ScopeA")
    scope_b = vq.Scope("ScopeB")
    project.add_scope(scope_a)
    project.add_scope(scope_b)

    @scope_a.root_model()
    class ModelA(BaseModel):
        value: float
        factor: float

    @scope_a.calculation()
    def calc_result(
        value: Annotated[float, vq.Ref("$.value")],
        factor: Annotated[float, vq.Ref("$.factor")],
    ) -> float:
        return value * factor

    @scope_a.verification()
    def verify_positive(
        result: Annotated[float, vq.Ref("@calc_result")],
    ) -> bool:
        return result > 0

    @scope_b.root_model()
    class ModelB(BaseModel):
        threshold: float

    @scope_b.verification(imports=["ScopeA"])
    def verify_threshold(
        result: Annotated[float, vq.Ref("@calc_result", scope="ScopeA")],
        threshold: Annotated[float, vq.Ref("$.threshold")],
    ) -> bool:
        return result > threshold

    return project


# --- parse_project_path tests ---


class TestParseProjectPath:
    def test_parse_model_path(self) -> None:
        result = parse_project_path("Power::$.design.battery")
        assert result.scope == "Power"
        assert isinstance(result.path, ModelPath)
        assert str(result) == "Power::$.design.battery"

    def test_parse_calc_path(self) -> None:
        result = parse_project_path("Thermal::@calculate_temperature")
        assert result.scope == "Thermal"
        assert isinstance(result.path, CalcPath)
        assert result.path.calc_name == "calculate_temperature"

    def test_parse_verification_path(self) -> None:
        result = parse_project_path("Power::?verify_battery")
        assert result.scope == "Power"
        assert isinstance(result.path, VerificationPath)
        assert result.path.verification_name == "verify_battery"

    def test_parse_path_with_table_key(self) -> None:
        result = parse_project_path("Power::$.table[nominal]")
        assert result.scope == "Power"
        assert str(result) == "Power::$.table[nominal]"

    def test_invalid_format_no_separator(self) -> None:
        with pytest.raises(ValueError, match="Invalid path format"):
            parse_project_path("invalid_path")

    def test_invalid_format_empty_scope(self) -> None:
        with pytest.raises(ValueError, match="Scope name cannot be empty"):
            parse_project_path("::$.path")

    def test_invalid_format_empty_path(self) -> None:
        with pytest.raises(ValueError, match="Path cannot be empty"):
            parse_project_path("Scope::")


# --- get_scope_summaries tests ---


class TestGetScopeSummaries:
    def test_returns_all_scopes(self, simple_project: vq.Project) -> None:
        summaries = get_scope_summaries(simple_project)
        scope_names = [s.name for s in summaries]
        assert "ScopeA" in scope_names
        assert "ScopeB" in scope_names

    def test_summary_counts(self, simple_project: vq.Project) -> None:
        summaries = get_scope_summaries(simple_project)
        scope_a = next(s for s in summaries if s.name == "ScopeA")

        # ScopeA has: 2 model fields, 1 calc, 1 verification
        assert scope_a.model_count == 2
        assert scope_a.calc_count == 1
        assert scope_a.verification_count == 1

    def test_returns_scope_summary_type(self, simple_project: vq.Project) -> None:
        summaries = get_scope_summaries(simple_project)
        assert all(isinstance(s, ScopeSummary) for s in summaries)


# --- list_nodes tests ---


class TestListNodes:
    def test_list_all_nodes(self, simple_project: vq.Project) -> None:
        nodes = list_nodes(simple_project)
        assert len(nodes) > 0
        assert all(isinstance(n, NodeInfo) for n in nodes)

    def test_filter_by_kind_model(self, simple_project: vq.Project) -> None:
        nodes = list_nodes(simple_project, kinds=[NodeKind.MODEL])
        assert all(n.kind == NodeKind.MODEL for n in nodes)

    def test_filter_by_kind_calculation(self, simple_project: vq.Project) -> None:
        nodes = list_nodes(simple_project, kinds=[NodeKind.CALCULATION])
        assert all(n.kind == NodeKind.CALCULATION for n in nodes)
        assert len(nodes) == 1  # calc_result

    def test_filter_by_kind_verification(self, simple_project: vq.Project) -> None:
        nodes = list_nodes(simple_project, kinds=[NodeKind.VERIFICATION])
        assert all(n.kind == NodeKind.VERIFICATION for n in nodes)
        assert len(nodes) == 2  # verify_positive, verify_threshold

    def test_filter_by_scope(self, simple_project: vq.Project) -> None:
        nodes = list_nodes(simple_project, scopes=["ScopeA"])
        assert all(n.path.scope == "ScopeA" for n in nodes)

    def test_filter_by_multiple_scopes(self, simple_project: vq.Project) -> None:
        nodes = list_nodes(simple_project, scopes=["ScopeA", "ScopeB"])
        scopes = {n.path.scope for n in nodes}
        assert scopes == {"ScopeA", "ScopeB"}

    def test_filter_leaves_only(self, simple_project: vq.Project) -> None:
        nodes = list_nodes(simple_project, leaves_only=True)
        # Verifications are typically leaves
        kinds = {n.kind for n in nodes}
        assert NodeKind.VERIFICATION in kinds

    def test_combined_filters(self, simple_project: vq.Project) -> None:
        nodes = list_nodes(
            simple_project,
            kinds=[NodeKind.VERIFICATION],
            scopes=["ScopeA"],
        )
        assert len(nodes) == 1
        assert nodes[0].path.scope == "ScopeA"
        assert nodes[0].kind == NodeKind.VERIFICATION


# --- get_node_detail tests ---


class TestGetNodeDetail:
    def test_get_calculation_detail(self, simple_project: vq.Project) -> None:
        path = ProjectPath("ScopeA", CalcPath.parse("@calc_result"))
        detail = get_node_detail(simple_project, path)

        assert detail.kind == NodeKind.CALCULATION
        assert detail.path.scope == "ScopeA"
        assert len(detail.direct_dependencies) == 2  # value, factor
        assert len(detail.direct_dependents) > 0  # verify_positive, verify_threshold

    def test_get_model_detail(self, simple_project: vq.Project) -> None:
        path = ProjectPath("ScopeA", ModelPath.parse("$.value"))
        detail = get_node_detail(simple_project, path)

        assert detail.kind == NodeKind.MODEL
        assert len(detail.direct_dependencies) == 0  # Models have no deps
        assert len(detail.direct_dependents) > 0  # calc_result depends on it

    def test_get_verification_detail(self, simple_project: vq.Project) -> None:
        path = ProjectPath("ScopeA", VerificationPath.parse("?verify_positive"))
        detail = get_node_detail(simple_project, path)

        assert detail.kind == NodeKind.VERIFICATION
        assert len(detail.direct_dependencies) > 0  # depends on calc_result

    def test_node_not_found(self, simple_project: vq.Project) -> None:
        path = ProjectPath("ScopeA", ModelPath.parse("$.nonexistent"))
        with pytest.raises(KeyError, match="Node not found"):
            get_node_detail(simple_project, path)

    def test_non_leaf_path_raises_error(self, simple_project: vq.Project) -> None:
        # $.value exists but $ (root) is a non-leaf path with multiple outputs
        path = ProjectPath("ScopeA", ModelPath.parse("$"))
        with pytest.raises(NonLeafPathError) as exc_info:
            get_node_detail(simple_project, path)

        # Should contain the leaf paths
        assert len(exc_info.value.leaf_paths) == 2  # value and factor
        leaf_strs = [str(p) for p in exc_info.value.leaf_paths]
        assert "ScopeA::$.value" in leaf_strs
        assert "ScopeA::$.factor" in leaf_strs


# --- get_dependency_tree tests ---


class TestGetDependencyTree:
    def test_tree_shows_dependencies(self, simple_project: vq.Project) -> None:
        path = ProjectPath("ScopeA", VerificationPath.parse("?verify_positive"))
        tree = get_dependency_tree(simple_project, path, invert=False)

        assert tree.path == path
        # verify_positive depends on calc_result
        child_paths = [c.path for c in tree.children]
        calc_paths = [p for p in child_paths if isinstance(p.path, CalcPath)]
        assert len(calc_paths) > 0

    def test_tree_shows_reverse_dependencies(self, simple_project: vq.Project) -> None:
        path = ProjectPath("ScopeA", CalcPath.parse("@calc_result"))
        tree = get_dependency_tree(simple_project, path, invert=True)

        assert tree.path == path
        # calc_result is depended on by verify_positive and verify_threshold
        child_paths = [c.path for c in tree.children]
        verif_paths = [p for p in child_paths if isinstance(p.path, VerificationPath)]
        assert len(verif_paths) >= 1

    def test_tree_respects_max_depth(self, simple_project: vq.Project) -> None:
        path = ProjectPath("ScopeA", VerificationPath.parse("?verify_positive"))
        tree = get_dependency_tree(simple_project, path, invert=False, max_depth=1)

        # With depth 1, just verify it doesn't error
        assert tree.path == path

    def test_tree_node_not_found(self, simple_project: vq.Project) -> None:
        path = ProjectPath("ScopeA", ModelPath.parse("$.nonexistent"))
        with pytest.raises(KeyError, match="Node not found"):
            get_dependency_tree(simple_project, path)


# --- get_available_scopes tests ---


class TestGetAvailableScopes:
    def test_returns_all_scope_names(self, simple_project: vq.Project) -> None:
        scopes = get_available_scopes(simple_project)
        assert "ScopeA" in scopes
        assert "ScopeB" in scopes
        assert len(scopes) == 2
