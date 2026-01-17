"""Evaluation engine module for veriq.

This module provides pure functions for evaluating computation graphs.
The evaluation engine takes a GraphSpec and initial values, and produces
computed results without side effects.

Key types:
- EvaluationResult: Structured result containing computed values and errors
- evaluate_graph: Pure function to evaluate a GraphSpec
"""

from ._engine import EvaluationResult, evaluate_graph

__all__ = ["EvaluationResult", "evaluate_graph"]
