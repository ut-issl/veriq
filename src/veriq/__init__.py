"""Requirements verification tool."""

__all__ = [
    "DependencyGraph",
    "EvaluationResult",
    "GraphSpec",
    "NodeKind",
    "NodeSpec",
    "Project",
    "Ref",
    "Requirement",
    "Scope",
    "Table",
    "assume",
    "build_graph_spec",
    "depends",
    "evaluate_graph",
    "evaluate_project",
    "export_to_toml",
    "is_valid_verification_return_type",
    "load_model_data_from_toml",
]

from ._decorators import assume
from ._eval import evaluate_project
from ._eval_engine import EvaluationResult, evaluate_graph
from ._graph import DependencyGraph
from ._io import export_to_toml, load_model_data_from_toml
from ._ir import GraphSpec, NodeKind, NodeSpec, build_graph_spec
from ._models import Project, Ref, Requirement, Scope, is_valid_verification_return_type
from ._relations import depends
from ._table import Table
