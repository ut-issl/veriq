"""Build dependency graph from project structure.

This module provides the public API for building dependency graphs.
It delegates to the new IR and graph modules internally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._graph import DependencyGraph
from ._ir import build_graph_spec

if TYPE_CHECKING:
    from ._models import Project
    from ._path import ProjectPath


@dataclass(slots=True)
class DepencenciesGraph:
    """Legacy dependency graph structure for backwards compatibility.

    This class wraps the new DependencyGraph internally while maintaining
    the original dict-based interface.

    Attributes:
        predecessors: Mapping from node to its dependencies (what it depends on).
        successors: Mapping from node to its dependents (what depends on it).

    """

    predecessors: dict[ProjectPath, set[ProjectPath]]
    successors: dict[ProjectPath, set[ProjectPath]]


def build_dependencies_graph(project: Project) -> DepencenciesGraph:
    """Build a dependency graph from a project.

    This function builds a graph representing the dependencies between
    model fields, calculations, and verifications in the project.

    Args:
        project: The project to build the graph from.

    Returns:
        A DepencenciesGraph containing predecessor and successor mappings.

    """
    # Use the new IR builder to get the graph spec
    graph_spec = build_graph_spec(project)

    # Build a DependencyGraph from the node specs
    edges: list[tuple[ProjectPath, ProjectPath]] = []
    for node in graph_spec.nodes.values():
        edges.extend((dep, node.id) for dep in node.dependencies)

    graph = DependencyGraph.from_edges(edges)

    # Convert to the legacy format (set instead of frozenset)
    predecessors: dict[ProjectPath, set[ProjectPath]] = {}
    successors: dict[ProjectPath, set[ProjectPath]] = {}

    for node_id in graph.nodes:
        preds = graph.predecessors(node_id)
        if preds:
            predecessors[node_id] = set(preds)

        succs = graph.successors(node_id)
        if succs:
            successors[node_id] = set(succs)

    return DepencenciesGraph(
        predecessors=predecessors,
        successors=successors,
    )
