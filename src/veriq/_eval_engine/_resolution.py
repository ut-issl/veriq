"""Value resolution utilities for the evaluation engine."""

from typing import TYPE_CHECKING, Any

from veriq._path import (
    CalcPath,
    ModelPath,
    ProjectPath,
    hydrate_value_by_leaf_values,
    iter_leaf_path_parts,
)

if TYPE_CHECKING:
    from veriq._ir import GraphSpec


def hydrate_inputs(
    param_mapping: dict[str, ProjectPath],
    values: dict[ProjectPath, Any],
    graph_spec: GraphSpec,
) -> dict[str, Any]:
    """Hydrate function inputs from leaf values.

    Given a mapping from parameter names to their source ProjectPaths,
    reconstruct the full objects from the leaf values stored in the
    results dictionary.

    Args:
        param_mapping: Maps function parameter names to source ProjectPaths.
        values: Dictionary of computed leaf values.
        graph_spec: The GraphSpec for type information.

    Returns:
        Dictionary mapping parameter names to hydrated values.

    Raises:
        KeyError: If a required leaf value is missing.

    """
    input_values: dict[str, Any] = {}

    for param_name, dep_ppath in param_mapping.items():
        dep_type = graph_spec.get_type(dep_ppath)

        # Collect leaf values for this dependency
        leaf_values: dict[tuple, Any] = {}
        for leaf_parts in iter_leaf_path_parts(dep_type):
            # Build the full leaf path
            full_leaf_parts = dep_ppath.path.parts + leaf_parts

            if isinstance(dep_ppath.path, CalcPath):
                leaf_path = CalcPath(root=dep_ppath.path.root, parts=full_leaf_parts)
            elif isinstance(dep_ppath.path, ModelPath):
                leaf_path = ModelPath(root="$", parts=full_leaf_parts)
            else:
                msg = f"Unsupported path type: {type(dep_ppath.path)}"
                raise TypeError(msg)

            leaf_ppath = ProjectPath(scope=dep_ppath.scope, path=leaf_path)

            if leaf_ppath not in values:
                msg = f"Missing value for path: {leaf_ppath}"
                raise KeyError(msg)

            leaf_values[leaf_parts] = values[leaf_ppath]

        # Hydrate the full value from leaves
        input_values[param_name] = hydrate_value_by_leaf_values(dep_type, leaf_values)

    return input_values
