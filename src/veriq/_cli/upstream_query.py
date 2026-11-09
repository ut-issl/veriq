"""Functional core for the `veriq upstream` command.

Builds a report over the definition-level upstream subgraph of a node: the nodes and
edges, optional metadata aggregation (sequential total over the node set and a
propagated value along the DAG), and the provenance of the root-model inputs the
target ultimately reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from veriq._io import load_provenance_from_toml
from veriq._ir import build_graph_spec
from veriq._subgraph import DefinitionId, UpstreamSubgraph, upstream_subgraph

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from veriq._models import Project
    from veriq._path import ProjectPath


class Combine(StrEnum):
    """How propagated predecessor values are merged (see `UpstreamSubgraph.propagate`)."""

    MAX = "max"
    SUM = "sum"


_COMBINE_FUNCS: dict[Combine, Callable[[Iterable[float]], float]] = {
    Combine.MAX: max,
    Combine.SUM: sum,
}


@dataclass(frozen=True, slots=True)
class MetadataAggregation:
    """Aggregation of one numeric metadata key over an upstream subgraph."""

    key: str
    combine: Combine
    default: float
    own: dict[DefinitionId, float]
    propagated: dict[DefinitionId, float]
    total: float
    """Sequential total: sum of `own` over the node set (each definition once)."""


@dataclass(frozen=True, slots=True)
class InputLeafInfo:
    """Provenance of one root-model leaf the target ultimately reads."""

    path: ProjectPath
    field_metadata: dict[str, Any]
    """From `vq.Meta` on the field definition (code side)."""
    provenance: dict[str, Any]
    """From the input TOML `provenance` table. Empty if no input file was given."""


@dataclass(frozen=True, slots=True)
class UpstreamReport:
    """Everything `veriq upstream` renders."""

    subgraph: UpstreamSubgraph
    order: list[DefinitionId]
    aggregation: MetadataAggregation | None
    inputs: list[InputLeafInfo]
    provenance_loaded: bool
    """True when an input TOML was read, so empty `provenance` means "none recorded"."""

    @property
    def propagated_at_target(self) -> float | None:
        if self.aggregation is None:
            return None
        return self.aggregation.propagated[self.subgraph.target]


def build_upstream_report(  # noqa: PLR0913
    project: Project,
    target: str | ProjectPath | DefinitionId,
    *,
    key: str | None = None,
    combine: Combine = Combine.MAX,
    default: float = 0.0,
    follow_assumes: bool = True,
    input_path: Path | None = None,
) -> UpstreamReport:
    """Build the upstream report for `target`.

    Raises:
        KeyError: If `target` does not name a definition.
        TypeError: If a node's metadata value under `key` is not a number.
        ProvenanceError: If the input TOML's `provenance` table does not match the model.

    """
    spec = build_graph_spec(project)
    sub = upstream_subgraph(spec, target, follow_assumes=follow_assumes)
    order = sub.topological_order()

    aggregation: MetadataAggregation | None = None
    if key is not None:
        # propagate_all validates that every value under `key` is numeric (raises TypeError)
        propagated = sub.propagate_all(
            key,
            combine=_COMBINE_FUNCS[combine],
            default=default,
        )
        own = {node_id: float(node.user_metadata.get(key, default)) for node_id, node in sub.nodes.items()}
        aggregation = MetadataAggregation(
            key=key,
            combine=combine,
            default=default,
            own=own,
            propagated=propagated,
            total=sum(own.values()),
        )

    provenance = load_provenance_from_toml(project, input_path) if input_path is not None else {}
    inputs = [
        InputLeafInfo(
            path=leaf,
            field_metadata=dict(spec.get_node(leaf).field_metadata),
            provenance=dict(provenance.get(leaf, {})),
        )
        for leaf in sorted(sub.input_leaves(), key=str)
    ]

    return UpstreamReport(
        subgraph=sub,
        order=order,
        aggregation=aggregation,
        inputs=inputs,
        provenance_loaded=input_path is not None,
    )


def report_to_dict(report: UpstreamReport) -> dict[str, Any]:
    """Convert a report to a JSON-friendly dict (callers serialize with `default=str`)."""
    sub = report.subgraph
    agg = report.aggregation
    nodes = [
        {
            "id": str(node_id),
            "scope": node_id.scope,
            "root": node_id.root,
            "kind": sub.nodes[node_id].kind.value,
            "outputs": [str(p) for p in sub.nodes[node_id].outputs],
            "user_metadata": dict(sub.nodes[node_id].user_metadata),
            **(
                {
                    "value": agg.own[node_id],
                    "propagated": agg.propagated[node_id],
                }
                if agg is not None
                else {}
            ),
        }
        for node_id in report.order
    ]
    data_edges = [
        {
            "source": str(edge.source),
            "target": str(edge.target),
            "bindings": [
                {
                    "param": b.param,
                    "ref": str(b.ref),
                    "leaves": [str(leaf) for leaf in sorted(b.leaves, key=str)],
                }
                for b in edge.bindings
            ],
        }
        for edge in sub.data_edges
    ]
    assume_edges = [{"source": str(e.source), "target": str(e.target)} for e in sub.assume_edges]
    inputs = [
        {
            "path": str(info.path),
            "field_metadata": info.field_metadata,
            "provenance": info.provenance,
        }
        for info in report.inputs
    ]
    result: dict[str, Any] = {
        "target": str(sub.target),
        "nodes": nodes,
        "data_edges": data_edges,
        "assume_edges": assume_edges,
        "inputs": inputs,
        "provenance_loaded": report.provenance_loaded,
    }
    if agg is not None:
        result["aggregation"] = {
            "key": agg.key,
            "combine": agg.combine.value,
            "default": agg.default,
            "total": agg.total,
            "propagated": report.propagated_at_target,
        }
    return result
