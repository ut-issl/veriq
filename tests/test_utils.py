"""Tests for utility functions in veriq._utils."""

import pytest

from veriq._utils import topological_sort


class TestTopologicalSort:
    def test_empty_graph(self):
        """Test sorting an empty dependency graph."""
        result = topological_sort({})
        assert result == []

    def test_single_node_no_deps(self):
        """Test graph with single node and no dependencies."""
        result = topological_sort({"a": []})
        assert result == ["a"]

    def test_single_node_with_successor(self):
        """Test graph with single node pointing to another."""
        result = topological_sort({"a": ["b"]})
        # 'a' has no incoming edges, so it comes first
        # 'b' depends on 'a', so it comes second
        assert result == ["a", "b"]

    def test_linear_chain(self):
        """Test a linear chain: a -> b -> c."""
        result = topological_sort({"a": ["b"], "b": ["c"]})
        assert result == ["a", "b", "c"]

    def test_diamond_dependency(self):
        """Test diamond-shaped dependency: a -> b, c -> d; b, c -> d."""
        result = topological_sort({"a": ["b", "c"], "b": ["d"], "c": ["d"]})
        # 'a' must come first, then b and c (in some order), then d
        assert result[0] == "a"
        assert result[-1] == "d"
        assert set(result[1:3]) == {"b", "c"}

    def test_multiple_roots(self):
        """Test graph with multiple independent roots."""
        result = topological_sort({"a": ["c"], "b": ["c"]})
        # Both a and b are roots (no incoming edges)
        # c depends on both
        assert result[-1] == "c"
        assert set(result[:-1]) == {"a", "b"}

    def test_complex_graph(self):
        """Test a more complex dependency graph."""
        # a -> b -> d
        #   -> c -> d
        #        -> e
        result = topological_sort(
            {"a": ["b", "c"], "b": ["d"], "c": ["d", "e"], "d": [], "e": []},
        )
        # Verify ordering constraints
        assert result.index("a") < result.index("b")
        assert result.index("a") < result.index("c")
        assert result.index("b") < result.index("d")
        assert result.index("c") < result.index("d")
        assert result.index("c") < result.index("e")

    def test_cycle_raises_error(self):
        """Test that a cycle in the graph raises ValueError."""
        # a -> b -> c -> a (cycle)
        with pytest.raises(ValueError, match="Cycle detected"):
            topological_sort({"a": ["b"], "b": ["c"], "c": ["a"]})

    def test_self_loop_raises_error(self):
        """Test that a self-loop raises ValueError."""
        with pytest.raises(ValueError, match="Cycle detected"):
            topological_sort({"a": ["a"]})

    def test_two_node_cycle_raises_error(self):
        """Test that a two-node cycle raises ValueError."""
        with pytest.raises(ValueError, match="Cycle detected"):
            topological_sort({"a": ["b"], "b": ["a"]})

    def test_isolated_nodes(self):
        """Test graph with isolated nodes (no edges)."""
        result = topological_sort({"a": [], "b": [], "c": []})
        # All nodes are roots, order doesn't matter but all should be present
        assert set(result) == {"a", "b", "c"}
        assert len(result) == 3

    def test_preserves_all_nodes(self):
        """Test that all nodes from the graph are in the result."""
        graph = {"x": ["y", "z"], "y": ["z"], "z": []}
        result = topological_sort(graph)
        assert set(result) == {"x", "y", "z"}

    def test_with_integer_nodes(self):
        """Test that topological sort works with non-string hashable types."""
        result = topological_sort({1: [2], 2: [3], 3: []})
        assert result == [1, 2, 3]

    def test_with_tuple_nodes(self):
        """Test with tuple nodes (like ProjectPath could be simplified to)."""
        a = ("scope", "a")
        b = ("scope", "b")
        c = ("scope", "c")
        result = topological_sort({a: [b], b: [c], c: []})
        assert result == [a, b, c]
