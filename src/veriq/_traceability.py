"""Requirement-verification traceability analysis.

This module implements the functional core for analyzing requirement-verification
traceability. It follows the "Functional Core, Imperative Shell" pattern where
all logic is pure functions operating on immutable data structures.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any, get_args, get_origin

from ._path import ItemPart, ProjectPath, VerificationPath
from ._table import Table

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._eval_engine import EvaluationResult
    from ._models import Project, Requirement, Verification


class RequirementStatus(StrEnum):
    """Status of a requirement based on its verifications and children.

    Status values are ordered by severity for propagation:
    VERIFIED/SATISFIED (0) < NOT_VERIFIED (1) < FAILED (2)

    Parent requirement status is the maximum of its children's statuses.
    """

    # Order matters for severity comparison (worst status propagates up)
    VERIFIED = "verified"  # Has direct verifications, all passed (severity 0)
    SATISFIED = "satisfied"  # No direct verifications, but all children/deps pass (severity 0)
    NOT_VERIFIED = "not_verified"  # Leaf requirement with no verifications (severity 1)
    FAILED = "failed"  # Something failed (verification, child, or dependency) (severity 2)

    @property
    def severity(self) -> int:
        """Return severity level for status propagation."""
        match self:
            case RequirementStatus.VERIFIED | RequirementStatus.SATISFIED:
                return 0
            case RequirementStatus.NOT_VERIFIED:
                return 1
            case RequirementStatus.FAILED:
                return 2


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Result of a single verification for traceability reporting.

    For Table[K, bool] verifications, each key becomes a separate result.
    """

    scope_name: str
    verification_name: str
    passed: bool
    xfail: bool
    table_key: str | tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class RequirementTraceEntry:
    """Traceability information for a single requirement."""

    requirement_id: str
    scope_name: str
    description: str
    status: RequirementStatus
    xfail: bool
    verification_results: tuple[VerificationResult, ...]
    linked_verifications: tuple[str, ...]  # Names of linked verification functions
    child_ids: tuple[str, ...]
    depends_on_ids: tuple[str, ...]
    depth: int


@dataclass(frozen=True, slots=True)
class TraceabilityReport:
    """Complete traceability report for a project."""

    project_name: str
    entries: tuple[RequirementTraceEntry, ...]
    total_requirements: int
    verified_count: int
    satisfied_count: int
    failed_count: int
    not_verified_count: int


def _worst_status(statuses: Sequence[RequirementStatus]) -> RequirementStatus | None:
    """Return the status with highest severity, or None if empty."""
    if not statuses:
        return None
    return max(statuses, key=lambda s: s.severity)


def compute_requirement_status(
    *,
    verification_results: Sequence[VerificationResult],
    child_statuses: Sequence[RequirementStatus],
    depends_on_statuses: Sequence[RequirementStatus],
) -> RequirementStatus:
    """Compute the status of a single requirement.

    This is a pure function that determines requirement status based on:
    1. Direct verification results
    2. Child requirement statuses
    3. Dependency (depends_on) requirement statuses

    Status propagation uses max-severity logic:
    - VERIFIED/SATISFIED have severity 0
    - NOT_VERIFIED has severity 1
    - FAILED has severity 2

    The parent's status is the maximum severity among:
    - Its own verification status (VERIFIED if all pass, FAILED if any fail)
    - All child statuses
    - All depends_on statuses

    If a requirement has no verifications, children, or dependencies,
    it's a coverage gap (NOT_VERIFIED).

    Note: Verification xfail is ignored for status computation.
    A failed verification means FAILED, regardless of xfail flag.

    Args:
        verification_results: Direct verification results for this requirement.
        child_statuses: Statuses of decomposed child requirements.
        depends_on_statuses: Statuses of depends_on requirements.

    Returns:
        The computed RequirementStatus.

    """
    # Determine this requirement's own status from direct verifications
    if verification_results:
        if any(not result.passed for result in verification_results):
            own_status = RequirementStatus.FAILED
        else:
            own_status = RequirementStatus.VERIFIED
    elif child_statuses or depends_on_statuses:
        # Has children or deps but no direct verifications
        own_status = RequirementStatus.SATISFIED
    else:
        # Leaf with no verifications - coverage gap
        own_status = RequirementStatus.NOT_VERIFIED

    # Collect all statuses to propagate (children and dependencies)
    all_statuses = [own_status, *child_statuses, *depends_on_statuses]

    # Return the worst (highest severity) status
    return _worst_status(all_statuses) or RequirementStatus.NOT_VERIFIED


def collect_all_requirements(
    project: Project,
) -> dict[str, tuple[str, Requirement]]:
    """Collect all requirements from all scopes in a project.

    Args:
        project: The project to collect requirements from.

    Returns:
        Dict mapping requirement ID to (scope_name, Requirement) tuple.

    """
    result: dict[str, tuple[str, Requirement]] = {}

    for scope_name, scope in project.scopes.items():
        for req_id, requirement in scope.requirements.items():
            if req_id in result:
                existing_scope, _ = result[req_id]
                msg = (
                    f"Duplicate requirement ID '{req_id}' found in scopes "
                    f"'{existing_scope}' and '{scope_name}'."
                )
                raise ValueError(msg)
            result[req_id] = (scope_name, requirement)

    return result


def extract_verification_results(
    verification: Verification[Any, ...],
    scope_name: str,
    evaluation_results: dict[ProjectPath, Any],
) -> list[VerificationResult]:
    """Extract verification results for a single verification.

    Handles both bool and Table[K, bool] verifications.
    For Table verifications, each key becomes a separate VerificationResult.

    Args:
        verification: The verification to extract results for.
        scope_name: The scope name where the verification is defined.
        evaluation_results: The evaluation results from evaluate_project().

    Returns:
        List of VerificationResult objects.

    """
    results: list[VerificationResult] = []
    output_type = verification.output_type

    # Check if it's a Table[K, bool] verification
    origin = get_origin(output_type)
    is_table = origin is Table or (isinstance(origin, type) and issubclass(origin, Table))

    if is_table:
        # Table[K, bool] verification - find all matching leaf paths
        type_args = get_args(output_type)
        if len(type_args) == 2:
            # Look for all results matching this verification
            for ppath, value in evaluation_results.items():
                if not isinstance(ppath.path, VerificationPath):
                    continue
                if ppath.scope != scope_name:
                    continue
                if ppath.path.verification_name != verification.name:
                    continue

                # Extract table key from path parts
                table_key: str | tuple[str, ...] | None = None
                if ppath.path.parts:
                    part = ppath.path.parts[0]
                    if isinstance(part, ItemPart):
                        table_key = part.key

                results.append(
                    VerificationResult(
                        scope_name=scope_name,
                        verification_name=verification.name,
                        passed=bool(value),
                        xfail=verification.xfail,
                        table_key=table_key,
                    ),
                )
    else:
        # Simple bool verification
        ppath = ProjectPath(
            scope=scope_name,
            path=VerificationPath(root=f"?{verification.name}", parts=()),
        )
        if ppath in evaluation_results:
            results.append(
                VerificationResult(
                    scope_name=scope_name,
                    verification_name=verification.name,
                    passed=bool(evaluation_results[ppath]),
                    xfail=verification.xfail,
                ),
            )

    return results


def _get_table_key_type(output_type: type) -> type | None:
    """Extract the key type from a Table[K, bool] type annotation.

    Returns None if not a Table type.
    """
    origin = get_origin(output_type)
    is_table = origin is Table or (isinstance(origin, type) and issubclass(origin, Table))
    if not is_table:
        return None

    type_args = get_args(output_type)
    if len(type_args) >= 1:
        return type_args[0]
    return None


def _expand_verification_names(verification: Verification[Any, ...]) -> list[str]:
    """Expand a verification into all its names, including Table keys.

    For a simple bool verification, returns a single name.
    For a Table[K, bool] verification, returns names for the base and each key.

    Args:
        verification: The verification to expand.

    Returns:
        List of verification names in Scope::?name[key] format.

    """
    base_name = f"{verification.default_scope_name}::?{verification.name}"
    key_type = _get_table_key_type(verification.output_type)

    if key_type is None:
        # Simple bool verification
        return [base_name]

    # Table[K, bool] verification - expand to include base and all keys
    names = [base_name]

    # Handle Enum key types
    if isinstance(key_type, type) and issubclass(key_type, Enum):
        for member in key_type:
            names.append(f"{base_name}[{member.value}]")
    else:
        # Handle tuple of enums (multi-dimensional Table)
        origin = get_origin(key_type)
        if origin is tuple:
            enum_types = get_args(key_type)
            if all(isinstance(t, type) and issubclass(t, Enum) for t in enum_types):
                # Generate all combinations
                import itertools

                all_values = [list(enum_type) for enum_type in enum_types]
                for combo in itertools.product(*all_values):
                    key_str = ",".join(m.value for m in combo)
                    names.append(f"{base_name}[{key_str}]")

    return names


def detect_circular_dependencies(
    requirements: dict[str, tuple[str, Requirement]],
) -> list[tuple[str, ...]]:
    """Detect circular dependencies in depends_on relationships.

    Uses DFS-based cycle detection.

    Args:
        requirements: Dict mapping requirement ID to (scope_name, Requirement).

    Returns:
        List of cycles found (each cycle as tuple of requirement IDs).
        Empty list if no cycles detected.

    """
    cycles: list[tuple[str, ...]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()
    path: list[str] = []

    def dfs(req_id: str) -> None:
        if req_id in rec_stack:
            # Found a cycle - extract it from the path
            cycle_start = path.index(req_id)
            cycle = (*path[cycle_start:], req_id)
            cycles.append(cycle)
            return

        if req_id in visited:
            return

        visited.add(req_id)
        rec_stack.add(req_id)
        path.append(req_id)

        if req_id in requirements:
            _, req = requirements[req_id]
            for dep in req.depends_on:
                dfs(dep.id)

        path.pop()
        rec_stack.remove(req_id)

    for req_id in requirements:
        if req_id not in visited:
            dfs(req_id)

    return cycles


def _get_root_requirements(
    requirements: dict[str, tuple[str, Requirement]],
) -> list[tuple[str, Requirement]]:
    """Get root requirements (those not decomposed from any other requirement).

    Args:
        requirements: Dict mapping requirement ID to (scope_name, Requirement).

    Returns:
        List of (scope_name, Requirement) tuples for root requirements.

    """
    # Find all IDs that are children of some requirement
    child_ids: set[str] = set()
    for _, req in requirements.values():
        for child in req.decomposed_requirements:
            child_ids.add(child.id)

    # Root requirements are those not in child_ids
    return [(scope_name, req) for scope_name, req in requirements.values() if req.id not in child_ids]


def _build_entry(
    requirement: Requirement,
    scope_name: str,
    evaluation_results: dict[ProjectPath, Any] | None,
    computed_statuses: dict[str, RequirementStatus],
    depth: int,
) -> RequirementTraceEntry:
    """Build a trace entry for a single requirement.

    Args:
        requirement: The requirement to build an entry for.
        scope_name: The scope name where the requirement is defined.
        evaluation_results: Optional evaluation results for verification extraction.
        computed_statuses: Dict of already computed statuses for children/deps.
        depth: Hierarchy depth for indentation.

    Returns:
        RequirementTraceEntry for this requirement.

    """
    # Extract verification results if evaluation results provided
    verification_results: list[VerificationResult] = []
    if evaluation_results is not None:
        for verif in requirement.verified_by:
            verification_results.extend(
                extract_verification_results(verif, verif.default_scope_name, evaluation_results),
            )

    # Get child and dependency statuses
    child_statuses = [computed_statuses[child.id] for child in requirement.decomposed_requirements]
    depends_on_statuses = [computed_statuses[dep.id] for dep in requirement.depends_on]

    # Compute status
    if evaluation_results is not None:
        status = compute_requirement_status(
            verification_results=verification_results,
            child_statuses=child_statuses,
            depends_on_statuses=depends_on_statuses,
        )
    else:
        # Without evaluation results, we can't determine status
        # Use NOT_VERIFIED for leaf requirements, SATISFIED for parents
        has_children = bool(requirement.decomposed_requirements)
        has_deps = bool(requirement.depends_on)
        has_verifications = bool(requirement.verified_by)

        if has_children or has_deps:
            status = RequirementStatus.SATISFIED
        elif has_verifications:
            # Has verifications but no results - can't determine
            status = RequirementStatus.NOT_VERIFIED
        else:
            status = RequirementStatus.NOT_VERIFIED

    # Get linked verification names in Scope::?verification_name format
    # Expand Table verifications to include all keys
    linked_verifications_list: list[str] = []
    for verif in requirement.verified_by:
        linked_verifications_list.extend(_expand_verification_names(verif))
    linked_verifications = tuple(linked_verifications_list)

    return RequirementTraceEntry(
        requirement_id=requirement.id,
        scope_name=scope_name,
        description=requirement.description,
        status=status,
        xfail=requirement.xfail,
        verification_results=tuple(verification_results),
        linked_verifications=linked_verifications,
        child_ids=tuple(child.id for child in requirement.decomposed_requirements),
        depends_on_ids=tuple(dep.id for dep in requirement.depends_on),
        depth=depth,
    )


def _build_entries_recursive(  # noqa: PLR0913
    requirement: Requirement,
    scope_name: str,
    evaluation_results: dict[ProjectPath, Any] | None,
    computed_statuses: dict[str, RequirementStatus],
    depth: int,
    entries: list[RequirementTraceEntry],
    requirements: dict[str, tuple[str, Requirement]],
) -> None:
    """Recursively build trace entries in pre-order (parent before children).

    This function first processes children (to compute their statuses),
    then builds the parent entry, and adds entries in display order.

    Args:
        requirement: The requirement to process.
        scope_name: The scope name where the requirement is defined.
        evaluation_results: Optional evaluation results.
        computed_statuses: Dict to store computed statuses.
        depth: Current hierarchy depth.
        entries: List to append entries to.
        requirements: All requirements dict (for looking up scope names).

    """
    # First, recursively process all children to compute their statuses
    for child in requirement.decomposed_requirements:
        child_scope_name = requirements[child.id][0] if child.id in requirements else scope_name
        _build_entries_recursive(
            child,
            child_scope_name,
            evaluation_results,
            computed_statuses,
            depth + 1,
            [],  # Don't add to entries yet - we'll do it in order
            requirements,
        )

    # Process depends_on requirements (they should already be processed)
    for dep in requirement.depends_on:
        if dep.id not in computed_statuses:
            dep_scope_name = requirements[dep.id][0] if dep.id in requirements else scope_name
            _build_entries_recursive(
                dep,
                dep_scope_name,
                evaluation_results,
                computed_statuses,
                0,  # depth doesn't matter for status computation
                [],
                requirements,
            )

    # Now build this requirement's entry (children are already computed)
    entry = _build_entry(requirement, scope_name, evaluation_results, computed_statuses, depth)
    computed_statuses[requirement.id] = entry.status

    # Add this entry
    entries.append(entry)

    # Then add children's entries in order (for display)
    for child in requirement.decomposed_requirements:
        child_scope_name = requirements[child.id][0] if child.id in requirements else scope_name
        child_entry = _build_entry(child, child_scope_name, evaluation_results, computed_statuses, depth + 1)
        entries.append(child_entry)

        # Recursively add grandchildren
        for grandchild in child.decomposed_requirements:
            gc_scope = requirements[grandchild.id][0] if grandchild.id in requirements else scope_name
            _add_entries_in_order(
                grandchild, gc_scope, evaluation_results, computed_statuses, depth + 2, entries, requirements,
            )


def _add_entries_in_order(  # noqa: PLR0913
    requirement: Requirement,
    scope_name: str,
    evaluation_results: dict[ProjectPath, Any] | None,
    computed_statuses: dict[str, RequirementStatus],
    depth: int,
    entries: list[RequirementTraceEntry],
    requirements: dict[str, tuple[str, Requirement]],
) -> None:
    """Add entries in display order (pre-order traversal)."""
    entry = _build_entry(requirement, scope_name, evaluation_results, computed_statuses, depth)
    entries.append(entry)

    for child in requirement.decomposed_requirements:
        child_scope_name = requirements[child.id][0] if child.id in requirements else scope_name
        _add_entries_in_order(
            child, child_scope_name, evaluation_results, computed_statuses, depth + 1, entries, requirements,
        )


def build_traceability_report(
    project: Project,
    evaluation_results: EvaluationResult | None = None,
) -> TraceabilityReport:
    """Build a complete traceability report for a project.

    Args:
        project: The project to analyze.
        evaluation_results: Optional evaluation results from evaluate_project().
            If None, only structure is reported (no pass/fail status).

    Returns:
        TraceabilityReport with all entries and summary stats.

    Raises:
        ValueError: If circular dependencies are detected in depends_on.

    """
    # Extract values dict from EvaluationResult
    eval_values: dict[ProjectPath, Any] | None = (
        evaluation_results.values if evaluation_results is not None else None
    )
    # Collect all requirements
    requirements = collect_all_requirements(project)

    # Detect circular dependencies
    cycles = detect_circular_dependencies(requirements)
    if cycles:
        cycle_str = " -> ".join(cycles[0])
        msg = f"Circular dependency detected in requirements: {cycle_str}"
        raise ValueError(msg)

    # Get root requirements (for tree traversal)
    root_reqs = _get_root_requirements(requirements)

    # Build entries with status computation
    computed_statuses: dict[str, RequirementStatus] = {}
    entries: list[RequirementTraceEntry] = []

    # First pass: compute all statuses (bottom-up)
    for scope_name, req in root_reqs:
        _compute_statuses_recursive(req, scope_name, eval_values, computed_statuses, requirements)

    # Second pass: build entries in display order (top-down)
    for scope_name, req in root_reqs:
        _add_entries_in_order(req, scope_name, eval_values, computed_statuses, 0, entries, requirements)

    # Count statistics
    verified_count = sum(1 for e in entries if e.status == RequirementStatus.VERIFIED)
    satisfied_count = sum(1 for e in entries if e.status == RequirementStatus.SATISFIED)
    failed_count = sum(1 for e in entries if e.status == RequirementStatus.FAILED)
    not_verified_count = sum(1 for e in entries if e.status == RequirementStatus.NOT_VERIFIED)

    return TraceabilityReport(
        project_name=project.name,
        entries=tuple(entries),
        total_requirements=len(entries),
        verified_count=verified_count,
        satisfied_count=satisfied_count,
        failed_count=failed_count,
        not_verified_count=not_verified_count,
    )


def _compute_statuses_recursive(  # noqa: PLR0913
    requirement: Requirement,
    scope_name: str,
    evaluation_results: dict[ProjectPath, Any] | None,
    computed_statuses: dict[str, RequirementStatus],
    requirements: dict[str, tuple[str, Requirement]],
    in_progress: set[str] | None = None,
) -> RequirementStatus:
    """Recursively compute statuses bottom-up.

    Args:
        requirement: The requirement to compute status for.
        scope_name: The scope name.
        evaluation_results: Optional evaluation results.
        computed_statuses: Dict to store computed statuses.
        requirements: All requirements dict.
        in_progress: Set of requirement IDs currently being computed (for cycle detection).

    Returns:
        The computed status for this requirement.

    """
    # If already computed, return cached value
    if requirement.id in computed_statuses:
        return computed_statuses[requirement.id]

    # Initialize in_progress set for cycle detection
    if in_progress is None:
        in_progress = set()

    # Check for cycle (requirement is already being computed)
    if requirement.id in in_progress:
        # Cycle detected - treat as NOT_VERIFIED to break the cycle
        # Store it to avoid KeyError when looking it up later
        computed_statuses[requirement.id] = RequirementStatus.NOT_VERIFIED
        return RequirementStatus.NOT_VERIFIED

    in_progress.add(requirement.id)

    # First compute children's statuses
    for child in requirement.decomposed_requirements:
        if child.id not in computed_statuses:
            child_scope = requirements[child.id][0] if child.id in requirements else scope_name
            _compute_statuses_recursive(
                child, child_scope, evaluation_results, computed_statuses, requirements, in_progress,
            )

    # Compute depends_on statuses
    for dep in requirement.depends_on:
        if dep.id not in computed_statuses:
            dep_scope = requirements[dep.id][0] if dep.id in requirements else scope_name
            _compute_statuses_recursive(
                dep, dep_scope, evaluation_results, computed_statuses, requirements, in_progress,
            )

    # Extract verification results
    verification_results: list[VerificationResult] = []
    if evaluation_results is not None:
        for verif in requirement.verified_by:
            verification_results.extend(
                extract_verification_results(verif, verif.default_scope_name, evaluation_results),
            )

    # Get child and dependency statuses
    child_statuses = [computed_statuses[child.id] for child in requirement.decomposed_requirements]
    depends_on_statuses = [computed_statuses[dep.id] for dep in requirement.depends_on]

    # Compute status using max-severity propagation
    # When evaluation_results is None, verification_results will be empty,
    # so compute_requirement_status will correctly handle the case
    status = compute_requirement_status(
        verification_results=verification_results,
        child_statuses=child_statuses,
        depends_on_statuses=depends_on_statuses,
    )

    computed_statuses[requirement.id] = status
    in_progress.discard(requirement.id)
    return status
