"""Requirements verification tool."""

__all__ = [
    "AssumeEdge",
    "ChecksumValidationEntry",
    "ChecksumValidationResult",
    "DataEdge",
    "DefinitionId",
    "DefinitionNode",
    "DefinitionNotFoundError",
    "DependencyGraph",
    "EvaluationResult",
    "ExternalData",
    "FileRef",
    "GraphSpec",
    "InputBinding",
    "Meta",
    "NodeKind",
    "NodeSpec",
    "PathNode",
    "Project",
    "ProvenanceError",
    "Ref",
    "Requirement",
    "RequirementStatus",
    "RequirementTraceEntry",
    "Scope",
    "ScopeTree",
    "StrEnumWithDoc",
    "Table",
    "TableFieldHandler",
    "TraceabilityReport",
    "UpstreamSubgraph",
    "VerificationResult",
    "assume",
    "build_graph_spec",
    "build_traceability_report",
    "depends",
    "evaluate_graph",
    "evaluate_project",
    "export_to_toml",
    "input_base_dir",
    "is_valid_verification_return_type",
    "load_model_data_from_toml",
    "load_project",
    "load_provenance_from_toml",
    "toml_to_provenance",
    "upstream_subgraph",
    "validate_external_data",
    "with_range",
]

# bounded-models integration
from ._bounded_models import TableFieldHandler
from ._decorators import assume
from ._discover import load_project
from ._eval import evaluate_project
from ._eval_engine import EvaluationResult, PathNode, ScopeTree, evaluate_graph
from ._external_data import (
    ChecksumValidationEntry,
    ChecksumValidationResult,
    ExternalData,
    FileRef,
    validate_external_data,
)
from ._graph import DependencyGraph
from ._io import export_to_toml, input_base_dir, load_model_data_from_toml, load_provenance_from_toml
from ._ir import GraphSpec, NodeKind, NodeSpec, build_graph_spec
from ._models import Project, Ref, Requirement, Scope, is_valid_verification_return_type
from ._provenance import Meta, ProvenanceError, toml_to_provenance
from ._range_enum import with_range
from ._relations import depends
from ._str_enum_with_doc import StrEnumWithDoc
from ._subgraph import (
    AssumeEdge,
    DataEdge,
    DefinitionId,
    DefinitionNode,
    DefinitionNotFoundError,
    InputBinding,
    UpstreamSubgraph,
    upstream_subgraph,
)
from ._table import Table
from ._traceability import (
    RequirementStatus,
    RequirementTraceEntry,
    TraceabilityReport,
    VerificationResult,
    build_traceability_report,
)
