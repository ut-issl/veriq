"""Tests for the Intermediate Representation (IR) module."""

from typing import Annotated

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._ir import GraphSpec, NodeKind, NodeSpec, build_graph_spec
from veriq._path import AttributePart, CalcPath, ModelPath, ProjectPath

# =============================================================================
# Tests for NodeSpec
# =============================================================================


def test_node_spec_model_node_is_input() -> None:
    node = NodeSpec(
        id=ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),))),
        kind=NodeKind.MODEL,
        dependencies=frozenset(),
        output_type=float,
    )
    assert node.is_input() is True


def test_node_spec_calculation_node_is_not_input() -> None:
    model_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
    node = NodeSpec(
        id=ProjectPath(scope="Test", path=CalcPath(root="@calc", parts=())),
        kind=NodeKind.CALCULATION,
        dependencies=frozenset({model_path}),
        output_type=float,
    )
    assert node.is_input() is False


def test_node_spec_is_hashable() -> None:
    node = NodeSpec(
        id=ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),))),
        kind=NodeKind.MODEL,
        dependencies=frozenset(),
        output_type=float,
    )
    # Should be hashable (for use in sets/dicts)
    assert hash(node) == hash(node.id)


def test_node_spec_is_frozen() -> None:
    node = NodeSpec(
        id=ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),))),
        kind=NodeKind.MODEL,
        dependencies=frozenset(),
        output_type=float,
    )
    with pytest.raises(AttributeError):
        node.kind = NodeKind.CALCULATION  # type: ignore[misc]


# =============================================================================
# Tests for GraphSpec
# =============================================================================


def test_graph_spec_empty() -> None:
    spec = GraphSpec()
    assert len(spec) == 0
    assert spec.scope_names == ()


def test_graph_spec_get_node() -> None:
    path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
    node = NodeSpec(
        id=path,
        kind=NodeKind.MODEL,
        dependencies=frozenset(),
        output_type=float,
    )
    spec = GraphSpec(nodes={path: node})
    assert spec.get_node(path) is node


def test_graph_spec_get_node_not_found() -> None:
    spec = GraphSpec()
    path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
    with pytest.raises(KeyError):
        spec.get_node(path)


def test_graph_spec_get_nodes_by_kind() -> None:
    model_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
    calc_path = ProjectPath(scope="Test", path=CalcPath(root="@calc", parts=()))

    model_node = NodeSpec(
        id=model_path,
        kind=NodeKind.MODEL,
        dependencies=frozenset(),
        output_type=float,
    )
    calc_node = NodeSpec(
        id=calc_path,
        kind=NodeKind.CALCULATION,
        dependencies=frozenset({model_path}),
        output_type=float,
    )

    spec = GraphSpec(nodes={model_path: model_node, calc_path: calc_node})

    model_nodes = spec.get_nodes_by_kind(NodeKind.MODEL)
    assert len(model_nodes) == 1
    assert model_nodes[0] is model_node

    calc_nodes = spec.get_nodes_by_kind(NodeKind.CALCULATION)
    assert len(calc_nodes) == 1
    assert calc_nodes[0] is calc_node


def test_graph_spec_get_nodes_in_scope() -> None:
    path1 = ProjectPath(scope="Scope1", path=ModelPath(root="$", parts=(AttributePart("x"),)))
    path2 = ProjectPath(scope="Scope2", path=ModelPath(root="$", parts=(AttributePart("y"),)))

    node1 = NodeSpec(id=path1, kind=NodeKind.MODEL, dependencies=frozenset(), output_type=float)
    node2 = NodeSpec(id=path2, kind=NodeKind.MODEL, dependencies=frozenset(), output_type=float)

    spec = GraphSpec(nodes={path1: node1, path2: node2}, scope_names=("Scope1", "Scope2"))

    scope1_nodes = spec.get_nodes_in_scope("Scope1")
    assert len(scope1_nodes) == 1
    assert scope1_nodes[0] is node1


def test_graph_spec_contains() -> None:
    path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("x"),)))
    node = NodeSpec(id=path, kind=NodeKind.MODEL, dependencies=frozenset(), output_type=float)
    spec = GraphSpec(nodes={path: node})

    assert path in spec
    other_path = ProjectPath(scope="Test", path=ModelPath(root="$", parts=(AttributePart("y"),)))
    assert other_path not in spec


# =============================================================================
# Tests for build_graph_spec
# =============================================================================


def test_build_graph_spec_simple_model_only() -> None:
    """Test building spec from a project with just a model."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        x: float
        y: float

    spec = build_graph_spec(project)

    assert spec.scope_names == ("TestScope",)
    assert len(spec.get_nodes_by_kind(NodeKind.MODEL)) == 2  # x and y

    # Check that model nodes have no dependencies
    for node in spec.get_nodes_by_kind(NodeKind.MODEL):
        assert node.dependencies == frozenset()
        assert node.compute_fn is None


def test_build_graph_spec_model_with_calculation() -> None:
    """Test building spec with a calculation."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        x: float

    @scope.calculation()
    def double_x(x: Annotated[float, vq.Ref("$.x")]) -> float:
        return x * 2

    spec = build_graph_spec(project)

    # Should have 1 model node and 1 calculation node
    model_nodes = spec.get_nodes_by_kind(NodeKind.MODEL)
    calc_nodes = spec.get_nodes_by_kind(NodeKind.CALCULATION)

    assert len(model_nodes) == 1
    assert len(calc_nodes) == 1

    # Calculation should depend on model
    calc_node = calc_nodes[0]
    assert len(calc_node.dependencies) == 1
    assert calc_node.compute_fn is not None

    # Check param_mapping
    assert "x" in calc_node.param_mapping


def test_build_graph_spec_model_with_verification() -> None:
    """Test building spec with a verification."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        x: float

    @scope.verification()
    def x_positive(x: Annotated[float, vq.Ref("$.x")]) -> bool:
        return x > 0

    spec = build_graph_spec(project)

    verif_nodes = spec.get_nodes_by_kind(NodeKind.VERIFICATION)
    assert len(verif_nodes) == 1

    verif_node = verif_nodes[0]
    assert len(verif_node.dependencies) == 1
    assert verif_node.output_type is bool
    assert verif_node.metadata.get("xfail") is False


def test_build_graph_spec_verification_xfail_metadata() -> None:
    """Test that xfail flag is captured in metadata."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        x: float

    @scope.verification(xfail=True)
    def x_check(x: Annotated[float, vq.Ref("$.x")]) -> bool:
        return x > 100

    spec = build_graph_spec(project)

    verif_nodes = spec.get_nodes_by_kind(NodeKind.VERIFICATION)
    assert verif_nodes[0].metadata["xfail"] is True


def test_build_graph_spec_chained_calculations() -> None:
    """Test building spec with chained calculations."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        x: float

    @scope.calculation()
    def double_x(x: Annotated[float, vq.Ref("$.x")]) -> float:
        return x * 2

    @scope.calculation()
    def triple_doubled(doubled: Annotated[float, vq.Ref("@double_x")]) -> float:
        return doubled * 3

    spec = build_graph_spec(project)

    calc_nodes = spec.get_nodes_by_kind(NodeKind.CALCULATION)
    assert len(calc_nodes) == 2

    # Find the triple_doubled node
    triple_node = next(n for n in calc_nodes if "@triple_doubled" in str(n.id))

    # It should depend on the double_x calculation output
    dep_paths = [str(d.path) for d in triple_node.dependencies]
    assert any("@double_x" in p for p in dep_paths)


def test_build_graph_spec_nested_model() -> None:
    """Test building spec with nested Pydantic models."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    class Inner(BaseModel):
        a: float
        b: float

    @scope.root_model()
    class Outer(BaseModel):
        inner: Inner
        c: float

    spec = build_graph_spec(project)

    model_nodes = spec.get_nodes_by_kind(NodeKind.MODEL)
    # Should have: inner.a, inner.b, c
    assert len(model_nodes) == 3

    # Check paths
    paths = {str(n.id.path) for n in model_nodes}
    assert "$.inner.a" in paths
    assert "$.inner.b" in paths
    assert "$.c" in paths


def test_build_graph_spec_type_registry() -> None:
    """Test that type registry is populated correctly."""
    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        x: float
        y: int

    spec = build_graph_spec(project)

    # Check type registry has entries
    assert len(spec.type_registry) == 2

    # Find paths and check types
    for path, typ in spec.type_registry.items():
        if "x" in str(path):
            assert typ is float
        elif "y" in str(path):
            assert typ is int


def test_build_graph_spec_multi_scope_project() -> None:
    """Test building spec with multiple scopes."""
    project = vq.Project(name="TestProject")

    scope1 = vq.Scope(name="Scope1")
    project.add_scope(scope1)

    @scope1.root_model()
    class Model1(BaseModel):
        x: float

    scope2 = vq.Scope(name="Scope2")
    project.add_scope(scope2)

    @scope2.root_model()
    class Model2(BaseModel):
        y: float

    spec = build_graph_spec(project)

    assert set(spec.scope_names) == {"Scope1", "Scope2"}

    scope1_nodes = spec.get_nodes_in_scope("Scope1")
    scope2_nodes = spec.get_nodes_in_scope("Scope2")

    assert len(scope1_nodes) == 1
    assert len(scope2_nodes) == 1
