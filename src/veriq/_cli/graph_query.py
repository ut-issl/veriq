"""Graph query functions for CLI commands.

This module provides pure functions for querying the dependency graph.
These are the functional core - no I/O, no Rich rendering.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from veriq._graph import DependencyGraph
from veriq._ir import GraphSpec, NodeKind, build_graph_spec

if TYPE_CHECKING:
    from veriq._models import Project
    from veriq._path import ProjectPath


class NonLeafPathError(Exception):
    """Raised when a path refers to a non-leaf node with multiple leaf outputs."""

    def __init__(self, path: ProjectPath, leaf_paths: list[ProjectPath]) -> None:
        self.path = path
        self.leaf_paths = leaf_paths
        super().__init__(f"Path '{path}' is a non-leaf node with {len(leaf_paths)} outputs")


@dataclass(frozen=True, slots=True)
class ScopeSummary:
    """Summary of a scope's contents."""

    name: str
    model_count: int
    calc_count: int
    verification_count: int


@dataclass(frozen=True, slots=True)
class NodeInfo:
    """Basic information about a node for listing."""

    path: ProjectPath
    kind: NodeKind
    dependency_count: int


@dataclass(frozen=True, slots=True)
class NodeDetail:
    """Detailed information about a node."""

    path: ProjectPath
    kind: NodeKind
    output_type: type
    direct_dependencies: frozenset[ProjectPath]
    direct_dependents: frozenset[ProjectPath]
    metadata: dict


@dataclass(slots=True)
class TreeNode:
    """A node in a dependency tree for rendering."""

    path: ProjectPath
    children: list[TreeNode]


def _build_dependency_graph(spec: GraphSpec) -> DependencyGraph[ProjectPath]:
    """Build a DependencyGraph from a GraphSpec."""
    edges: list[tuple[ProjectPath, ProjectPath]] = []
    for node in spec.nodes.values():
        edges.extend((dep, node.id) for dep in node.dependencies)
    return DependencyGraph.from_edges(edges)


def get_scope_summaries(project: Project) -> list[ScopeSummary]:
    """Get summary information for all scopes in the project.

    Args:
        project: The Project to analyze.

    Returns:
        List of ScopeSummary, one per scope.

    """
    spec = build_graph_spec(project)

    summaries: dict[str, dict[str, int]] = {}
    for scope_name in spec.scope_names:
        summaries[scope_name] = {"model": 0, "calc": 0, "verification": 0}

    for node in spec.nodes.values():
        scope_name = node.id.scope
        if scope_name not in summaries:
            summaries[scope_name] = {"model": 0, "calc": 0, "verification": 0}

        match node.kind:
            case NodeKind.MODEL:
                summaries[scope_name]["model"] += 1
            case NodeKind.CALCULATION:
                summaries[scope_name]["calc"] += 1
            case NodeKind.VERIFICATION:
                summaries[scope_name]["verification"] += 1

    return [
        ScopeSummary(
            name=name,
            model_count=counts["model"],
            calc_count=counts["calc"],
            verification_count=counts["verification"],
        )
        for name, counts in summaries.items()
    ]


def _is_path_prefix_of(prefix_str: str, path_str: str) -> bool:
    """Check if prefix_str is a proper path prefix of path_str.

    A proper prefix means path_str starts with prefix_str followed by
    '.' (attribute access) or '[' (item access).

    Args:
        prefix_str: The potential prefix path string.
        path_str: The path string to check against.

    Returns:
        True if prefix_str is a proper path prefix of path_str.

    """
    if not path_str.startswith(prefix_str):
        return False
    if len(path_str) <= len(prefix_str):
        return False
    next_char = path_str[len(prefix_str)]
    return next_char in (".", "[")


def _find_non_leaf_paths(paths: set[str]) -> set[str]:
    """Find all path strings that have children (are non-leaf).

    A path is non-leaf if another path exists that starts with it
    followed by '.' or '['.

    Args:
        paths: Set of path strings to analyze.

    Returns:
        Set of path strings that are non-leaf (have children).

    """
    non_leaf: set[str] = set()
    for path_str in paths:
        for other_str in paths:
            if path_str != other_str and _is_path_prefix_of(path_str, other_str):
                non_leaf.add(path_str)
                break
    return non_leaf


def _filter_non_leaf_table_paths(spec: GraphSpec) -> set[ProjectPath]:
    """Find all non-leaf Table paths that should be excluded from listings.

    Table types are stored both as the whole table and as individual items.
    This function identifies the non-leaf paths (the whole table entries)
    that have children (individual items).

    Args:
        spec: The GraphSpec to analyze.

    Returns:
        Set of ProjectPath that are non-leaf Table paths.

    """
    all_path_strs = {str(p) for p in spec.nodes}
    non_leaf_strs = _find_non_leaf_paths(all_path_strs)
    return {p for p in spec.nodes if str(p) in non_leaf_strs}


def list_nodes(
    project: Project,
    *,
    kinds: list[NodeKind] | None = None,
    scopes: list[str] | None = None,
    leaves_only: bool = False,
) -> list[NodeInfo]:
    """List nodes in the project with optional filtering.

    Args:
        project: The Project to analyze.
        kinds: Filter by node kinds (MODEL, CALCULATION, VERIFICATION).
        scopes: Filter by scope names.
        leaves_only: If True, only return leaf nodes (nothing depends on them).

    Returns:
        List of NodeInfo matching the filters.

    """
    spec = build_graph_spec(project)
    graph = _build_dependency_graph(spec)

    # Filter out non-leaf Table paths (e.g., $.power_consumption when
    # $.power_consumption[mission] etc. exist)
    non_leaf_table_paths = _filter_non_leaf_table_paths(spec)
    nodes = [n for n in spec.nodes.values() if n.id not in non_leaf_table_paths]

    # Filter by kind
    if kinds:
        nodes = [n for n in nodes if n.kind in kinds]

    # Filter by scope
    if scopes:
        nodes = [n for n in nodes if n.id.scope in scopes]

    # Filter to leaves only
    if leaves_only:
        leaf_paths = graph.leaves()
        nodes = [n for n in nodes if n.id in leaf_paths]

    # Sort by scope then path string for consistent output
    nodes.sort(key=lambda n: (n.id.scope, str(n.id.path)))

    return [
        NodeInfo(
            path=n.id,
            kind=n.kind,
            dependency_count=len(n.dependencies),
        )
        for n in nodes
    ]


def get_node_detail(project: Project, path: ProjectPath) -> NodeDetail:
    """Get detailed information about a specific node.

    Args:
        project: The Project containing the node.
        path: The ProjectPath identifying the node.

    Returns:
        NodeDetail with full information about the node.

    Raises:
        KeyError: If the node is not found.
        NonLeafPathError: If the path refers to a non-leaf node with multiple outputs.

    """
    spec = build_graph_spec(project)
    graph = _build_dependency_graph(spec)

    if path not in spec:
        # Check if this is a non-leaf path (prefix of leaf paths)
        leaf_paths = _find_matching_leaf_paths(spec, path)
        if leaf_paths:
            raise NonLeafPathError(path, leaf_paths)
        msg = f"Node not found: {path}"
        raise KeyError(msg)

    node = spec.get_node(path)

    return NodeDetail(
        path=path,
        kind=node.kind,
        output_type=node.output_type,
        direct_dependencies=graph.predecessors(path),
        direct_dependents=graph.successors(path),
        metadata=dict(node.metadata),
    )


def _find_matching_leaf_paths(spec: GraphSpec, prefix_path: ProjectPath) -> list[ProjectPath]:
    """Find all leaf paths that start with the given prefix path.

    Only returns true leaf paths (those that don't have any children).
    This filters out intermediate Table paths that are also stored in the graph.

    Args:
        spec: The GraphSpec to search.
        prefix_path: The prefix path to match.

    Returns:
        List of matching leaf paths, sorted by string representation.

    """
    prefix_str = str(prefix_path)

    # Find all paths that are children of the prefix
    matching: list[ProjectPath] = [
        node_path
        for node_path in spec.nodes
        if _is_path_prefix_of(prefix_str, str(node_path))
    ]

    # Filter out non-leaf paths using the shared helper
    matching_strs = {str(p) for p in matching}
    non_leaf_strs = _find_non_leaf_paths(matching_strs)
    leaf_paths: list[ProjectPath] = [p for p in matching if str(p) not in non_leaf_strs]

    leaf_paths.sort(key=str)
    return leaf_paths


def get_dependency_tree(
    project: Project,
    path: ProjectPath,
    *,
    invert: bool = False,
    max_depth: int | None = None,
) -> TreeNode:
    """Build a dependency tree for visualization.

    Args:
        project: The Project containing the node.
        path: The root node of the tree.
        invert: If False, show what the node depends on.
                If True, show what depends on the node (reverse dependencies).
        max_depth: Maximum depth to traverse (None for unlimited).

    Returns:
        TreeNode representing the dependency tree.

    Raises:
        KeyError: If the node is not found.

    """
    spec = build_graph_spec(project)
    graph = _build_dependency_graph(spec)

    if path not in spec:
        msg = f"Node not found: {path}"
        raise KeyError(msg)

    def build_tree(node_path: ProjectPath, depth: int, visited: set[ProjectPath]) -> TreeNode:
        children: list[TreeNode] = []

        if max_depth is not None and depth >= max_depth:
            return TreeNode(path=node_path, children=children)

        # Get neighbors based on direction
        neighbors = graph.successors(node_path) if invert else graph.predecessors(node_path)

        # Sort for consistent output
        sorted_neighbors: list[ProjectPath] = list(neighbors)
        sorted_neighbors.sort(key=str)
        for neighbor in sorted_neighbors:
            if neighbor not in visited:
                visited.add(neighbor)
                child_tree = build_tree(neighbor, depth + 1, visited)
                children.append(child_tree)

        return TreeNode(path=node_path, children=children)

    visited: set[ProjectPath] = {path}
    return build_tree(path, 0, visited)


def validate_scope_exists(project: Project, scope_name: str) -> bool:
    """Check if a scope exists in the project.

    Args:
        project: The Project to check.
        scope_name: The scope name to validate.

    Returns:
        True if the scope exists, False otherwise.

    """
    spec = build_graph_spec(project)
    return scope_name in spec.scope_names


def get_available_scopes(project: Project) -> list[str]:
    """Get list of available scope names.

    Args:
        project: The Project to query.

    Returns:
        List of scope names.

    """
    spec = build_graph_spec(project)
    return list(spec.scope_names)
