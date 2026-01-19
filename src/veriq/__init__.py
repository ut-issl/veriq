"""Requirements verification tool."""

__all__ = [
    "ChecksumValidationEntry",
    "ChecksumValidationResult",
    "DependencyGraph",
    "EvaluationResult",
    "ExternalData",
    "FileRef",
    "GraphSpec",
    "NodeKind",
    "NodeSpec",
    "Project",
    "Ref",
    "Requirement",
    "RequirementStatus",
    "RequirementTraceEntry",
    "Scope",
    "Table",
    "TableFieldHandler",
    "TraceabilityReport",
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
    "validate_external_data",
]

from ._decorators import assume
from ._eval import evaluate_project
from ._eval_engine import EvaluationResult, evaluate_graph
from ._external_data import (
    ChecksumValidationEntry,
    ChecksumValidationResult,
    ExternalData,
    FileRef,
    validate_external_data,
)
from ._graph import DependencyGraph
from ._io import export_to_toml, input_base_dir, load_model_data_from_toml
from ._ir import GraphSpec, NodeKind, NodeSpec, build_graph_spec
from ._models import Project, Ref, Requirement, Scope, is_valid_verification_return_type
from ._relations import depends
from ._table import Table
from ._traceability import (
    RequirementStatus,
    RequirementTraceEntry,
    TraceabilityReport,
    VerificationResult,
    build_traceability_report,
)

# Optional bounded-models integration
try:
    from ._bounded_models import TableFieldHandler
except ImportError:

    def __getattr__(name: str) -> object:
        if name == "TableFieldHandler":
            msg = "TableFieldHandler requires bounded-models to be installed. Install with: pip install bounded-models"
            raise ImportError(msg)
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
