"""Builder functions to construct IR from user-facing types."""

from typing import TYPE_CHECKING, Any

from veriq._models import Collect, Tag
from veriq._path import (
    AttributePart,
    CalcPath,
    ModelPath,
    ProjectPath,
    VerificationPath,
    iter_leaf_path_parts,
    parse_path,
)

from ._graph_spec import GraphSpec
from ._node_spec import NodeKind, NodeSpec

if TYPE_CHECKING:
    from veriq._models import Project


TagIndex = dict[str, list[tuple[str, ModelPath, type]]]
CollectMapping = dict[str, dict[str, ProjectPath]]


def _get_leaf_type(project: Project, ppath: ProjectPath) -> type:
    """Get the type at a specific leaf path.

    Args:
        project: The Project for type resolution.
        ppath: The ProjectPath to look up.

    Returns:
        The type at the given path.

    """
    return project.get_type(ppath)


def _build_tag_index(project: Project) -> TagIndex:
    """Build an index of tags declared on root model top-level fields.

    v1 intentionally scans only direct fields of each scope's root model. Nested
    fields, calculation outputs, and richer matching forms can be added later
    without changing the collect hydration contract.

    Args:
        project: The Project whose root model fields should be indexed.

    Returns:
        Mapping from tag name to tagged root field entries.

    """
    tag_index: TagIndex = {}

    for scope_name, scope in project.scopes.items():
        root_model = scope.get_root_model()
        for field_name, field_info in root_model.model_fields.items():
            field_type = field_info.annotation
            if field_type is None:
                continue

            tags = [metadata for metadata in field_info.metadata if isinstance(metadata, Tag)]
            if not tags:
                continue

            model_path = ModelPath(root="$", parts=(AttributePart(field_name),))
            for tag in tags:
                tag_index.setdefault(tag.name, []).append((scope_name, model_path, field_type))

    return tag_index


def _collect_leaf_paths(dep_ppath: ProjectPath, dep_type: type) -> set[ProjectPath]:
    """Expand one dependency path into the leaf paths it requires."""
    leaf_paths: set[ProjectPath] = set()

    for leaf_parts in iter_leaf_path_parts(dep_type):
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
        leaf_paths.update(_collect_leaf_paths(dep_ppath, dep_type))

    return leaf_paths


def _resolve_collect_mapping(collect_specs: dict[str, Collect], tag_index: TagIndex) -> CollectMapping:
    """Resolve Collect specs to sorted project paths."""
    collect_mapping: CollectMapping = {}

    for param_name, collect in collect_specs.items():
        member_paths = []
        for scope_name, model_path, _field_type in tag_index.get(collect.tag, []):
            field_part = model_path.parts[0]
            if not isinstance(field_part, AttributePart):
                msg = f"Collect member path must start with an attribute: {model_path}"
                raise TypeError(msg)
            member_key = f"{scope_name}.{field_part.name}"
            member_paths.append((member_key, ProjectPath(scope=scope_name, path=model_path)))

        collect_mapping[param_name] = dict(sorted(member_paths, key=lambda item: item[0]))

    return collect_mapping


def _collect_collect_leaf_paths(collect_mapping: CollectMapping, project: Project) -> set[ProjectPath]:
    """Collect leaf dependencies required by collective inputs."""
    leaf_paths: set[ProjectPath] = set()

    for member_mapping in collect_mapping.values():
        for member_ppath in member_mapping.values():
            member_type = project.get_type(member_ppath)
            leaf_paths.update(_collect_leaf_paths(member_ppath, member_type))

    return leaf_paths


def _register_dependency_types(
    type_registry: dict[ProjectPath, type],
    dep_ppaths: dict[str, ProjectPath],
    project: Project,
) -> None:
    """Register high-level dependency path types for hydration."""
    for dep_ppath in dep_ppaths.values():
        if dep_ppath not in type_registry:
            type_registry[dep_ppath] = project.get_type(dep_ppath)


def _register_collect_member_types(
    type_registry: dict[ProjectPath, type],
    collect_mapping: CollectMapping,
    project: Project,
) -> None:
    """Register collect member path types for hydration."""
    for member_mapping in collect_mapping.values():
        for member_ppath in member_mapping.values():
            if member_ppath not in type_registry:
                type_registry[member_ppath] = project.get_type(member_ppath)


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
    tag_index = _build_tag_index(project)

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
            collect_mapping = _resolve_collect_mapping(calc.collect_specs, tag_index)

            # Collect all input leaf paths as dependencies
            deps = _collect_input_leaf_paths(calc.dep_ppaths, project)
            deps.update(_collect_collect_leaf_paths(collect_mapping, project))

            # Register types for all dependency paths (including non-leaf paths)
            # This is needed for hydration of nested models
            _register_dependency_types(type_registry, calc.dep_ppaths, project)
            _register_collect_member_types(type_registry, collect_mapping, project)

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
                # Convert assumed_refs to ProjectPaths for the evaluation engine
                if calc.assumed_refs:
                    assumed_paths = []
                    for ref in calc.assumed_refs:
                        # Use the scope from Ref, or default to the calculation's scope
                        ref_scope = ref.scope if ref.scope is not None else scope_name
                        verif_ppath = ProjectPath(
                            scope=ref_scope,
                            path=parse_path(ref.path),
                        )
                        assumed_paths.append(verif_ppath)
                    metadata["assumed_verification_paths"] = assumed_paths

                nodes[leaf_ppath] = NodeSpec(
                    id=leaf_ppath,
                    kind=NodeKind.CALCULATION,
                    dependencies=frozenset(deps),
                    output_type=leaf_type,
                    compute_fn=calc.func,
                    param_mapping=dict(calc.dep_ppaths),
                    collect_mapping=collect_mapping,
                    metadata=metadata,
                )
                type_registry[leaf_ppath] = leaf_type

        # 3. Create VERIFICATION nodes
        for verif_name, verif in scope.verifications.items():
            collect_mapping = _resolve_collect_mapping(verif.collect_specs, tag_index)

            # Collect all input leaf paths as dependencies
            deps = _collect_input_leaf_paths(verif.dep_ppaths, project)
            deps.update(_collect_collect_leaf_paths(collect_mapping, project))

            # Register types for all dependency paths (including non-leaf paths)
            _register_dependency_types(type_registry, verif.dep_ppaths, project)
            _register_collect_member_types(type_registry, collect_mapping, project)

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
                # Convert assumed_refs to ProjectPaths for the evaluation engine
                if verif.assumed_refs:
                    assumed_paths = []
                    for ref in verif.assumed_refs:
                        # Use the scope from Ref, or default to the verification's scope
                        ref_scope = ref.scope if ref.scope is not None else scope_name
                        verif_ppath = ProjectPath(
                            scope=ref_scope,
                            path=parse_path(ref.path),
                        )
                        assumed_paths.append(verif_ppath)
                    metadata["assumed_verification_paths"] = assumed_paths

                nodes[leaf_ppath] = NodeSpec(
                    id=leaf_ppath,
                    kind=NodeKind.VERIFICATION,
                    dependencies=frozenset(deps),
                    output_type=leaf_type,
                    compute_fn=verif.func,
                    param_mapping=dict(verif.dep_ppaths),
                    collect_mapping=collect_mapping,
                    metadata=metadata,
                )
                type_registry[leaf_ppath] = leaf_type

    return GraphSpec(
        nodes=nodes,
        scope_names=tuple(project.scopes.keys()),
        type_registry=type_registry,
    )
