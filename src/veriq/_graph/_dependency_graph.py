"""Generic dependency graph abstraction."""

from collections import defaultdict
from dataclasses import dataclass, field

from ._algorithms import topological_sort


@dataclass(frozen=True, slots=True)
class DependencyGraph[T]:
    """A directed acyclic graph representing dependencies between nodes.

    This is a pure, immutable data structure with query methods.
    It is generic over the node type T (e.g., str, int, ProjectPath).

    The graph represents "depends on" relationships:
    - predecessors[b] = {a} means "b depends on a"
    - successors[a] = {b} means "a is depended on by b"

    Attributes:
        _predecessors: Mapping from node to its direct dependencies.
        _successors: Mapping from node to nodes that depend on it.

    """

    _predecessors: dict[T, frozenset[T]] = field(default_factory=dict)
    _successors: dict[T, frozenset[T]] = field(default_factory=dict)

    @classmethod
    def from_edges(cls, edges: list[tuple[T, T]]) -> DependencyGraph[T]:
        """Build a graph from a list of (source, target) edges.

        An edge (a, b) means "b depends on a" (a -> b in the DAG).

        Args:
            edges: List of (source, target) tuples.

        Returns:
            A new DependencyGraph instance.

        Example:
            >>> # b depends on a, c depends on b
            >>> graph = DependencyGraph.from_edges([("a", "b"), ("b", "c")])
            >>> graph.predecessors("b")
            frozenset({'a'})

        """
        predecessors: defaultdict[T, set[T]] = defaultdict(set)
        successors: defaultdict[T, set[T]] = defaultdict(set)

        for src, dst in edges:
            predecessors[dst].add(src)
            successors[src].add(dst)
            # Ensure both nodes exist in the graph
            predecessors.setdefault(src, set())
            successors.setdefault(dst, set())

        return cls(
            _predecessors={k: frozenset(v) for k, v in predecessors.items()},
            _successors={k: frozenset(v) for k, v in successors.items()},
        )

    @property
    def nodes(self) -> frozenset[T]:
        """All nodes in the graph."""
        return frozenset(self._predecessors.keys()) | frozenset(self._successors.keys())

    def predecessors(self, node: T) -> frozenset[T]:
        """Get direct dependencies of a node (nodes it depends on).

        Args:
            node: The node to query.

        Returns:
            Set of nodes that this node directly depends on.

        """
        return self._predecessors.get(node, frozenset())

    def successors(self, node: T) -> frozenset[T]:
        """Get direct dependents of a node (nodes that depend on it).

        Args:
            node: The node to query.

        Returns:
            Set of nodes that directly depend on this node.

        """
        return self._successors.get(node, frozenset())

    def roots(self) -> frozenset[T]:
        """Get nodes with no predecessors (input/source nodes).

        Returns:
            Set of nodes that have no dependencies.

        """
        return frozenset(n for n in self.nodes if not self._predecessors.get(n))

    def leaves(self) -> frozenset[T]:
        """Get nodes with no successors (output/sink nodes).

        Returns:
            Set of nodes that nothing depends on.

        """
        return frozenset(n for n in self.nodes if not self._successors.get(n))

    def ancestors(self, node: T) -> frozenset[T]:
        """Get all transitive dependencies of a node.

        Args:
            node: The node to query.

        Returns:
            Set of all nodes that this node transitively depends on.

        """
        visited: set[T] = set()
        stack = list(self.predecessors(node))
        while stack:
            current = stack.pop()
            if current not in visited:
                visited.add(current)
                stack.extend(self.predecessors(current))
        return frozenset(visited)

    def descendants(self, node: T) -> frozenset[T]:
        """Get all transitive dependents of a node.

        Args:
            node: The node to query.

        Returns:
            Set of all nodes that transitively depend on this node.

        """
        visited: set[T] = set()
        stack = list(self.successors(node))
        while stack:
            current = stack.pop()
            if current not in visited:
                visited.add(current)
                stack.extend(self.successors(current))
        return frozenset(visited)

    def topological_order(self) -> list[T]:
        """Return nodes in topological order (dependencies before dependents).

        Returns:
            List of nodes where each node appears before all nodes that depend on it.

        Raises:
            ValueError: If the graph contains a cycle.

        """
        return topological_sort(dict(self._successors))

    def has_cycle(self) -> bool:
        """Check if the graph contains a cycle.

        Returns:
            True if the graph has a cycle, False otherwise.

        """
        try:
            self.topological_order()
        except ValueError:
            return True
        return False

    def subgraph(self, nodes: frozenset[T]) -> DependencyGraph[T]:
        """Create a subgraph containing only the specified nodes.

        Edges are kept only if both endpoints are in the node set.

        Args:
            nodes: Set of nodes to include in the subgraph.

        Returns:
            A new DependencyGraph containing only the specified nodes.

        """
        return DependencyGraph(
            _predecessors={n: self._predecessors.get(n, frozenset()) & nodes for n in nodes},
            _successors={n: self._successors.get(n, frozenset()) & nodes for n in nodes},
        )

    def validate(self) -> list[str]:
        """Validate the graph and return a list of error messages.

        Checks for:
        - Cycles in the graph
        - Missing nodes (edges pointing to non-existent nodes)

        Returns:
            List of error messages. Empty list if graph is valid.

        """
        errors: list[str] = []

        if self.has_cycle():
            errors.append("Graph contains a cycle")

        all_nodes = self.nodes
        for node, deps in self._predecessors.items():
            missing = deps - all_nodes
            if missing:
                errors.append(f"Node '{node}' has missing dependencies: {missing}")

        return errors

    def __len__(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self.nodes)

    def __contains__(self, node: T) -> bool:
        """Check if a node is in the graph."""
        return node in self._predecessors or node in self._successors
