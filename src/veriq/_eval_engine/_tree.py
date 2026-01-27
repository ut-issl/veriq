"""Tree-based data structures for evaluation results.

This module provides a hierarchical representation of evaluation results
organized as trees of PathNodes grouped by scope. This enables:
- Natural parent-child navigation for paths
- No duplication between composite and leaf values
- Extensibility for dependency visualization and interactive exploration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from veriq._path import (
    AttributePart,
    CalcPath,
    ItemPart,
    ModelPath,
    PartBase,
    ProjectPath,
    VerificationPath,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclass(frozen=True, slots=True)
class PathNode:
    """A node in the path tree.

    Represents either a leaf value or an intermediate node with children.
    For leaf nodes, `value` contains the computed result and `children` is empty.
    For intermediate nodes, `value` is None and `children` contains sub-nodes.

    Attributes:
        path: The ProjectPath identifying this node.
        value: The computed value (for leaf nodes) or None (for intermediate nodes).
        children: Tuple of child nodes (empty for leaf nodes).

    """

    path: ProjectPath
    value: Any | None = None
    children: tuple[PathNode, ...] = ()

    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (has no children)."""
        return len(self.children) == 0

    def iter_leaves(self) -> Generator[PathNode]:
        """Iterate over all leaf nodes in this subtree.

        Yields:
            PathNode instances that are leaves (have values, no children).

        """
        if self.is_leaf:
            yield self
        else:
            for child in self.children:
                yield from child.iter_leaves()

    def get_child(self, part: PartBase) -> PathNode | None:
        """Get a direct child by its path part.

        Args:
            part: The path part (AttributePart or ItemPart) to look for.

        Returns:
            The matching child PathNode, or None if not found.

        """
        for child in self.children:
            child_parts = child.path.path.parts
            if child_parts and child_parts[-1] == part:
                return child
        return None


@dataclass(frozen=True, slots=True)
class ScopeTree:
    """Tree of values for a single scope.

    Contains separate trees for the model, calculations, and verifications.

    Attributes:
        scope_name: The name of the scope.
        model: The root PathNode for the model (or None if no model).
        calculations: Tuple of PathNodes for calculations.
        verifications: Tuple of PathNodes for verifications.

    """

    scope_name: str
    model: PathNode | None = None
    calculations: tuple[PathNode, ...] = ()
    verifications: tuple[PathNode, ...] = ()

    def get_calculation(self, name: str) -> PathNode | None:
        """Get a calculation tree by name.

        Args:
            name: The calculation name (without '@' prefix).

        Returns:
            The PathNode for the calculation, or None if not found.

        """
        root = f"@{name}"
        for calc in self.calculations:
            if calc.path.path.root == root:
                return calc
        return None

    def get_verification(self, name: str) -> PathNode | None:
        """Get a verification tree by name.

        Args:
            name: The verification name (without '?' prefix).

        Returns:
            The PathNode for the verification, or None if not found.

        """
        root = f"?{name}"
        for verif in self.verifications:
            if verif.path.path.root == root:
                return verif
        return None

    def iter_all_nodes(self) -> Generator[PathNode]:
        """Iterate over all root path nodes in this scope.

        Yields:
            PathNode instances for model, calculations, and verifications.

        """
        if self.model is not None:
            yield self.model
        yield from self.calculations
        yield from self.verifications


def _group_paths_by_root(
    paths_values: list[tuple[ProjectPath, Any]],
) -> dict[str, list[tuple[ProjectPath, Any]]]:
    """Group paths by their root (e.g., '$', '@calc_name', '?verify_name')."""
    groups: dict[str, list[tuple[ProjectPath, Any]]] = {}
    for ppath, value in paths_values:
        root = ppath.path.root
        if root not in groups:
            groups[root] = []
        groups[root].append((ppath, value))
    return groups


def _build_tree_from_paths(
    scope_name: str,
    root: str,
    paths_values: list[tuple[ProjectPath, Any]],
    path_class: type[ModelPath | CalcPath | VerificationPath],
) -> PathNode:
    """Build a tree structure from a list of paths with the same root.

    Args:
        scope_name: The scope name for constructing ProjectPaths.
        root: The root string (e.g., '$', '@calc_name').
        paths_values: List of (ProjectPath, value) tuples with the same root.
        path_class: The path class (ModelPath, CalcPath, or VerificationPath).

    Returns:
        The root PathNode of the constructed tree.

    """
    # Build a nested dict structure first for easier tree construction
    # tree_data[parts] = value for leaf nodes
    tree_data: dict[tuple[PartBase, ...], Any] = {}
    for ppath, value in paths_values:
        tree_data[ppath.path.parts] = value

    def build_node(
        current_parts: tuple[PartBase, ...],
        remaining_keys: set[tuple[PartBase, ...]],
    ) -> PathNode:
        """Recursively build PathNode from parts."""
        # Create the path for this node
        path = path_class(root=root, parts=current_parts)
        ppath = ProjectPath(scope=scope_name, path=path)

        # Check if this is a leaf node (has a value directly)
        if current_parts in tree_data and not any(
            k != current_parts and len(k) > len(current_parts) and k[: len(current_parts)] == current_parts
            for k in remaining_keys
        ):
            return PathNode(path=ppath, value=tree_data[current_parts])

        # Find direct children (paths that extend current_parts by exactly one part)
        direct_child_parts: set[PartBase] = set()
        for parts in remaining_keys:
            if len(parts) > len(current_parts) and parts[: len(current_parts)] == current_parts:
                # This path extends current_parts
                next_part = parts[len(current_parts)]
                direct_child_parts.add(next_part)

        if not direct_child_parts:
            # No children, this must be a leaf
            value = tree_data.get(current_parts)
            return PathNode(path=ppath, value=value)

        # Build children
        children: list[PathNode] = []
        for child_part in sorted(direct_child_parts, key=_part_sort_key):
            child_parts = (*current_parts, child_part)
            child_remaining = {k for k in remaining_keys if k[: len(child_parts)] == child_parts}
            child_node = build_node(child_parts, child_remaining)
            children.append(child_node)

        # Intermediate node with children (value is None)
        return PathNode(path=ppath, value=None, children=tuple(children))

    return build_node((), set(tree_data.keys()))


def _part_sort_key(part: PartBase) -> tuple[int, str]:
    """Sort key for path parts (AttributePart before ItemPart, then by name/key)."""
    if isinstance(part, AttributePart):
        return (0, part.name)
    if isinstance(part, ItemPart):
        key = part.key
        if isinstance(key, tuple):
            return (1, ",".join(key))
        return (1, key)
    return (2, str(part))


def build_scope_trees(  # noqa: C901
    values: dict[ProjectPath, Any],
) -> dict[str, ScopeTree]:
    """Build tree structure from flat values dict.

    Args:
        values: Flat dict mapping ProjectPath to computed values.

    Returns:
        Dict mapping scope names to ScopeTree instances.

    """
    # Group by scope first
    by_scope: dict[str, list[tuple[ProjectPath, Any]]] = {}
    for ppath, value in values.items():
        scope = ppath.scope
        if scope not in by_scope:
            by_scope[scope] = []
        by_scope[scope].append((ppath, value))

    result: dict[str, ScopeTree] = {}

    for scope_name, scope_paths in by_scope.items():
        # Separate by path type
        model_paths: list[tuple[ProjectPath, Any]] = []
        calc_paths: list[tuple[ProjectPath, Any]] = []
        verif_paths: list[tuple[ProjectPath, Any]] = []

        for ppath, value in scope_paths:
            if isinstance(ppath.path, ModelPath):
                model_paths.append((ppath, value))
            elif isinstance(ppath.path, CalcPath):
                calc_paths.append((ppath, value))
            elif isinstance(ppath.path, VerificationPath):
                verif_paths.append((ppath, value))

        # Build model tree
        model_node: PathNode | None = None
        if model_paths:
            model_node = _build_tree_from_paths(scope_name, "$", model_paths, ModelPath)

        # Build calculation trees (grouped by root/calc name)
        calc_groups = _group_paths_by_root(calc_paths)
        calc_nodes: list[PathNode] = []
        for root, paths in sorted(calc_groups.items()):
            calc_node = _build_tree_from_paths(scope_name, root, paths, CalcPath)
            calc_nodes.append(calc_node)

        # Build verification trees (grouped by root/verification name)
        verif_groups = _group_paths_by_root(verif_paths)
        verif_nodes: list[PathNode] = []
        for root, paths in sorted(verif_groups.items()):
            verif_node = _build_tree_from_paths(scope_name, root, paths, VerificationPath)
            verif_nodes.append(verif_node)

        result[scope_name] = ScopeTree(
            scope_name=scope_name,
            model=model_node,
            calculations=tuple(calc_nodes),
            verifications=tuple(verif_nodes),
        )

    return result
