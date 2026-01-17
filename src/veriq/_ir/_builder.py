"""Builder functions to construct IR from user-facing types."""

from typing import TYPE_CHECKING, Any

from veriq._path import (
    CalcPath,
    ModelPath,
    ProjectPath,
    VerificationPath,
    iter_leaf_path_parts,
)

from ._graph_spec import GraphSpec
from ._node_spec import NodeKind, NodeSpec

if TYPE_CHECKING:
    from veriq._models import Project


def _get_leaf_type(project: Project, ppath: ProjectPath) -> type:
    """Get the type at a specific leaf path.

    Args:
        project: The Project for type resolution.
        ppath: The ProjectPath to look up.

    Returns:
        The type at the given path.

    """
    return project.get_type(ppath)


def _collect_input_leaf_paths(
    dep_ppaths: dict[str, ProjectPath],
    project: Project,
) -> set[ProjectPath]:
    """Collect all leaf paths from a set of dependency paths.

    This expands high-level dependency paths (which may point to Pydantic models
    or Tables) into their constituent leaf paths.

    Args:
        dep_ppaths: Mapping from parameter name to dependency ProjectPath.
        project: The Project for type resolution.

    Returns:
        Set of all leaf ProjectPaths that the dependencies expand to.

    """
    leaf_paths: set[ProjectPath] = set()

    for dep_ppath in dep_ppaths.values():
        dep_type = project.get_type(dep_ppath)
        for leaf_parts in iter_leaf_path_parts(dep_type):
            # Build the full leaf path by appending leaf parts to the dependency path
            src_leaf_abs_parts = dep_ppath.path.parts + leaf_parts

            if isinstance(dep_ppath.path, ModelPath):
                src_leaf_path = ModelPath(root="$", parts=src_leaf_abs_parts)
            elif isinstance(dep_ppath.path, CalcPath):
                src_leaf_path = CalcPath(root=dep_ppath.path.root, parts=src_leaf_abs_parts)
            else:
                msg = f"Unsupported dependency path type: {type(dep_ppath.path)}"
                raise TypeError(msg)

            leaf_paths.add(ProjectPath(scope=dep_ppath.scope, path=src_leaf_path))

    return leaf_paths


def build_graph_spec(project: Project) -> GraphSpec:  # noqa: C901
    """Build a GraphSpec from a user-facing Project.

    This is the bridge between the user-facing layer and the core layer.
    It extracts all necessary information from Project/Scope/Calculation/Verification
    and creates a pure data representation suitable for evaluation.

    The function:
    1. Creates MODEL nodes for all leaf paths in root models
    2. Creates CALCULATION nodes for all calculation output leaves
    3. Creates VERIFICATION nodes for all verification output leaves
    4. Builds a type registry for all paths (including non-leaf paths for hydration)

    Args:
        project: The user-facing Project object.

    Returns:
        A GraphSpec containing all nodes and their dependencies.

    Example:
        >>> project = Project(name="MyProject")
        >>> # ... set up scopes, models, calculations, verifications ...
        >>> spec = build_graph_spec(project)
        >>> len(spec.nodes)
        42

    """
    nodes: dict[ProjectPath, NodeSpec] = {}
    type_registry: dict[ProjectPath, type] = {}

    for scope_name, scope in project.scopes.items():
        # 1. Create MODEL nodes for root model leaf paths
        root_model = scope.get_root_model()
        for leaf_parts in iter_leaf_path_parts(root_model):
            leaf_ppath = ProjectPath(
                scope=scope_name,
                path=ModelPath(root="$", parts=leaf_parts),
            )
            leaf_type = _get_leaf_type(project, leaf_ppath)

            nodes[leaf_ppath] = NodeSpec(
                id=leaf_ppath,
                kind=NodeKind.MODEL,
                dependencies=frozenset(),
                output_type=leaf_type,
                compute_fn=None,
                param_mapping={},
                metadata={},
            )
            type_registry[leaf_ppath] = leaf_type

        # 2. Create CALCULATION nodes
        for calc_name, calc in scope.calculations.items():
            # Collect all input leaf paths as dependencies
            deps = _collect_input_leaf_paths(calc.dep_ppaths, project)

            # Register types for all dependency paths (including non-leaf paths)
            # This is needed for hydration of nested models
            for dep_ppath in calc.dep_ppaths.values():
                if dep_ppath not in type_registry:
                    type_registry[dep_ppath] = project.get_type(dep_ppath)

            # Create a node for each output leaf path
            for leaf_parts in iter_leaf_path_parts(calc.output_type):
                leaf_ppath = ProjectPath(
                    scope=scope_name,
                    path=CalcPath(root=f"@{calc_name}", parts=leaf_parts),
                )
                leaf_type = _get_leaf_type(project, leaf_ppath)

                # Build metadata
                metadata: dict[str, Any] = {
                    # Store the full output type for decomposition during evaluation
                    "root_output_type": calc.output_type,
                }
                if calc.assumed_verifications:
                    metadata["assumed_verifications"] = calc.assumed_verifications

                nodes[leaf_ppath] = NodeSpec(
                    id=leaf_ppath,
                    kind=NodeKind.CALCULATION,
                    dependencies=frozenset(deps),
                    output_type=leaf_type,
                    compute_fn=calc.func,
                    param_mapping=dict(calc.dep_ppaths),
                    metadata=metadata,
                )
                type_registry[leaf_ppath] = leaf_type

        # 3. Create VERIFICATION nodes
        for verif_name, verif in scope.verifications.items():
            # Collect all input leaf paths as dependencies
            deps = _collect_input_leaf_paths(verif.dep_ppaths, project)

            # Register types for all dependency paths (including non-leaf paths)
            for dep_ppath in verif.dep_ppaths.values():
                if dep_ppath not in type_registry:
                    type_registry[dep_ppath] = project.get_type(dep_ppath)

            # Create a node for each output leaf path
            for leaf_parts in iter_leaf_path_parts(verif.output_type):
                leaf_ppath = ProjectPath(
                    scope=scope_name,
                    path=VerificationPath(root=f"?{verif_name}", parts=leaf_parts),
                )
                leaf_type = _get_leaf_type(project, leaf_ppath)

                # Build metadata
                metadata: dict[str, Any] = {
                    "xfail": verif.xfail,
                    # Store the full output type for decomposition during evaluation
                    "root_output_type": verif.output_type,
                }
                if verif.assumed_verifications:
                    metadata["assumed_verifications"] = verif.assumed_verifications

                nodes[leaf_ppath] = NodeSpec(
                    id=leaf_ppath,
                    kind=NodeKind.VERIFICATION,
                    dependencies=frozenset(deps),
                    output_type=leaf_type,
                    compute_fn=verif.func,
                    param_mapping=dict(verif.dep_ppaths),
                    metadata=metadata,
                )
                type_registry[leaf_ppath] = leaf_type

    return GraphSpec(
        nodes=nodes,
        scope_names=tuple(project.scopes.keys()),
        type_registry=type_registry,
    )
