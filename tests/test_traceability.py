"""Tests for requirement-verification traceability analysis."""

from typing import Annotated

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._eval_engine import EvaluationResult, build_scope_trees
from veriq._path import ItemPart, ProjectPath, VerificationPath
from veriq._traceability import (
    RequirementStatus,
    VerificationResult,
    build_traceability_report,
    collect_all_requirements,
    compute_requirement_status,
    detect_circular_dependencies,
    extract_verification_results,
)


class TestComputeRequirementStatus:
    """Tests for compute_requirement_status function."""

    def test_no_verifications_no_children_no_deps_returns_not_verified(self) -> None:
        """Leaf requirement with no verifications is a coverage gap."""
        status = compute_requirement_status(
            verification_results=[],
            child_statuses=[],
            depends_on_statuses=[],
        )
        assert status == RequirementStatus.NOT_VERIFIED

    def test_all_verifications_passed_returns_verified(self) -> None:
        """Requirement with all verifications passed is VERIFIED."""
        results = [
            VerificationResult(
                scope_name="Power",
                verification_name="verify_battery",
                passed=True,
                xfail=False,
            ),
            VerificationResult(
                scope_name="Power",
                verification_name="verify_power_budget",
                passed=True,
                xfail=False,
                table_key="nominal",
            ),
        ]
        status = compute_requirement_status(
            verification_results=results,
            child_statuses=[],
            depends_on_statuses=[],
        )
        assert status == RequirementStatus.VERIFIED

    def test_any_verification_failed_returns_failed(self) -> None:
        """Requirement with any failed verification is FAILED."""
        results = [
            VerificationResult(
                scope_name="Power",
                verification_name="verify_battery",
                passed=True,
                xfail=False,
            ),
            VerificationResult(
                scope_name="Power",
                verification_name="verify_power_budget",
                passed=False,
                xfail=False,
            ),
        ]
        status = compute_requirement_status(
            verification_results=results,
            child_statuses=[],
            depends_on_statuses=[],
        )
        assert status == RequirementStatus.FAILED

    def test_verification_xfail_ignored_for_status(self) -> None:
        """Verification xfail flag is ignored - failed means FAILED."""
        results = [
            VerificationResult(
                scope_name="Power",
                verification_name="verify_battery",
                passed=False,
                xfail=True,  # xfail should be ignored
            ),
        ]
        status = compute_requirement_status(
            verification_results=results,
            child_statuses=[],
            depends_on_statuses=[],
        )
        assert status == RequirementStatus.FAILED

    def test_all_children_passed_no_verifications_returns_satisfied(self) -> None:
        """Requirement with all children passed but no direct verifications is SATISFIED."""
        status = compute_requirement_status(
            verification_results=[],
            child_statuses=[RequirementStatus.VERIFIED, RequirementStatus.SATISFIED],
            depends_on_statuses=[],
        )
        assert status == RequirementStatus.SATISFIED

    def test_any_child_failed_returns_failed(self) -> None:
        """Requirement with any failed child is FAILED."""
        status = compute_requirement_status(
            verification_results=[],
            child_statuses=[RequirementStatus.VERIFIED, RequirementStatus.FAILED],
            depends_on_statuses=[],
        )
        assert status == RequirementStatus.FAILED

    def test_child_not_verified_propagates_to_parent(self) -> None:
        """NOT_VERIFIED child propagates to parent (max-severity logic)."""
        status = compute_requirement_status(
            verification_results=[],
            child_statuses=[RequirementStatus.VERIFIED, RequirementStatus.NOT_VERIFIED],
            depends_on_statuses=[],
        )
        assert status == RequirementStatus.NOT_VERIFIED

    def test_depends_on_failed_returns_failed(self) -> None:
        """Requirement with failed dependency is FAILED."""
        status = compute_requirement_status(
            verification_results=[],
            child_statuses=[],
            depends_on_statuses=[RequirementStatus.FAILED],
        )
        assert status == RequirementStatus.FAILED

    def test_depends_on_satisfied_no_verifications_returns_satisfied(self) -> None:
        """Requirement with satisfied dependencies but no verifications is SATISFIED."""
        status = compute_requirement_status(
            verification_results=[],
            child_statuses=[],
            depends_on_statuses=[RequirementStatus.VERIFIED, RequirementStatus.SATISFIED],
        )
        assert status == RequirementStatus.SATISFIED

    def test_depends_on_not_verified_propagates(self) -> None:
        """NOT_VERIFIED dependency propagates to requirement (max-severity logic)."""
        status = compute_requirement_status(
            verification_results=[],
            child_statuses=[],
            depends_on_statuses=[RequirementStatus.NOT_VERIFIED],
        )
        assert status == RequirementStatus.NOT_VERIFIED

    def test_both_children_and_deps_all_passed_returns_satisfied(self) -> None:
        """Requirement with both children and deps all passed is SATISFIED."""
        status = compute_requirement_status(
            verification_results=[],
            child_statuses=[RequirementStatus.VERIFIED],
            depends_on_statuses=[RequirementStatus.SATISFIED],
        )
        assert status == RequirementStatus.SATISFIED

    def test_verifications_and_children_all_passed_returns_verified(self) -> None:
        """Requirement with verifications takes precedence - returns VERIFIED."""
        results = [
            VerificationResult(
                scope_name="Power",
                verification_name="verify_battery",
                passed=True,
                xfail=False,
            ),
        ]
        status = compute_requirement_status(
            verification_results=results,
            child_statuses=[RequirementStatus.VERIFIED],
            depends_on_statuses=[RequirementStatus.SATISFIED],
        )
        assert status == RequirementStatus.VERIFIED

    def test_depends_on_failed_takes_precedence_over_verifications(self) -> None:
        """Failed dependency causes FAILED even if verifications pass."""
        results = [
            VerificationResult(
                scope_name="Power",
                verification_name="verify_battery",
                passed=True,
                xfail=False,
            ),
        ]
        status = compute_requirement_status(
            verification_results=results,
            child_statuses=[],
            depends_on_statuses=[RequirementStatus.FAILED],
        )
        assert status == RequirementStatus.FAILED

    def test_child_failed_takes_precedence_over_verifications(self) -> None:
        """Failed child causes FAILED even if verifications pass."""
        results = [
            VerificationResult(
                scope_name="Power",
                verification_name="verify_battery",
                passed=True,
                xfail=False,
            ),
        ]
        status = compute_requirement_status(
            verification_results=results,
            child_statuses=[RequirementStatus.FAILED],
            depends_on_statuses=[],
        )
        assert status == RequirementStatus.FAILED


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_basic_verification_result(self) -> None:
        """Test basic VerificationResult creation."""
        result = VerificationResult(
            scope_name="Power",
            verification_name="verify_battery",
            passed=True,
            xfail=False,
        )
        assert result.scope_name == "Power"
        assert result.verification_name == "verify_battery"
        assert result.passed is True
        assert result.xfail is False
        assert result.table_key is None

    def test_verification_result_with_table_key(self) -> None:
        """Test VerificationResult with table key."""
        result = VerificationResult(
            scope_name="Power",
            verification_name="verify_power_budget",
            passed=True,
            xfail=False,
            table_key="nominal",
        )
        assert result.table_key == "nominal"

    def test_verification_result_with_tuple_table_key(self) -> None:
        """Test VerificationResult with tuple table key (multi-dimensional)."""
        result = VerificationResult(
            scope_name="RWA",
            verification_name="verify_matrix",
            passed=True,
            xfail=False,
            table_key=("initial", "nominal"),
        )
        assert result.table_key == ("initial", "nominal")

    def test_verification_result_is_frozen(self) -> None:
        """Test that VerificationResult is immutable."""
        result = VerificationResult(
            scope_name="Power",
            verification_name="verify_battery",
            passed=True,
            xfail=False,
        )
        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore[misc]


class TestRequirementStatus:
    """Tests for RequirementStatus enum."""

    def test_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert RequirementStatus.VERIFIED
        assert RequirementStatus.SATISFIED
        assert RequirementStatus.FAILED
        assert RequirementStatus.NOT_VERIFIED

    def test_status_is_str_enum(self) -> None:
        """Test that status values are strings."""
        assert isinstance(RequirementStatus.VERIFIED, str)
        assert isinstance(RequirementStatus.FAILED, str)


class TestCollectAllRequirements:
    """Tests for collect_all_requirements function."""

    def test_collect_from_single_scope(self) -> None:
        """Test collecting requirements from a single scope."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        scope.requirement("REQ-001", "First requirement")
        scope.requirement("REQ-002", "Second requirement")

        result = collect_all_requirements(project)

        assert len(result) == 2
        assert "REQ-001" in result
        assert "REQ-002" in result
        assert result["REQ-001"][0] == "System"
        assert result["REQ-002"][0] == "System"

    def test_collect_from_multiple_scopes(self) -> None:
        """Test collecting requirements from multiple scopes."""
        project = vq.Project("Test")
        system = vq.Scope("System")
        power = vq.Scope("Power")
        project.add_scope(system)
        project.add_scope(power)

        system.requirement("REQ-SYS-001", "System requirement")
        power.requirement("REQ-PWR-001", "Power requirement")

        result = collect_all_requirements(project)

        assert len(result) == 2
        assert result["REQ-SYS-001"][0] == "System"
        assert result["REQ-PWR-001"][0] == "Power"

    def test_collect_nested_requirements(self) -> None:
        """Test collecting hierarchical requirements."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        with scope.requirement("REQ-001", "Parent requirement"):
            scope.requirement("REQ-001-1", "Child requirement 1")
            scope.requirement("REQ-001-2", "Child requirement 2")

        result = collect_all_requirements(project)

        assert len(result) == 3
        assert "REQ-001" in result
        assert "REQ-001-1" in result
        assert "REQ-001-2" in result

    def test_duplicate_id_raises_error(self) -> None:
        """Test that duplicate requirement IDs raise an error."""
        project = vq.Project("Test")
        system = vq.Scope("System")
        power = vq.Scope("Power")
        project.add_scope(system)
        project.add_scope(power)

        system.requirement("REQ-001", "System requirement")
        power.requirement("REQ-001", "Power requirement with same ID")

        with pytest.raises(ValueError, match="Duplicate requirement ID"):
            collect_all_requirements(project)

    def test_empty_project(self) -> None:
        """Test collecting from project with no requirements."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        result = collect_all_requirements(project)

        assert len(result) == 0


class TestExtractVerificationResults:
    """Tests for extract_verification_results function."""

    def test_extract_bool_verification_passed(self) -> None:
        """Test extracting result from a bool verification that passed."""
        scope = vq.Scope("Power")

        class PowerModel(BaseModel):
            capacity: float

        @scope.verification()
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.capacity")],
        ) -> bool:
            return capacity > 0

        # Simulate evaluation results
        ppath = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_capacity", parts=()),
        )
        evaluation_results = EvaluationResult(
            scopes=build_scope_trees({ppath: True}),
            errors=[],
            validity={ppath: True},
        )

        results = extract_verification_results(verify_capacity, "Power", evaluation_results)

        assert len(results) == 1
        assert results[0].scope_name == "Power"
        assert results[0].verification_name == "verify_capacity"
        assert results[0].passed is True
        assert results[0].table_key is None

    def test_extract_bool_verification_failed(self) -> None:
        """Test extracting result from a bool verification that failed."""
        scope = vq.Scope("Power")

        class PowerModel(BaseModel):
            capacity: float

        @scope.verification()
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.capacity")],
        ) -> bool:
            return capacity > 0

        ppath = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_capacity", parts=()),
        )
        evaluation_results = EvaluationResult(
            scopes=build_scope_trees({ppath: False}),
            errors=[],
            validity={ppath: True},
        )

        results = extract_verification_results(verify_capacity, "Power", evaluation_results)

        assert len(results) == 1
        assert results[0].passed is False

    def test_extract_table_verification(self) -> None:
        """Test extracting results from a Table[K, bool] verification.

        Only leaf results (with table keys) should be returned.
        The non-leaf aggregate result (without table key) should be excluded.
        """
        from enum import StrEnum, unique

        @unique
        class Mode(StrEnum):
            NOMINAL = "nominal"
            SAFE = "safe"

        scope = vq.Scope("Power")

        class PowerModel(BaseModel):
            power: vq.Table[Mode, float]

        @scope.verification()
        def verify_power(
            power: Annotated[vq.Table[Mode, float], vq.Ref("$.power")],
        ) -> vq.Table[Mode, bool]:
            return vq.Table({mode: power[mode] > 0 for mode in Mode})  # ty: ignore[invalid-return-type]

        # Simulate evaluation results including both:
        # - Non-leaf aggregate result (no parts) - should be excluded
        # - Leaf results (with ItemPart) - should be included
        ppath_root = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_power", parts=()),
        )
        ppath_nominal = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_power", parts=(ItemPart(key="nominal"),)),
        )
        ppath_safe = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_power", parts=(ItemPart(key="safe"),)),
        )
        values_dict = {
            # Non-leaf aggregate result - should NOT be included in output
            ppath_root: True,
            # Leaf results - should be included in output
            ppath_nominal: True,
            ppath_safe: False,
        }
        evaluation_results = EvaluationResult(
            scopes=build_scope_trees(values_dict),
            errors=[],
            validity={ppath_root: True, ppath_nominal: True, ppath_safe: True},
        )

        results = extract_verification_results(verify_power, "Power", evaluation_results)

        # Should only return leaf results (2), not the non-leaf aggregate (3 total in input)
        assert len(results) == 2
        # All results should have a table_key (no None values)
        assert all(r.table_key is not None for r in results)
        results_by_key = {r.table_key: r for r in results}
        assert results_by_key["nominal"].passed is True
        assert results_by_key["safe"].passed is False

    def test_extract_xfail_verification(self) -> None:
        """Test that xfail flag is preserved in results."""
        scope = vq.Scope("Power")

        class PowerModel(BaseModel):
            capacity: float

        @scope.verification(xfail=True)
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.capacity")],
        ) -> bool:
            return capacity > 0

        ppath = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_capacity", parts=()),
        )
        evaluation_results = EvaluationResult(
            scopes=build_scope_trees({ppath: False}),
            errors=[],
            validity={ppath: True},
        )

        results = extract_verification_results(verify_capacity, "Power", evaluation_results)

        assert len(results) == 1
        assert results[0].xfail is True

    def test_extract_missing_result_returns_empty(self) -> None:
        """Test that missing evaluation result returns empty list."""
        scope = vq.Scope("Power")

        class PowerModel(BaseModel):
            capacity: float

        @scope.verification()
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.capacity")],
        ) -> bool:
            return capacity > 0

        evaluation_results = EvaluationResult(
            scopes=build_scope_trees({}),
            errors=[],
            validity={},
        )

        results = extract_verification_results(verify_capacity, "Power", evaluation_results)

        assert len(results) == 0


class TestDetectCircularDependencies:
    """Tests for detect_circular_dependencies function."""

    def test_no_cycles(self) -> None:
        """Test detection when there are no cycles."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        req1 = scope.requirement("REQ-001", "First")
        req2 = scope.requirement("REQ-002", "Second")

        with scope.fetch_requirement("REQ-002"):
            vq.depends(req1)

        requirements = collect_all_requirements(project)
        cycles = detect_circular_dependencies(requirements)

        assert len(cycles) == 0

    def test_simple_cycle(self) -> None:
        """Test detection of a simple A -> B -> A cycle."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        req1 = scope.requirement("REQ-001", "First")
        req2 = scope.requirement("REQ-002", "Second")

        # Create cycle: REQ-001 depends on REQ-002, REQ-002 depends on REQ-001
        req1.depends_on.append(req2)
        req2.depends_on.append(req1)

        requirements = collect_all_requirements(project)
        cycles = detect_circular_dependencies(requirements)

        assert len(cycles) > 0
        # At least one cycle should contain both requirements
        all_cycle_ids = set()
        for cycle in cycles:
            all_cycle_ids.update(cycle)
        assert "REQ-001" in all_cycle_ids
        assert "REQ-002" in all_cycle_ids

    def test_self_cycle(self) -> None:
        """Test detection of a self-referencing cycle."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        req1 = scope.requirement("REQ-001", "First")
        req1.depends_on.append(req1)

        requirements = collect_all_requirements(project)
        cycles = detect_circular_dependencies(requirements)

        assert len(cycles) > 0
        assert "REQ-001" in cycles[0]

    def test_longer_cycle(self) -> None:
        """Test detection of a longer cycle A -> B -> C -> A."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        req1 = scope.requirement("REQ-001", "First")
        req2 = scope.requirement("REQ-002", "Second")
        req3 = scope.requirement("REQ-003", "Third")

        req1.depends_on.append(req2)
        req2.depends_on.append(req3)
        req3.depends_on.append(req1)

        requirements = collect_all_requirements(project)
        cycles = detect_circular_dependencies(requirements)

        assert len(cycles) > 0

    def test_no_requirements(self) -> None:
        """Test with empty requirements dict."""
        cycles = detect_circular_dependencies({})
        assert len(cycles) == 0


class TestBuildTraceabilityReport:
    """Tests for build_traceability_report function."""

    def test_empty_project(self) -> None:
        """Test report for project with no requirements."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        report = build_traceability_report(project)

        assert report.project_name == "Test"
        assert len(report.entries) == 0
        assert report.total_requirements == 0

    def test_single_requirement_no_verification(self) -> None:
        """Test report for single requirement without verification."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        scope.requirement("REQ-001", "Test requirement")

        report = build_traceability_report(project)

        assert len(report.entries) == 1
        assert report.entries[0].requirement_id == "REQ-001"
        assert report.entries[0].status == RequirementStatus.NOT_VERIFIED
        assert report.not_verified_count == 1

    def test_hierarchical_requirements(self) -> None:
        """Test report for hierarchical requirements."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        with scope.requirement("REQ-001", "Parent"):
            scope.requirement("REQ-001-1", "Child 1")
            scope.requirement("REQ-001-2", "Child 2")

        report = build_traceability_report(project)

        assert len(report.entries) == 3
        # Parent should be first (pre-order)
        assert report.entries[0].requirement_id == "REQ-001"
        assert report.entries[0].depth == 0
        # Children should follow
        assert report.entries[1].depth == 1
        assert report.entries[2].depth == 1

    def test_report_with_verification_results(self) -> None:
        """Test report with actual verification results."""
        project = vq.Project("Test")
        scope = vq.Scope("Power")
        project.add_scope(scope)

        class PowerModel(BaseModel):
            capacity: float

        @scope.root_model()
        class RootModel(BaseModel):
            power: PowerModel

        @scope.verification()
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.power.capacity")],
        ) -> bool:
            return capacity > 0

        scope.requirement("REQ-001", "Capacity must be positive", verified_by=[vq.Ref("?verify_capacity")])

        # Simulate evaluation results
        ppath = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_capacity", parts=()),
        )
        evaluation_results = EvaluationResult(scopes=build_scope_trees({ppath: True}),
            errors=[],
            validity={ppath: True},
        )

        report = build_traceability_report(project, evaluation_results)

        assert len(report.entries) == 1
        assert report.entries[0].status == RequirementStatus.VERIFIED
        assert len(report.entries[0].verification_results) == 1
        assert report.entries[0].verification_results[0].passed is True

    def test_report_with_failed_verification(self) -> None:
        """Test report with failed verification."""
        project = vq.Project("Test")
        scope = vq.Scope("Power")
        project.add_scope(scope)

        class PowerModel(BaseModel):
            capacity: float

        @scope.root_model()
        class RootModel(BaseModel):
            power: PowerModel

        @scope.verification()
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.power.capacity")],
        ) -> bool:
            return capacity > 0

        scope.requirement("REQ-001", "Capacity must be positive", verified_by=[vq.Ref("?verify_capacity")])

        ppath = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_capacity", parts=()),
        )
        evaluation_results = EvaluationResult(scopes=build_scope_trees({ppath: False}),
            errors=[],
            validity={ppath: True},
        )

        report = build_traceability_report(project, evaluation_results)

        assert report.entries[0].status == RequirementStatus.FAILED
        assert report.failed_count == 1

    def test_parent_fails_when_child_fails(self) -> None:
        """Test that parent requirement fails when child fails."""
        project = vq.Project("Test")
        scope = vq.Scope("Power")
        project.add_scope(scope)

        class PowerModel(BaseModel):
            capacity: float

        @scope.root_model()
        class RootModel(BaseModel):
            power: PowerModel

        @scope.verification()
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.power.capacity")],
        ) -> bool:
            return capacity > 0

        with scope.requirement("REQ-001", "Parent"):
            scope.requirement("REQ-001-1", "Child", verified_by=[vq.Ref("?verify_capacity")])

        ppath = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_capacity", parts=()),
        )
        evaluation_results = EvaluationResult(scopes=build_scope_trees({ppath: False}),
            errors=[],
            validity={ppath: True},
        )

        report = build_traceability_report(project, evaluation_results)

        # Find parent and child entries
        parent = next(e for e in report.entries if e.requirement_id == "REQ-001")
        child = next(e for e in report.entries if e.requirement_id == "REQ-001-1")

        assert child.status == RequirementStatus.FAILED
        assert parent.status == RequirementStatus.FAILED

    def test_circular_dependency_raises_error(self) -> None:
        """Test that circular dependencies raise an error."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        req1 = scope.requirement("REQ-001", "First")
        req2 = scope.requirement("REQ-002", "Second")

        req1.depends_on.append(req2)
        req2.depends_on.append(req1)

        with pytest.raises(ValueError, match="Circular dependency"):
            build_traceability_report(project)

    def test_xfail_requirement_preserved(self) -> None:
        """Test that xfail flag is preserved in report."""
        project = vq.Project("Test")
        scope = vq.Scope("System")
        project.add_scope(scope)

        scope.requirement("REQ-001", "Expected to fail", xfail=True)

        report = build_traceability_report(project)

        assert report.entries[0].xfail is True

    def test_depends_on_failure_propagates(self) -> None:
        """Test that failed dependency causes requirement to fail."""
        project = vq.Project("Test")
        scope = vq.Scope("Power")
        project.add_scope(scope)

        class PowerModel(BaseModel):
            capacity: float

        @scope.root_model()
        class RootModel(BaseModel):
            power: PowerModel

        @scope.verification()
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.power.capacity")],
        ) -> bool:
            return capacity > 0

        req1 = scope.requirement("REQ-001", "Base requirement", verified_by=[vq.Ref("?verify_capacity")])
        req2 = scope.requirement("REQ-002", "Dependent requirement")

        with scope.fetch_requirement("REQ-002"):
            vq.depends(req1)

        ppath = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_capacity", parts=()),
        )
        evaluation_results = EvaluationResult(scopes=build_scope_trees({ppath: False}),
            errors=[],
            validity={ppath: True},
        )

        report = build_traceability_report(project, evaluation_results)

        req1_entry = next(e for e in report.entries if e.requirement_id == "REQ-001")
        req2_entry = next(e for e in report.entries if e.requirement_id == "REQ-002")

        assert req1_entry.status == RequirementStatus.FAILED
        assert req2_entry.status == RequirementStatus.FAILED

    def test_report_with_evaluation_result_object(self) -> None:
        """Test report with EvaluationResult object (not just dict).

        This is a regression test for the case when build_traceability_report
        is called with the actual EvaluationResult from evaluate_project.
        """
        project = vq.Project("Test")
        scope = vq.Scope("Power")
        project.add_scope(scope)

        class PowerModel(BaseModel):
            capacity: float

        @scope.root_model()
        class RootModel(BaseModel):
            power: PowerModel

        @scope.verification()
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.power.capacity")],
        ) -> bool:
            return capacity > 0

        scope.requirement("REQ-001", "Capacity must be positive", verified_by=[vq.Ref("?verify_capacity")])

        # Use EvaluationResult object instead of plain dict
        ppath = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_capacity", parts=()),
        )
        evaluation_results = EvaluationResult(scopes=build_scope_trees({ppath: True}),
            errors=[],
            validity={ppath: True},
        )

        report = build_traceability_report(project, evaluation_results)

        assert len(report.entries) == 1
        assert report.entries[0].status == RequirementStatus.VERIFIED
        assert len(report.entries[0].verification_results) == 1
        assert report.entries[0].verification_results[0].passed is True


class TestVerifiedByRef:
    """Tests for verified_by with Ref objects."""

    def test_verified_by_ref_same_scope(self) -> None:
        """Ref without scope uses requirement's scope."""
        project = vq.Project("Test")
        scope = vq.Scope("Power")
        project.add_scope(scope)

        class PowerModel(BaseModel):
            capacity: float

        @scope.root_model()
        class RootModel(BaseModel):
            power: PowerModel

        @scope.verification()
        def verify_capacity(
            capacity: Annotated[float, vq.Ref("$.power.capacity")],
        ) -> bool:
            return capacity > 0

        # Use Ref instead of direct Verification
        scope.requirement(
            "REQ-001",
            "Capacity must be positive",
            verified_by=[vq.Ref("?verify_capacity")],
        )

        ppath = ProjectPath(
            scope="Power",
            path=VerificationPath(root="?verify_capacity", parts=()),
        )
        evaluation_results = EvaluationResult(scopes=build_scope_trees({ppath: True}),
            errors=[],
            validity={ppath: True},
        )

        report = build_traceability_report(project, evaluation_results)

        assert len(report.entries) == 1
        entry = report.entries[0]
        assert "Power::?verify_capacity" in entry.linked_verifications
        assert entry.status == RequirementStatus.VERIFIED

    def test_verified_by_ref_cross_scope(self) -> None:
        """Ref with scope references verification in another scope."""
        project = vq.Project("Test")
        power = vq.Scope("Power")
        thermal = vq.Scope("Thermal")
        project.add_scope(power)
        project.add_scope(thermal)

        @power.root_model()
        class PowerModel(BaseModel):
            pass

        class ThermalData(BaseModel):
            temperature: float

        @thermal.root_model()
        class ThermalModel(BaseModel):
            data: ThermalData

        @thermal.verification()
        def verify_temp(
            temperature: Annotated[float, vq.Ref("$.data.temperature")],
        ) -> bool:
            return temperature < 100

        # Requirement in power scope references verification in thermal scope
        power.requirement(
            "REQ-PWR-001",
            "Temperature must be safe.",
            verified_by=[vq.Ref("?verify_temp", scope="Thermal")],
        )

        ppath = ProjectPath(
            scope="Thermal",
            path=VerificationPath(root="?verify_temp", parts=()),
        )
        evaluation_results = EvaluationResult(scopes=build_scope_trees({ppath: True}),
            errors=[],
            validity={ppath: True},
        )

        report = build_traceability_report(project, evaluation_results)

        assert len(report.entries) == 1
        entry = report.entries[0]
        assert "Thermal::?verify_temp" in entry.linked_verifications
        assert entry.status == RequirementStatus.VERIFIED

    def test_verified_by_ref_invalid_path_raises(self) -> None:
        """Ref with non-verification path raises ValueError."""
        project = vq.Project("Test")
        scope = vq.Scope("Power")
        project.add_scope(scope)

        @scope.root_model()
        class Model(BaseModel):
            pass

        with pytest.raises(ValueError, match="must point to a verification"):
            scope.requirement(
                "REQ-001",
                "Test",
                verified_by=[vq.Ref("$.field")],  # Model path, not verification
            )

    def test_verified_by_ref_nonexistent_verification_raises(self) -> None:
        """Ref to nonexistent verification raises ValueError at resolution time."""
        project = vq.Project("Test")
        scope = vq.Scope("Power")
        project.add_scope(scope)

        @scope.root_model()
        class Model(BaseModel):
            pass

        scope.requirement(
            "REQ-001",
            "Test",
            verified_by=[vq.Ref("?nonexistent_verification")],
        )

        # Error occurs at resolution time (when building traceability report)
        with pytest.raises(ValueError, match="Verification 'nonexistent_verification' not found"):
            build_traceability_report(project)

    def test_verified_by_ref_nonexistent_scope_raises(self) -> None:
        """Ref with nonexistent scope raises ValueError at resolution time."""
        project = vq.Project("Test")
        scope = vq.Scope("Power")
        project.add_scope(scope)

        @scope.root_model()
        class Model(BaseModel):
            pass

        scope.requirement(
            "REQ-001",
            "Test",
            verified_by=[vq.Ref("?some_verification", scope="NonexistentScope")],
        )

        # Error occurs at resolution time (when building traceability report)
        with pytest.raises(ValueError, match="Scope 'NonexistentScope' not found"):
            build_traceability_report(project)
