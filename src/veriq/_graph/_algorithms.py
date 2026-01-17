"""Graph algorithms for dependency graph operations."""

from collections import defaultdict, deque
from collections.abc import Collection, Hashable, Mapping


def topological_sort[T: Hashable](successors: Mapping[T, Collection[T]]) -> list[T]:
    """Sort a graph topologically (dependencies before dependents).

    Given a graph represented as a mapping from nodes to their successors
    (nodes that depend on them), return nodes in an order where each node
    appears before all nodes that depend on it.

    Args:
        successors: Mapping from node to collection of nodes that depend on it.
            An edge (a -> b) means "b depends on a".

    Returns:
        List of nodes in topological order.

    Raises:
        ValueError: If the graph contains a cycle.

    Example:
        >>> # a -> b -> c means c depends on b, b depends on a
        >>> topological_sort({"a": ["b"], "b": ["c"], "c": []})
        ['a', 'b', 'c']

    """
    # Calculate in-degree for each node
    indegree: defaultdict[T, int] = defaultdict(int)
    for node, deps in successors.items():
        indegree[node] = indegree.get(node, 0)
        for dep in deps:
            indegree[dep] += 1

    # Start with nodes that have no predecessors (in-degree 0)
    queue = deque([node for node, deg in indegree.items() if deg == 0])
    order: list[T] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for successor in successors.get(node, []):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)

    if len(order) != len(indegree):
        msg = "Cycle detected in graph"
        raise ValueError(msg)

    return order
