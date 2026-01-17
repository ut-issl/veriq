"""Graph specification containing all node specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veriq._path import ProjectPath

    from ._node_spec import NodeKind, NodeSpec


@dataclass(frozen=True, slots=True)
class GraphSpec:
    """Specification of the entire computation graph.

    This is an immutable collection of NodeSpecs that fully describes
    the computation graph. It can be:
    - Validated for correctness
    - Transformed into a DependencyGraph for evaluation
    - (Future) Serialized/deserialized for caching

    Attributes:
        nodes: Mapping from node ID (ProjectPath) to NodeSpec.
        scope_names: Tuple of scope names in the graph.
        type_registry: Mapping from ProjectPath to type for type resolution.
            This allows looking up types at any path without traversing
            the user-facing Project structure.

    Example:
        >>> spec = GraphSpec(
        ...     nodes={path1: node1, path2: node2},
        ...     scope_names=("Power", "Thermal"),
        ...     type_registry={path1: float, path2: bool},
        ... )
        >>> spec.get_nodes_by_kind(NodeKind.CALCULATION)
        [node1]

    """

    nodes: dict[ProjectPath, NodeSpec] = field(default_factory=dict)
    scope_names: tuple[str, ...] = field(default_factory=tuple)
    type_registry: dict[ProjectPath, type] = field(default_factory=dict)

    def get_node(self, path: ProjectPath) -> NodeSpec:
        """Get a node by its path.

        Args:
            path: The ProjectPath identifying the node.

        Returns:
            The NodeSpec at the given path.

        Raises:
            KeyError: If no node exists at the given path.

        """
        return self.nodes[path]

    def get_nodes_by_kind(self, kind: NodeKind) -> list[NodeSpec]:
        """Get all nodes of a specific kind.

        Args:
            kind: The NodeKind to filter by.

        Returns:
            List of NodeSpecs with the specified kind.

        """
        return [node for node in self.nodes.values() if node.kind == kind]

    def get_nodes_in_scope(self, scope_name: str) -> list[NodeSpec]:
        """Get all nodes in a specific scope.

        Args:
            scope_name: The name of the scope to filter by.

        Returns:
            List of NodeSpecs in the specified scope.

        """
        return [node for node in self.nodes.values() if node.id.scope == scope_name]

    def get_type(self, path: ProjectPath) -> type:
        """Get the type at a specific path.

        Args:
            path: The ProjectPath to look up.

        Returns:
            The type at the given path.

        Raises:
            KeyError: If the path is not in the type registry.

        """
        return self.type_registry[path]

    def __len__(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self.nodes)

    def __contains__(self, path: ProjectPath) -> bool:
        """Check if a node exists at the given path."""
        return path in self.nodes
