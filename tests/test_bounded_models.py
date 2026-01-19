"""Tests for bounded-models TableFieldHandler integration."""

from enum import StrEnum
from typing import Annotated

import pytest
from bounded_models import EnumFieldHandler, FieldHandlerRegistry, NumericFieldHandler
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

import veriq as vq
from veriq._bounded_models import TableFieldHandler


class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"
    AGGRESSIVE = "aggressive"


class Phase(StrEnum):
    INITIAL = "initial"
    CRUISE = "cruise"


@pytest.fixture
def registry() -> FieldHandlerRegistry:
    """Create a registry with TableFieldHandler and basic handlers."""
    return FieldHandlerRegistry(
        handlers=[
            (10, TableFieldHandler()),  # Higher priority to check Table first
            NumericFieldHandler(),
            EnumFieldHandler(),
        ],
    )


class TestTableFieldHandlerCanHandle:
    def test_can_handle_table(self) -> None:
        handler = TableFieldHandler()
        field_info = FieldInfo(annotation=vq.Table[Mode, float], default=...)
        assert handler.can_handle(field_info) is True

    def test_can_handle_table_with_tuple_key(self) -> None:
        handler = TableFieldHandler()
        field_info = FieldInfo(annotation=vq.Table[tuple[Phase, Mode], float], default=...)
        assert handler.can_handle(field_info) is True

    def test_cannot_handle_dict(self) -> None:
        handler = TableFieldHandler()
        field_info = FieldInfo(annotation=dict[str, float], default=...)
        assert handler.can_handle(field_info) is False

    def test_cannot_handle_float(self) -> None:
        handler = TableFieldHandler()
        field_info = FieldInfo(annotation=float, default=...)
        assert handler.can_handle(field_info) is False


class TestTableFieldHandlerBoundedness:
    def test_bounded_with_bounded_value(self, registry: FieldHandlerRegistry) -> None:
        """Table with bounded float value is bounded."""
        field_info = FieldInfo(
            annotation=vq.Table[Mode, Annotated[float, Field(ge=0.0, le=100.0)]],
            default=...,
        )
        handler = TableFieldHandler()
        assert handler.check_boundedness(field_info, registry) is True

    def test_unbounded_with_unbounded_value(self, registry: FieldHandlerRegistry) -> None:
        """Table with unbounded float value is not bounded."""
        field_info = FieldInfo(
            annotation=vq.Table[Mode, float],
            default=...,
        )
        handler = TableFieldHandler()
        assert handler.check_boundedness(field_info, registry) is False

    def test_bounded_with_enum_value(self, registry: FieldHandlerRegistry) -> None:
        """Table with enum value is bounded (enums are always bounded)."""
        field_info = FieldInfo(
            annotation=vq.Table[Mode, Phase],
            default=...,
        )
        handler = TableFieldHandler()
        assert handler.check_boundedness(field_info, registry) is True


class TestTableFieldHandlerDimensions:
    def test_dimensions_single_key(self, registry: FieldHandlerRegistry) -> None:
        """Table[Mode, float] should have 3 dimensions (one per Mode member)."""
        field_info = FieldInfo(
            annotation=vq.Table[Mode, Annotated[float, Field(ge=0.0, le=100.0)]],
            default=...,
        )
        handler = TableFieldHandler()
        assert handler.n_dimensions(field_info, registry) == 3

    def test_dimensions_tuple_key(self, registry: FieldHandlerRegistry) -> None:
        """Table[(Phase, Mode), float] should have 6 dimensions (2 * 3)."""
        field_info = FieldInfo(
            annotation=vq.Table[tuple[Phase, Mode], Annotated[float, Field(ge=0.0, le=100.0)]],
            default=...,
        )
        handler = TableFieldHandler()
        assert handler.n_dimensions(field_info, registry) == 6


class TestTableFieldHandlerSample:
    def test_sample_single_key(self, registry: FieldHandlerRegistry) -> None:
        """Sample a Table[Mode, float] from unit values."""
        field_info = FieldInfo(
            annotation=vq.Table[Mode, Annotated[float, Field(ge=0.0, le=100.0)]],
            default=...,
        )
        handler = TableFieldHandler()

        # Unit values: 0.0 -> 0.0, 0.5 -> 50.0, 1.0 -> 100.0
        unit_values = [0.0, 0.5, 1.0]
        result = handler.sample(unit_values, field_info, registry)

        assert isinstance(result, vq.Table)
        assert len(result) == 3
        assert result[Mode.NOMINAL] == pytest.approx(0.0)
        assert result[Mode.SAFE] == pytest.approx(50.0)
        assert result[Mode.AGGRESSIVE] == pytest.approx(100.0)

    def test_sample_tuple_key(self, registry: FieldHandlerRegistry) -> None:
        """Sample a Table[(Phase, Mode), float] from unit values."""
        field_info = FieldInfo(
            annotation=vq.Table[tuple[Phase, Mode], Annotated[float, Field(ge=0.0, le=100.0)]],
            default=...,
        )
        handler = TableFieldHandler()

        # 6 unit values for 6 key combinations
        unit_values = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        result = handler.sample(unit_values, field_info, registry)

        assert isinstance(result, vq.Table)
        assert len(result) == 6
        # Check some values (order is INITIAL-NOMINAL, INITIAL-SAFE, INITIAL-AGGRESSIVE, CRUISE-...)
        assert result[(Phase.INITIAL, Mode.NOMINAL)] == pytest.approx(0.0)
        assert result[(Phase.INITIAL, Mode.SAFE)] == pytest.approx(20.0)
        assert result[(Phase.CRUISE, Mode.AGGRESSIVE)] == pytest.approx(100.0)


class TestTableFieldHandlerIntegration:
    def test_model_with_table_field(self, registry: FieldHandlerRegistry) -> None:
        """Test using TableFieldHandler with a Pydantic model containing a Table field."""

        class PowerConfig(BaseModel):
            power_limits: vq.Table[Mode, Annotated[float, Field(ge=0.0, le=1000.0)]]

        # Check model boundedness
        assert registry.check_model_boundedness(PowerConfig) is True

        # Check dimensions
        assert registry.model_dimensions(PowerConfig) == 3

        # Sample a model instance
        unit_values = [0.1, 0.5, 0.9]
        instance = registry.sample_model(unit_values, PowerConfig)

        assert isinstance(instance, PowerConfig)
        assert isinstance(instance.power_limits, vq.Table)
        assert instance.power_limits[Mode.NOMINAL] == pytest.approx(100.0)
        assert instance.power_limits[Mode.SAFE] == pytest.approx(500.0)
        assert instance.power_limits[Mode.AGGRESSIVE] == pytest.approx(900.0)

    def test_model_with_unbounded_table_field(self, registry: FieldHandlerRegistry) -> None:
        """Test that a model with unbounded Table value is not bounded."""

        class UnboundedConfig(BaseModel):
            values: vq.Table[Mode, float]  # No bounds on float

        assert registry.check_model_boundedness(UnboundedConfig) is False
