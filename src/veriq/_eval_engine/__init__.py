"""Evaluation engine module for veriq.

This module provides pure functions for evaluating computation graphs.
The evaluation engine takes a GraphSpec and initial values, and produces
computed results without side effects.

Key types:
- EvaluationResult: Structured result containing computed values and errors
- PathNode: A node in the path tree (leaf or intermediate)
- ScopeTree: Tree of values for a single scope
- evaluate_graph: Pure function to evaluate a GraphSpec
"""

from ._engine import EvaluationResult, evaluate_graph
from ._tree import PathNode, ScopeTree, build_scope_trees

__all__ = [
    "EvaluationResult",
    "PathNode",
    "ScopeTree",
    "build_scope_trees",
    "evaluate_graph",
]
