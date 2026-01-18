"""Core evaluation engine for computation graphs."""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from veriq._graph import DependencyGraph
from veriq._ir import NodeKind
from veriq._path import (
    CalcPath,
    ModelPath,
    ProjectPath,
    VerificationPath,
    get_value_by_parts,
    iter_leaf_path_parts,
)

from ._resolution import hydrate_inputs

if TYPE_CHECKING:
    from veriq._ir import GraphSpec

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Result of evaluating a computation graph.

    This is an immutable data structure containing all computed values,
    validity tracking, and any errors that occurred during evaluation.

    Attributes:
        values: Mapping from node path to computed value. Invalid verifications
            are overridden to False in this dict.
        errors: List of (node_path, error_message) for any failed evaluations.
        validity: Mapping from node path to validity status. True means the node's
            assumptions hold, False means an assumed verification failed.

    """

    values: dict[ProjectPath, Any] = field(default_factory=dict)
    errors: list[tuple[ProjectPath, str]] = field(default_factory=list)
    validity: dict[ProjectPath, bool] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if evaluation completed without errors."""
        return len(self.errors) == 0

    def get_value(self, path: ProjectPath) -> Any:
        """Get a computed value by path.

        Args:
            path: The ProjectPath to look up.

        Returns:
            The computed value at the given path.

        Raises:
            KeyError: If no value exists at the given path.

        """
        return self.values[path]

    def is_valid(self, path: ProjectPath) -> bool:
        """Check if a value at path is valid (all assumptions hold).

        Args:
            path: The ProjectPath to check.

        Returns:
            True if the value is valid (assumptions hold), False otherwise.
            Returns True if the path is not in the validity dict (no assumptions).

        """
        return self.validity.get(path, True)


def _get_function_key(path: ProjectPath) -> str:
    """Get a unique key for the function associated with a path.

    Multiple leaf paths may share the same underlying function.
    This key identifies the function so we only call it once.
    """
    return f"{path.scope}::{path.path.root}"


def _check_validity(  # noqa: C901, PLR0912
    graph_spec: GraphSpec,
    values: dict[ProjectPath, Any],
    eval_order: list[ProjectPath],
) -> dict[ProjectPath, bool]:
    """Check validity based on assumed verifications.

    A node is invalid if:
    1. It assumes a verification that returned False (or was not evaluated)
    2. It depends on a node that is invalid (transitive invalidity)

    IMPORTANT: This function modifies `values` in place - invalid verification
    values are overridden to False to ensure consistent behavior for all API users.

    Args:
        graph_spec: The specification of nodes and their dependencies.
        values: The computed values dict (will be modified in place for invalid verifications).
        eval_order: The topological order of evaluation.

    Returns:
        Dictionary mapping paths to validity status (True = valid).

    """
    validity: dict[ProjectPath, bool] = dict.fromkeys(values, True)

    # First pass: Check direct assumptions
    # Group nodes by function key to handle multiple leaf paths from same function
    func_assumptions: dict[str, list[ProjectPath]] = {}
    func_nodes: dict[str, list[ProjectPath]] = {}

    for path, spec in graph_spec.nodes.items():
        if spec.kind in (NodeKind.CALCULATION, NodeKind.VERIFICATION):
            func_key = _get_function_key(path)
            func_nodes.setdefault(func_key, []).append(path)
            assumed_paths = spec.metadata.get("assumed_verification_paths", [])
            if assumed_paths and func_key not in func_assumptions:
                func_assumptions[func_key] = assumed_paths

    # Mark nodes invalid if their assumed verifications failed
    for func_key, assumed_paths in func_assumptions.items():
        assumption_holds = True
        for assumed_path in assumed_paths:
            # Check ALL leaf paths of the verification (for Table[K, bool])
            # The assumed_path is the root verification path, we need to find all leaves
            verif_results = [
                values.get(p)
                for p in values
                if p.scope == assumed_path.scope and p.path.root == assumed_path.path.root
            ]
            # Assumption holds only if ALL verification results are True
            if not all(v is True for v in verif_results if v is not None):
                assumption_holds = False
                break

        if not assumption_holds:
            for output_path in func_nodes.get(func_key, []):
                validity[output_path] = False

    # Second pass: Propagate invalidity through dependencies (in topological order)
    for path in eval_order:
        if path not in validity:
            continue
        if not validity[path]:
            continue  # Already invalid

        spec = graph_spec.nodes.get(path)
        if spec is None:
            continue

        # Check if any dependency is invalid
        for dep_path in spec.dependencies:
            if not validity.get(dep_path, True):
                validity[path] = False
                break

    # Override invalid verification values to False
    # This ensures consistent behavior for both Python API and CLI users
    for path, is_valid in validity.items():
        if not is_valid and isinstance(path.path, VerificationPath):
            values[path] = False

    return validity


def _make_output_leaf_path(
    base_path: ProjectPath,
    leaf_parts: tuple,
) -> ProjectPath:
    """Create an output leaf path from a base path and leaf parts."""
    if isinstance(base_path.path, CalcPath):
        leaf_path = CalcPath(root=base_path.path.root, parts=leaf_parts)
    elif isinstance(base_path.path, VerificationPath):
        leaf_path = VerificationPath(root=base_path.path.root, parts=leaf_parts)
    else:
        msg = f"Cannot create output leaf path for: {type(base_path.path)}"
        raise TypeError(msg)

    return ProjectPath(scope=base_path.scope, path=leaf_path)


def evaluate_graph(  # noqa: C901
    graph_spec: GraphSpec,
    initial_values: dict[ProjectPath, Any],
) -> EvaluationResult:
    """Evaluate the computation graph with given initial values.

    This is a pure function that:
    1. Builds a DependencyGraph from the GraphSpec
    2. Validates the graph (checks for cycles, missing dependencies)
    3. Computes topological order
    4. Evaluates each node in order, resolving dependencies from computed values

    Args:
        graph_spec: The specification of nodes and their dependencies.
        initial_values: Values for MODEL nodes (input data from TOML/etc).

    Returns:
        EvaluationResult containing computed values and any errors.

    Example:
        >>> spec = build_graph_spec(project)
        >>> initial = {path: value for path, value in model_data}
        >>> result = evaluate_graph(spec, initial)
        >>> if result.success:
        ...     print(result.values)

    """
    # Build the dependency graph from node specs
    edges: list[tuple[ProjectPath, ProjectPath]] = []
    for node in graph_spec.nodes.values():
        edges.extend((dep, node.id) for dep in node.dependencies)

    graph = DependencyGraph.from_edges(edges)

    # Add isolated nodes (MODEL nodes with no dependents may not have edges)
    # We need to ensure all nodes are in the graph for proper ordering

    # Validate the graph
    validation_errors = graph.validate()
    if validation_errors:
        return EvaluationResult(
            values={},
            errors=[
                (
                    ProjectPath(
                        scope="__validation__",
                        path=ModelPath(root="$", parts=()),
                    ),
                    err,
                )
                for err in validation_errors
            ],
        )

    # Get evaluation order
    try:
        eval_order = graph.topological_order()
    except ValueError as e:
        return EvaluationResult(
            values={},
            errors=[
                (
                    ProjectPath(
                        scope="__validation__",
                        path=ModelPath(root="$", parts=()),
                    ),
                    str(e),
                ),
            ],
        )

    # Initialize values with initial_values
    values: dict[ProjectPath, Any] = dict(initial_values)
    errors: list[tuple[ProjectPath, str]] = []

    # Track which functions have been evaluated
    # (Multiple leaf paths share the same underlying function)
    evaluated_functions: set[str] = set()

    logger.debug("Starting evaluation with %d nodes in order", len(eval_order))

    for node_path in eval_order:
        # Skip if already have value (MODEL node or already computed)
        if node_path in values:
            logger.debug("Skipping %s (already has value)", node_path)
            continue

        spec = graph_spec.nodes.get(node_path)
        if spec is None:
            errors.append((node_path, f"No spec found for node {node_path}"))
            continue

        if spec.kind == NodeKind.MODEL:
            errors.append((node_path, f"Missing initial value for model node {node_path}"))
            continue

        # For CALCULATION and VERIFICATION nodes
        if spec.compute_fn is None:
            errors.append((node_path, f"No compute function for node {node_path}"))
            continue

        # Check if we've already evaluated this function
        func_key = _get_function_key(node_path)
        if func_key in evaluated_functions:
            # Value should already be computed by the first leaf path
            continue

        logger.debug("Evaluating %s", node_path)

        # Hydrate inputs from leaf values
        try:
            input_values = hydrate_inputs(
                spec.param_mapping,
                values,
                graph_spec,
            )
        except KeyError as e:
            errors.append((node_path, f"Missing dependency value: {e}"))
            continue

        # Call the function
        try:
            result = spec.compute_fn(**input_values)
        except (TypeError, ValueError, AttributeError, KeyError, RuntimeError) as e:
            errors.append((node_path, f"Evaluation error: {e}"))
            continue

        logger.debug("Result for %s: %r", node_path, result)

        # Decompose result into leaf values
        # Use root_output_type from metadata to get the full output structure
        root_output_type = spec.metadata.get("root_output_type", spec.output_type)
        for leaf_parts in iter_leaf_path_parts(root_output_type):
            leaf_ppath = _make_output_leaf_path(node_path, leaf_parts)
            leaf_value = get_value_by_parts(result, leaf_parts)
            values[leaf_ppath] = leaf_value
            logger.debug("  Set %s = %r", leaf_ppath, leaf_value)

        evaluated_functions.add(func_key)

    # Check validity based on assumed verifications
    # Note: _check_validity modifies values in place for invalid verifications
    # (invalid verifications are overridden to False)
    validity = _check_validity(graph_spec, values, eval_order)

    return EvaluationResult(values=values, errors=errors, validity=validity)
