"""Tests for relation functions in veriq._relations."""

import pytest
from scoped_context import NoContextError

import veriq as vq
from veriq._relations import depends


class TestDepends:
    def test_depends_adds_requirement_to_parent(self):
        """Test that depends() adds a requirement to the parent's depends_on list."""
        scope = vq.Scope("TestScope")

        req_parent = scope.requirement("REQ-PARENT", description="Parent requirement")
        req_child = scope.requirement("REQ-CHILD", description="Child requirement")

        with req_parent:
            depends(req_child)

        assert req_child in req_parent.depends_on

    def test_depends_multiple_requirements(self):
        """Test that depends() can add multiple requirements."""
        scope = vq.Scope("TestScope")

        req_parent = scope.requirement("REQ-PARENT", description="Parent")
        req_dep1 = scope.requirement("REQ-DEP1", description="Dependency 1")
        req_dep2 = scope.requirement("REQ-DEP2", description="Dependency 2")
        req_dep3 = scope.requirement("REQ-DEP3", description="Dependency 3")

        with req_parent:
            depends(req_dep1)
            depends(req_dep2)
            depends(req_dep3)

        assert req_dep1 in req_parent.depends_on
        assert req_dep2 in req_parent.depends_on
        assert req_dep3 in req_parent.depends_on
        assert len(req_parent.depends_on) == 3

    def test_depends_outside_context_raises(self):
        """Test that depends() raises error when called outside requirement context."""
        scope = vq.Scope("TestScope")
        req = scope.requirement("REQ-1", description="Some requirement")

        with pytest.raises(NoContextError):
            depends(req)

    def test_depends_nested_requirements(self):
        """Test depends() works with nested requirement contexts."""
        scope = vq.Scope("TestScope")

        req_outer = scope.requirement("REQ-OUTER", description="Outer")
        req_inner = scope.requirement("REQ-INNER", description="Inner")
        req_dep = scope.requirement("REQ-DEP", description="Dependency")

        with req_outer, req_inner:
            # This should add to req_inner (the current context)
            depends(req_dep)

        # req_dep should be in req_inner's depends_on, not req_outer's
        assert req_dep in req_inner.depends_on
        assert req_dep not in req_outer.depends_on

    def test_depends_cross_scope(self):
        """Test that depends() works with requirements from different scopes."""
        scope_a = vq.Scope("ScopeA")
        scope_b = vq.Scope("ScopeB")

        req_a = scope_a.requirement("REQ-A", description="From scope A")
        req_b = scope_b.requirement("REQ-B", description="From scope B")

        with req_a:
            depends(req_b)

        assert req_b in req_a.depends_on
