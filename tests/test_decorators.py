"""Tests for decorator functions in veriq._decorators."""

from typing import Annotated

from pydantic import BaseModel

import veriq as vq
from veriq._decorators import assume


class TestAssumeDecorator:
    def test_assume_attaches_verification_to_function(self):
        """Test that @assume attaches a verification to the function."""
        scope = vq.Scope("TestScope")

        @scope.root_model()
        class TestModel(BaseModel):
            value: float

        @scope.verification()
        def my_verification(val: Annotated[float, vq.Ref("$.value")]) -> bool:
            return val > 0

        @assume(my_verification)
        def some_function() -> float:
            return 42.0

        assert hasattr(some_function, "__veriq_assumed_verifications__")
        assert my_verification in some_function.__veriq_assumed_verifications__

    def test_assume_multiple_verifications(self):
        """Test that @assume can attach multiple verifications."""
        scope = vq.Scope("TestScope")

        @scope.root_model()
        class TestModel(BaseModel):
            value: float

        @scope.verification()
        def verif_positive(val: Annotated[float, vq.Ref("$.value")]) -> bool:
            return val > 0

        @scope.verification()
        def verif_small(val: Annotated[float, vq.Ref("$.value")]) -> bool:
            return val < 100

        @assume(verif_positive)
        @assume(verif_small)
        def some_function() -> float:
            return 42.0

        assert hasattr(some_function, "__veriq_assumed_verifications__")
        assert verif_positive in some_function.__veriq_assumed_verifications__
        assert verif_small in some_function.__veriq_assumed_verifications__

    def test_assume_with_calculation_decorator(self):
        """Test that @assume works with @calculation decorator."""
        scope = vq.Scope("TestScope")

        @scope.root_model()
        class TestModel(BaseModel):
            value: float

        @scope.verification()
        def input_positive(val: Annotated[float, vq.Ref("$.value")]) -> bool:
            return val > 0

        @scope.calculation()
        @assume(input_positive)
        def calculate_result(val: Annotated[float, vq.Ref("$.value")]) -> float:
            return val * 2

        # The calculation should have the assumed verification stored
        assert input_positive in calculate_result.assumed_verifications

    def test_assume_preserves_function_behavior(self):
        """Test that @assume doesn't change function behavior."""
        scope = vq.Scope("TestScope")

        @scope.root_model()
        class TestModel(BaseModel):
            value: float

        @scope.verification()
        def dummy_verif(val: Annotated[float, vq.Ref("$.value")]) -> bool:
            return True

        @assume(dummy_verif)
        def add_numbers(a: int, b: int) -> int:
            return a + b

        # Function should still work normally
        assert add_numbers(2, 3) == 5
        assert add_numbers(10, 20) == 30
