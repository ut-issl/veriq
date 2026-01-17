"""Tests for DependencyGraph and graph algorithms."""

import pytest

from veriq._graph import DependencyGraph, topological_sort

# =============================================================================
# Tests for topological_sort algorithm
# =============================================================================


def test_topological_sort_empty_graph() -> None:
    result = topological_sort({})
    assert result == []


def test_topological_sort_single_node() -> None:
    result = topological_sort({"a": []})
    assert result == ["a"]


def test_topological_sort_linear_chain() -> None:
    # a -> b -> c (c depends on b, b depends on a)
    result = topological_sort({"a": ["b"], "b": ["c"], "c": []})
    assert result == ["a", "b", "c"]


def test_topological_sort_diamond_dependency() -> None:
    # a -> b, a -> c, b -> d, c -> d
    result = topological_sort({"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []})
    assert result[0] == "a"
    assert result[-1] == "d"
    assert result.index("b") < result.index("d")
    assert result.index("c") < result.index("d")


def test_topological_sort_multiple_roots() -> None:
    result = topological_sort({"a": ["c"], "b": ["c"], "c": []})
    assert result[-1] == "c"
    assert set(result[:2]) == {"a", "b"}


def test_topological_sort_cycle_detection() -> None:
    with pytest.raises(ValueError, match="Cycle"):
        topological_sort({"a": ["b"], "b": ["a"]})


def test_topological_sort_self_loop_detection() -> None:
    with pytest.raises(ValueError, match="Cycle"):
        topological_sort({"a": ["a"]})


def test_topological_sort_longer_cycle() -> None:
    with pytest.raises(ValueError, match="Cycle"):
        topological_sort({"a": ["b"], "b": ["c"], "c": ["a"]})


def test_topological_sort_works_with_integers() -> None:
    result = topological_sort({1: [2], 2: [3], 3: []})
    assert result == [1, 2, 3]


def test_topological_sort_works_with_tuples() -> None:
    result = topological_sort({("a", 1): [("b", 2)], ("b", 2): []})
    assert result == [("a", 1), ("b", 2)]


# =============================================================================
# Tests for DependencyGraph construction
# =============================================================================


def test_graph_from_edges_empty() -> None:
    graph = DependencyGraph.from_edges([])
    assert graph.nodes == frozenset()
    assert len(graph) == 0


def test_graph_from_edges_single_edge() -> None:
    graph = DependencyGraph.from_edges([("a", "b")])
    assert graph.nodes == frozenset({"a", "b"})
    assert len(graph) == 2


def test_graph_from_edges_multiple_edges() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c"), ("a", "c")])
    assert graph.nodes == frozenset({"a", "b", "c"})


def test_graph_contains() -> None:
    graph = DependencyGraph.from_edges([("a", "b")])
    assert "a" in graph
    assert "b" in graph
    assert "c" not in graph


# =============================================================================
# Tests for DependencyGraph query methods
# =============================================================================


def test_graph_predecessors_simple() -> None:
    graph = DependencyGraph.from_edges([("a", "b")])
    assert graph.predecessors("b") == frozenset({"a"})
    assert graph.predecessors("a") == frozenset()


def test_graph_predecessors_multiple() -> None:
    graph = DependencyGraph.from_edges([("a", "c"), ("b", "c")])
    assert graph.predecessors("c") == frozenset({"a", "b"})


def test_graph_predecessors_nonexistent_node() -> None:
    graph = DependencyGraph.from_edges([("a", "b")])
    assert graph.predecessors("nonexistent") == frozenset()


def test_graph_successors_simple() -> None:
    graph = DependencyGraph.from_edges([("a", "b")])
    assert graph.successors("a") == frozenset({"b"})
    assert graph.successors("b") == frozenset()


def test_graph_successors_multiple() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("a", "c")])
    assert graph.successors("a") == frozenset({"b", "c"})


def test_graph_roots_simple() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
    assert graph.roots() == frozenset({"a"})


def test_graph_roots_multiple() -> None:
    graph = DependencyGraph.from_edges([("a", "c"), ("b", "c")])
    assert graph.roots() == frozenset({"a", "b"})


def test_graph_roots_empty_graph() -> None:
    graph = DependencyGraph.from_edges([])
    assert graph.roots() == frozenset()


def test_graph_leaves_simple() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
    assert graph.leaves() == frozenset({"c"})


def test_graph_leaves_multiple() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("a", "c")])
    assert graph.leaves() == frozenset({"b", "c"})


# =============================================================================
# Tests for transitive queries (ancestors/descendants)
# =============================================================================


def test_graph_ancestors_simple() -> None:
    # a -> b -> c
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
    assert graph.ancestors("c") == frozenset({"a", "b"})
    assert graph.ancestors("b") == frozenset({"a"})
    assert graph.ancestors("a") == frozenset()


def test_graph_ancestors_diamond() -> None:
    # a -> b -> d, a -> c -> d
    graph = DependencyGraph.from_edges([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
    assert graph.ancestors("d") == frozenset({"a", "b", "c"})


def test_graph_descendants_simple() -> None:
    # a -> b -> c
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
    assert graph.descendants("a") == frozenset({"b", "c"})
    assert graph.descendants("b") == frozenset({"c"})
    assert graph.descendants("c") == frozenset()


def test_graph_descendants_branching() -> None:
    # a -> b, a -> c, b -> d, c -> d
    graph = DependencyGraph.from_edges([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
    assert graph.descendants("a") == frozenset({"b", "c", "d"})


# =============================================================================
# Tests for topological ordering
# =============================================================================


def test_graph_topological_order_linear() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
    assert graph.topological_order() == ["a", "b", "c"]


def test_graph_topological_order_respects_dependencies() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
    order = graph.topological_order()
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_graph_has_cycle_false() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
    assert graph.has_cycle() is False


def test_graph_has_cycle_true() -> None:
    graph = DependencyGraph(
        _predecessors={"a": frozenset({"b"}), "b": frozenset({"a"})},
        _successors={"a": frozenset({"b"}), "b": frozenset({"a"})},
    )
    assert graph.has_cycle() is True


# =============================================================================
# Tests for subgraph extraction
# =============================================================================


def test_graph_subgraph_keeps_internal_edges() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c"), ("c", "d")])
    sub = graph.subgraph(frozenset({"b", "c"}))
    assert sub.nodes == frozenset({"b", "c"})
    assert sub.predecessors("c") == frozenset({"b"})


def test_graph_subgraph_removes_external_edges() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
    sub = graph.subgraph(frozenset({"b", "c"}))
    # Edge from "a" to "b" should be removed since "a" is not in subgraph
    assert sub.predecessors("b") == frozenset()


def test_graph_subgraph_empty() -> None:
    graph = DependencyGraph.from_edges([("a", "b")])
    sub = graph.subgraph(frozenset())
    assert sub.nodes == frozenset()


# =============================================================================
# Tests for validation
# =============================================================================


def test_graph_validate_valid_graph() -> None:
    graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
    errors = graph.validate()
    assert errors == []


def test_graph_validate_cycle_detected() -> None:
    graph = DependencyGraph(
        _predecessors={"a": frozenset({"b"}), "b": frozenset({"a"})},
        _successors={"a": frozenset({"b"}), "b": frozenset({"a"})},
    )
    errors = graph.validate()
    assert len(errors) == 1
    assert "cycle" in errors[0].lower()


def test_graph_validate_missing_dependency_detected() -> None:
    # Manually construct a graph with a missing node
    graph = DependencyGraph(
        _predecessors={"b": frozenset({"nonexistent"})},
        _successors={},
    )
    errors = graph.validate()
    assert any("missing" in e.lower() for e in errors)


# =============================================================================
# Tests for immutability
# =============================================================================


def test_graph_nodes_returns_frozenset() -> None:
    graph = DependencyGraph.from_edges([("a", "b")])
    nodes = graph.nodes
    assert isinstance(nodes, frozenset)


def test_graph_predecessors_returns_frozenset() -> None:
    graph = DependencyGraph.from_edges([("a", "b")])
    preds = graph.predecessors("b")
    assert isinstance(preds, frozenset)


def test_graph_successors_returns_frozenset() -> None:
    graph = DependencyGraph.from_edges([("a", "b")])
    succs = graph.successors("a")
    assert isinstance(succs, frozenset)
