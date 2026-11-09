"""Definition-level upstream subgraph of a node.

The IR (`GraphSpec`) expands every definition (root model, calculation, verification)
into one `NodeSpec` per output leaf. That is the right granularity for evaluation but
the wrong one for aggregation and provenance: any traversal over leaf nodes counts a
definition once per leaf it produces.

This module reduces the leaf graph to **definition granularity** (one node per
`$` / `@calculation` / `?verification` root in a scope) while preserving what a plain
edge set would throw away:

- `InputBinding`: which function parameter is bound to which declared reference, and
  which leaf paths that reference expands to.
- `AssumeEdge`: `@vq.assume` references, kept apart from data dependencies.

`upstream_subgraph()` returns everything a target transitively depends on, so one can
ask both "what is the total of some metadata key over this subgraph?" and "which
root-model fields does this verification ultimately read, through which parameters?".
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ._graph import topological_sort
from ._ir import GraphSpec, NodeKind, build_graph_spec
from ._models import Project
from ._path import ProjectPath, parse_project_path

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ._ir import NodeSpec


@dataclass(frozen=True, slots=True)
class DefinitionId:
    """Identity of a definition: a scope and a path root (`$`, `@name` or `?name`)."""

    scope: str
    root: str

    @classmethod
    def from_path(cls, path: ProjectPath) -> DefinitionId:
        return cls(scope=path.scope, root=path.path.root)

    def __str__(self) -> str:
        return f"{self.scope}::{self.root}"


@dataclass(frozen=True, slots=True)
class DefinitionNode:
    """A definition (root model, calculation or verification) and the leaves it produces."""

    id: DefinitionId
    kind: NodeKind
    outputs: tuple[ProjectPath, ...]
    user_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(frozen=True, slots=True)
class InputBinding:
    """One function parameter of a consumer and where its value comes from."""

    param: str
    ref: ProjectPath
    leaves: frozenset[ProjectPath]


@dataclass(frozen=True, slots=True)
class DataEdge:
    """`target` reads data produced by `source`, through the listed parameter bindings."""

    source: DefinitionId
    target: DefinitionId
    bindings: tuple[InputBinding, ...]


@dataclass(frozen=True, slots=True)
class AssumeEdge:
    """`target` carries `@vq.assume(...)` pointing at the verification `source`.

    This is a premise relation, not a data dependency: `source` may itself depend on
    `target`'s output (compute assuming X, then verify X from the result). It is kept
    apart from `DataEdge` and never used for ordering.
    """

    source: DefinitionId
    target: DefinitionId


@dataclass(frozen=True, slots=True)
class UpstreamSubgraph:
    """Everything `target` transitively depends on, at definition granularity.

    `nodes` includes the target itself. `data_edges` and `assume_edges` are sorted
    deterministically. Edge direction is producer -> consumer.
    """

    target: DefinitionId
    nodes: Mapping[DefinitionId, DefinitionNode]
    data_edges: tuple[DataEdge, ...]
    assume_edges: tuple[AssumeEdge, ...]

    def predecessors(self, node_id: DefinitionId) -> frozenset[DefinitionId]:
        """Definitions whose data `node_id` reads directly."""
        return frozenset(edge.source for edge in self.data_edges if edge.target == node_id)

    def successors(self, node_id: DefinitionId) -> frozenset[DefinitionId]:
        """Definitions in this subgraph that read `node_id`'s data directly."""
        return frozenset(edge.target for edge in self.data_edges if edge.source == node_id)

    def assumptions_of(self, node_id: DefinitionId) -> frozenset[DefinitionId]:
        """Verifications that `node_id` assumes via `@vq.assume`."""
        return frozenset(edge.source for edge in self.assume_edges if edge.target == node_id)

    def inputs_of(self, node_id: DefinitionId) -> tuple[InputBinding, ...]:
        """All parameter bindings of `node_id`, grouped by source definition (declaration order within a group)."""
        return tuple(b for edge in self.data_edges if edge.target == node_id for b in edge.bindings)

    def input_leaves(self) -> frozenset[ProjectPath]:
        """Root-model leaf paths at the start of every chain (join key for input provenance)."""
        return frozenset(
            leaf
            for edge in self.data_edges
            if self.nodes[edge.source].kind == NodeKind.MODEL
            for binding in edge.bindings
            for leaf in binding.leaves
        )

    def topological_order(self) -> list[DefinitionId]:
        """Definitions ordered so that every producer precedes its consumers (data edges only).

        Assume edges are not ordering constraints: an assumed verification is a premise
        checked after the fact and may itself depend on the assuming definition's output,
        so including them could introduce cycles. Assumed definitions are still part of
        `nodes` and appear in the order wherever their data dependencies place them.
        """
        successors: dict[DefinitionId, set[DefinitionId]] = {node_id: set() for node_id in self.nodes}
        for edge in self.data_edges:
            successors[edge.source].add(edge.target)
        return topological_sort(successors)

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self.nodes


# =============================================================================
# Reduction
# =============================================================================


def _group_by_definition(spec: GraphSpec) -> dict[DefinitionId, list[NodeSpec]]:
    groups: dict[DefinitionId, list[NodeSpec]] = {}
    for node in spec.nodes.values():
        groups.setdefault(DefinitionId.from_path(node.id), []).append(node)
    return groups


def _is_under(leaf: ProjectPath, ref: ProjectPath) -> bool:
    """True if `leaf` is `ref` itself or lies below it in the same definition."""
    return (
        leaf.scope == ref.scope
        and leaf.path.root == ref.path.root
        and leaf.path.parts[: len(ref.path.parts)] == ref.path.parts
    )


def _bindings_of(leaves: list[NodeSpec]) -> tuple[InputBinding, ...]:
    """Parameter bindings of a definition (all its leaves share `param_mapping`)."""
    representative = leaves[0]
    dependencies = frozenset().union(*(leaf.dependencies for leaf in leaves))
    return tuple(
        InputBinding(
            param=param,
            ref=ref,
            leaves=frozenset(dep for dep in dependencies if _is_under(dep, ref)),
        )
        for param, ref in representative.param_mapping.items()
    )


def _assumed_ids(leaves: list[NodeSpec]) -> frozenset[DefinitionId]:
    assumed: set[DefinitionId] = set()
    for leaf in leaves:
        for path in leaf.metadata.get("assumed_verification_paths", ()):
            assumed.add(DefinitionId.from_path(path))
    return frozenset(assumed)


def _resolve_target(target: ProjectPath | str | DefinitionId) -> DefinitionId:
    if isinstance(target, DefinitionId):
        return target
    if isinstance(target, str):
        target = parse_project_path(target)
    return DefinitionId.from_path(target)


class _Reducer:
    """Collects definition-level nodes and edges while walking upstream of a target."""

    def __init__(self, spec: GraphSpec, *, follow_assumes: bool) -> None:
        self.groups = _group_by_definition(spec)
        self.follow_assumes = follow_assumes
        self.nodes: dict[DefinitionId, DefinitionNode] = {}
        self.data_edges: list[DataEdge] = []
        self.assume_edges: list[AssumeEdge] = []

    def add_node(self, node_id: DefinitionId) -> None:
        if node_id in self.nodes:
            return
        leaves = self.groups[node_id]
        self.nodes[node_id] = DefinitionNode(
            id=node_id,
            kind=leaves[0].kind,
            outputs=tuple(sorted((leaf.id for leaf in leaves), key=str)),
            user_metadata=leaves[0].user_metadata,
        )

    def expand(self, node_id: DefinitionId) -> Iterable[DefinitionId]:
        """Record edges into `node_id` and yield the definitions to visit next."""
        leaves = self.groups[node_id]
        by_source: dict[DefinitionId, list[InputBinding]] = {}
        for binding in _bindings_of(leaves):
            by_source.setdefault(DefinitionId.from_path(binding.ref), []).append(binding)
        for source_id, bindings in by_source.items():
            if source_id != node_id:
                self.data_edges.append(DataEdge(source=source_id, target=node_id, bindings=tuple(bindings)))
                yield source_id
        for assumed_id in _assumed_ids(leaves):
            if assumed_id not in self.groups:
                msg = f"Assumed verification not found: {assumed_id} (assumed by {node_id})"
                raise KeyError(msg)
            self.assume_edges.append(AssumeEdge(source=assumed_id, target=node_id))
            if self.follow_assumes:
                yield assumed_id
            else:
                self.add_node(assumed_id)

    def run(self, target_id: DefinitionId) -> UpstreamSubgraph:
        if target_id not in self.groups:
            msg = f"Definition not found: {target_id}"
            raise KeyError(msg)
        self.add_node(target_id)
        queue: deque[DefinitionId] = deque([target_id])
        expanded: set[DefinitionId] = set()
        while queue:
            node_id = queue.popleft()
            if node_id in expanded:
                continue
            expanded.add(node_id)
            for next_id in self.expand(node_id):
                self.add_node(next_id)
                queue.append(next_id)
        return UpstreamSubgraph(
            target=target_id,
            nodes=dict(sorted(self.nodes.items(), key=lambda kv: str(kv[0]))),
            data_edges=tuple(sorted(set(self.data_edges), key=lambda e: (str(e.source), str(e.target)))),
            assume_edges=tuple(sorted(set(self.assume_edges), key=lambda e: (str(e.source), str(e.target)))),
        )


def upstream_subgraph(
    source: Project | GraphSpec,
    target: ProjectPath | str | DefinitionId,
    *,
    follow_assumes: bool = True,
) -> UpstreamSubgraph:
    """Return the definition-level subgraph upstream of `target`.

    Args:
        source: A `Project` (its `GraphSpec` is built) or an already built `GraphSpec`.
        target: The definition to start from, as a `ProjectPath`, a `'Scope::path'` string
            (e.g. `"Power::?verify_margin"`), or a `DefinitionId`. Any leaf of the definition
            may be given; the whole definition is used.
        follow_assumes: If True (default), traversal continues through verifications referenced
            by `@vq.assume`, so the result contains the full assumption closure. If False, the
            assume edges and the assumed verifications are included but their own upstream is not.

    Raises:
        KeyError: If `target` does not name a definition in the graph.

    """
    spec = build_graph_spec(source) if isinstance(source, Project) else source
    return _Reducer(spec, follow_assumes=follow_assumes).run(_resolve_target(target))
