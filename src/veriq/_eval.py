"""Evaluate a project with model data.

This module provides the public API for project evaluation.
It delegates to the new evaluation engine internally.
"""

import logging
from typing import TYPE_CHECKING, Any

from ._eval_engine import evaluate_graph
from ._ir import build_graph_spec
from ._path import ModelPath, ProjectPath, get_value_by_parts, iter_leaf_path_parts

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import BaseModel

    from ._models import Project

logger = logging.getLogger(__name__)


def evaluate_project(project: Project, model_data: Mapping[str, BaseModel]) -> dict[ProjectPath, Any]:
    """Evaluate a project with the given model data.

    This function:
    1. Extracts leaf values from model data as initial values
    2. Builds a graph specification from the project
    3. Evaluates the graph using the new evaluation engine
    4. Returns the computed values

    Args:
        project: The project to evaluate.
        model_data: Mapping from scope name to the model data for that scope.

    Returns:
        A dictionary mapping ProjectPaths to their computed values.

    Raises:
        RuntimeError: If evaluation fails with errors.

    """
    # Extract initial values from model data
    initial_values: dict[ProjectPath, Any] = {}
    for scope_name, scope_data in model_data.items():
        root_model = project.scopes[scope_name].get_root_model()
        for leaf_path_parts in iter_leaf_path_parts(root_model):
            leaf_path = ProjectPath(
                scope=scope_name,
                path=ModelPath(root="$", parts=leaf_path_parts),
            )
            value = get_value_by_parts(scope_data, leaf_path_parts)
            initial_values[leaf_path] = value

    logger.debug("Initial values from model data:")
    for ppath, value in initial_values.items():
        logger.debug("  %s: %r", ppath, value)

    # Build graph spec and evaluate
    graph_spec = build_graph_spec(project)
    result = evaluate_graph(graph_spec, initial_values)

    # Check for errors
    if not result.success:
        error_messages = [f"{path}: {msg}" for path, msg in result.errors]
        msg = "Evaluation failed with errors:\n" + "\n".join(error_messages)
        raise RuntimeError(msg)

    return result.values
