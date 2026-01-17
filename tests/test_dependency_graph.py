"""Tests for DependencyGraph and graph algorithms."""

import pytest

from veriq._graph import DependencyGraph, topological_sort


class TestTopologicalSort:
    """Tests for the topological_sort algorithm."""

    def test_empty_graph(self) -> None:
        result = topological_sort({})
        assert result == []

    def test_single_node(self) -> None:
        result = topological_sort({"a": []})
        assert result == ["a"]

    def test_linear_chain(self) -> None:
        # a -> b -> c (c depends on b, b depends on a)
        result = topological_sort({"a": ["b"], "b": ["c"], "c": []})
        assert result == ["a", "b", "c"]

    def test_diamond_dependency(self) -> None:
        # a -> b, a -> c, b -> d, c -> d
        result = topological_sort({"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []})
        assert result[0] == "a"
        assert result[-1] == "d"
        assert result.index("b") < result.index("d")
        assert result.index("c") < result.index("d")

    def test_multiple_roots(self) -> None:
        result = topological_sort({"a": ["c"], "b": ["c"], "c": []})
        assert result[-1] == "c"
        assert set(result[:2]) == {"a", "b"}

    def test_cycle_detection(self) -> None:
        with pytest.raises(ValueError, match="Cycle"):
            topological_sort({"a": ["b"], "b": ["a"]})

    def test_self_loop_detection(self) -> None:
        with pytest.raises(ValueError, match="Cycle"):
            topological_sort({"a": ["a"]})

    def test_longer_cycle(self) -> None:
        with pytest.raises(ValueError, match="Cycle"):
            topological_sort({"a": ["b"], "b": ["c"], "c": ["a"]})

    def test_works_with_integers(self) -> None:
        result = topological_sort({1: [2], 2: [3], 3: []})
        assert result == [1, 2, 3]

    def test_works_with_tuples(self) -> None:
        result = topological_sort({("a", 1): [("b", 2)], ("b", 2): []})
        assert result == [("a", 1), ("b", 2)]


class TestDependencyGraphConstruction:
    """Tests for DependencyGraph construction."""

    def test_empty_graph(self) -> None:
        graph = DependencyGraph.from_edges([])
        assert graph.nodes == frozenset()
        assert len(graph) == 0

    def test_single_edge(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b")])
        assert graph.nodes == frozenset({"a", "b"})
        assert len(graph) == 2

    def test_multiple_edges(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c"), ("a", "c")])
        assert graph.nodes == frozenset({"a", "b", "c"})

    def test_contains(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b")])
        assert "a" in graph
        assert "b" in graph
        assert "c" not in graph


class TestDependencyGraphQueries:
    """Tests for DependencyGraph query methods."""

    def test_predecessors_simple(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b")])
        assert graph.predecessors("b") == frozenset({"a"})
        assert graph.predecessors("a") == frozenset()

    def test_predecessors_multiple(self) -> None:
        graph = DependencyGraph.from_edges([("a", "c"), ("b", "c")])
        assert graph.predecessors("c") == frozenset({"a", "b"})

    def test_predecessors_nonexistent_node(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b")])
        assert graph.predecessors("nonexistent") == frozenset()

    def test_successors_simple(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b")])
        assert graph.successors("a") == frozenset({"b"})
        assert graph.successors("b") == frozenset()

    def test_successors_multiple(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("a", "c")])
        assert graph.successors("a") == frozenset({"b", "c"})

    def test_roots_simple(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
        assert graph.roots() == frozenset({"a"})

    def test_roots_multiple(self) -> None:
        graph = DependencyGraph.from_edges([("a", "c"), ("b", "c")])
        assert graph.roots() == frozenset({"a", "b"})

    def test_roots_empty_graph(self) -> None:
        graph = DependencyGraph.from_edges([])
        assert graph.roots() == frozenset()

    def test_leaves_simple(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
        assert graph.leaves() == frozenset({"c"})

    def test_leaves_multiple(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("a", "c")])
        assert graph.leaves() == frozenset({"b", "c"})


class TestDependencyGraphTransitiveQueries:
    """Tests for transitive dependency queries (ancestors/descendants)."""

    def test_ancestors_simple(self) -> None:
        # a -> b -> c
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
        assert graph.ancestors("c") == frozenset({"a", "b"})
        assert graph.ancestors("b") == frozenset({"a"})
        assert graph.ancestors("a") == frozenset()

    def test_ancestors_diamond(self) -> None:
        # a -> b -> d, a -> c -> d
        graph = DependencyGraph.from_edges([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
        assert graph.ancestors("d") == frozenset({"a", "b", "c"})

    def test_descendants_simple(self) -> None:
        # a -> b -> c
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
        assert graph.descendants("a") == frozenset({"b", "c"})
        assert graph.descendants("b") == frozenset({"c"})
        assert graph.descendants("c") == frozenset()

    def test_descendants_branching(self) -> None:
        # a -> b, a -> c, b -> d, c -> d
        graph = DependencyGraph.from_edges([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
        assert graph.descendants("a") == frozenset({"b", "c", "d"})


class TestDependencyGraphTopologicalOrder:
    """Tests for topological ordering of the graph."""

    def test_topological_order_linear(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
        assert graph.topological_order() == ["a", "b", "c"]

    def test_topological_order_respects_dependencies(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])
        order = graph.topological_order()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_has_cycle_false(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
        assert graph.has_cycle() is False

    def test_has_cycle_true(self) -> None:
        graph = DependencyGraph(
            _predecessors={"a": frozenset({"b"}), "b": frozenset({"a"})},
            _successors={"a": frozenset({"b"}), "b": frozenset({"a"})},
        )
        assert graph.has_cycle() is True


class TestDependencyGraphSubgraph:
    """Tests for subgraph extraction."""

    def test_subgraph_keeps_internal_edges(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c"), ("c", "d")])
        sub = graph.subgraph(frozenset({"b", "c"}))
        assert sub.nodes == frozenset({"b", "c"})
        assert sub.predecessors("c") == frozenset({"b"})

    def test_subgraph_removes_external_edges(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
        sub = graph.subgraph(frozenset({"b", "c"}))
        # Edge from "a" to "b" should be removed since "a" is not in subgraph
        assert sub.predecessors("b") == frozenset()

    def test_subgraph_empty(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b")])
        sub = graph.subgraph(frozenset())
        assert sub.nodes == frozenset()


class TestDependencyGraphValidation:
    """Tests for graph validation."""

    def test_valid_graph(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
        errors = graph.validate()
        assert errors == []

    def test_cycle_detected(self) -> None:
        graph = DependencyGraph(
            _predecessors={"a": frozenset({"b"}), "b": frozenset({"a"})},
            _successors={"a": frozenset({"b"}), "b": frozenset({"a"})},
        )
        errors = graph.validate()
        assert len(errors) == 1
        assert "cycle" in errors[0].lower()

    def test_missing_dependency_detected(self) -> None:
        # Manually construct a graph with a missing node
        graph = DependencyGraph(
            _predecessors={"b": frozenset({"nonexistent"})},
            _successors={},
        )
        errors = graph.validate()
        assert any("missing" in e.lower() for e in errors)


class TestDependencyGraphImmutability:
    """Tests ensuring the graph is immutable."""

    def test_nodes_returns_frozenset(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b")])
        nodes = graph.nodes
        assert isinstance(nodes, frozenset)

    def test_predecessors_returns_frozenset(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b")])
        preds = graph.predecessors("b")
        assert isinstance(preds, frozenset)

    def test_successors_returns_frozenset(self) -> None:
        graph = DependencyGraph.from_edges([("a", "b")])
        succs = graph.successors("a")
        assert isinstance(succs, frozenset)
