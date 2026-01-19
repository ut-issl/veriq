"""Tests for decorator functions in veriq._decorators."""

from typing import Annotated

from pydantic import BaseModel

import veriq as vq
from veriq._decorators import assume


class TestAssumeDecorator:
    def test_assume_attaches_ref_to_function(self):
        """Test that @assume attaches a Ref to the function."""
        ref = vq.Ref("?my_verification")

        @assume(ref)
        def some_function() -> float:
            return 42.0

        assert hasattr(some_function, "__veriq_assumed_refs__")
        assert ref in some_function.__veriq_assumed_refs__  # ty: ignore[unsupported-operator]

    def test_assume_multiple_refs(self):
        """Test that @assume can attach multiple refs."""
        ref1 = vq.Ref("?verif_positive")
        ref2 = vq.Ref("?verif_small")

        @assume(ref1)
        @assume(ref2)
        def some_function() -> float:
            return 42.0

        assert hasattr(some_function, "__veriq_assumed_refs__")
        assert ref1 in some_function.__veriq_assumed_refs__  # ty: ignore[unsupported-operator]
        assert ref2 in some_function.__veriq_assumed_refs__  # ty: ignore[unsupported-operator]

    def test_assume_with_calculation_decorator(self):
        """Test that @assume works with @calculation decorator."""
        scope = vq.Scope("TestScope")

        @scope.root_model()
        class TestModel(BaseModel):
            value: float

        @scope.verification()
        def input_positive(val: Annotated[float, vq.Ref("$.value")]) -> bool:
            return val > 0

        ref = vq.Ref("?input_positive")

        @scope.calculation()
        @assume(ref)
        def calculate_result(val: Annotated[float, vq.Ref("$.value")]) -> float:
            return val * 2

        # The calculation should have the assumed ref stored
        assert ref in calculate_result.assumed_refs

    def test_assume_preserves_function_behavior(self):
        """Test that @assume doesn't change function behavior."""
        ref = vq.Ref("?dummy_verif")

        @assume(ref)
        def add_numbers(a: int, b: int) -> int:
            return a + b

        # Function should still work normally
        assert add_numbers(2, 3) == 5
        assert add_numbers(10, 20) == 30

    def test_assume_requires_verification_ref(self):
        """Test that @assume raises error if ref doesn't start with ?."""
        import pytest

        with pytest.raises(ValueError, match="requires a verification reference"):
            @assume(vq.Ref("$.some_field"))
            def some_function() -> float:
                return 42.0

    def test_assume_with_cross_scope_ref(self):
        """Test that @assume works with cross-scope refs."""
        ref = vq.Ref("?verify_temperature", scope="Thermal")

        @assume(ref)
        def calculate_power() -> float:
            return 100.0

        assert hasattr(calculate_power, "__veriq_assumed_refs__")
        assert ref in calculate_power.__veriq_assumed_refs__  # ty: ignore[unsupported-operator]
        assert calculate_power.__veriq_assumed_refs__[0].scope == "Thermal"  # ty: ignore[not-subscriptable]
