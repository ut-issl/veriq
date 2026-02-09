"""Field handler for bounded-models integration.

This module provides a TableFieldHandler for use with the bounded-models library,
enabling boundedness checking and uniform sampling of vq.Table fields.
"""

from __future__ import annotations

from itertools import islice, product
from typing import TYPE_CHECKING, Annotated, Any, get_args, get_origin

import annotated_types
from bounded_models import FieldHandler
from pydantic.fields import FieldInfo

from ._table import Table

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from enum import StrEnum

    from bounded_models import FieldHandlerRegistry

# Mapping from annotated_types constraint classes to FieldInfo keyword argument names
_CONSTRAINT_TO_KWARG: dict[type, str] = {
    annotated_types.Ge: "ge",
    annotated_types.Gt: "gt",
    annotated_types.Le: "le",
    annotated_types.Lt: "lt",
    annotated_types.MultipleOf: "multiple_of",
    annotated_types.MinLen: "min_length",
    annotated_types.MaxLen: "max_length",
}


def _create_field_info_for_value_type(value_type_arg: type) -> FieldInfo:
    """Create a FieldInfo for the value type, handling Annotated types properly.

    When value_type_arg is Annotated[T, metadata...], we need to:
    1. Extract the base type T
    2. Extract the metadata (including Pydantic Field constraints)
    3. Create a FieldInfo with annotation=T and constraints as keyword arguments

    Note: FieldInfo's metadata parameter is ignored by Pydantic. Constraints must be
    passed as keyword arguments (e.g., ge=0.0, le=100.0) to be properly stored.
    """
    origin = get_origin(value_type_arg)
    if origin is Annotated:
        # Annotated[T, *metadata] - extract base type and metadata
        args = get_args(value_type_arg)
        base_type = args[0]
        metadata = args[1:]

        # Collect all constraint metadata items
        all_metadata: list[Any] = []
        for m in metadata:
            if isinstance(m, FieldInfo):
                all_metadata.extend(m.metadata)
            else:
                all_metadata.append(m)

        # Convert constraint objects to keyword arguments
        kwargs: dict[str, Any] = {"annotation": base_type, "default": ...}
        for item in all_metadata:
            for constraint_type, kwarg_name in _CONSTRAINT_TO_KWARG.items():
                if isinstance(item, constraint_type):
                    # Get the value from the constraint object using its attribute name
                    kwargs[kwarg_name] = getattr(item, kwarg_name)
                    break

        return FieldInfo(**kwargs)
    # Not Annotated, just use as-is
    return FieldInfo(annotation=value_type_arg, default=...)


class TableFieldHandler(FieldHandler[Table[Any, Any]]):
    """Handler for vq.Table[K, V] fields in bounded-models.

    Table keys are always bounded (they must be StrEnum or tuple of StrEnum).
    The handler checks if the value type V is bounded using the registry.

    Dimensions: n_keys * value_dimensions, where n_keys is the cartesian product
    of all enum members for the key type(s).

    Example:
        Table[Mode, float] with Mode having 3 members -> 3 dimensions
        Table[(Phase, Mode), float] with Phase(2) and Mode(3) -> 6 dimensions

    """

    def can_handle(self, field_info: FieldInfo) -> bool:
        """Check if the field is a Table[K, V] type."""
        origin = get_origin(field_info.annotation)
        return origin is Table

    def check_boundedness(self, field_info: FieldInfo, registry: FieldHandlerRegistry) -> bool:
        """Check if the Table field is properly bounded.

        Table keys are always bounded (StrEnum constraint).
        Returns True if the value type V is also bounded.
        """
        type_args = get_args(field_info.annotation)
        if len(type_args) != 2:
            return False

        _key_type_arg, value_type_arg = type_args

        # Keys are always bounded (enforced by Table's type constraint: StrEnum or tuple[StrEnum, ...])
        # Check if value type is bounded
        value_field = _create_field_info_for_value_type(value_type_arg)
        return registry.check_field_boundedness(value_field)

    def n_dimensions(self, field_info: FieldInfo, registry: FieldHandlerRegistry) -> int:
        """Return the number of dimensions for Table fields.

        This is n_keys * value_dimensions, where n_keys is the number of
        expected keys (cartesian product of enum members).
        """
        type_args = get_args(field_info.annotation)
        if len(type_args) != 2:
            msg = f"Table requires exactly 2 type arguments, got {len(type_args)}"
            raise TypeError(msg)

        key_type_arg, value_type_arg = type_args

        # Determine enum types from key type
        key_type_args = get_args(key_type_arg)
        enum_types: tuple[type[StrEnum], ...] = key_type_args or (key_type_arg,)

        # Count expected keys (cartesian product of enum members)
        num_keys = 1
        for enum_type in enum_types:
            num_keys *= len(list(enum_type))

        # Get dimensions per value
        value_field = _create_field_info_for_value_type(value_type_arg)
        value_dims = registry.field_dimensions(value_field)

        return num_keys * value_dims

    def sample(
        self,
        unit_values: Iterable[float],
        field_info: FieldInfo,
        registry: FieldHandlerRegistry,
    ) -> Table[Any, Any]:
        """Sample a complete Table instance from unit values.

        Generates all expected keys (cartesian product of enum members),
        then samples a value for each key using the appropriate number
        of unit values.
        """
        type_args = get_args(field_info.annotation)
        if len(type_args) != 2:
            msg = f"Table requires exactly 2 type arguments, got {len(type_args)}"
            raise TypeError(msg)

        key_type_arg, value_type_arg = type_args

        # Determine enum types from key type
        key_type_args = get_args(key_type_arg)
        enum_types: tuple[type[StrEnum], ...] = key_type_args or (key_type_arg,)

        # Generate all expected keys
        if len(enum_types) == 1:
            expected_keys: list[Any] = list(enum_types[0])
        else:
            expected_keys = [tuple(combo) for combo in product(*(list(et) for et in enum_types))]

        # Get value field info and dimensions
        value_field = _create_field_info_for_value_type(value_type_arg)
        value_dims = registry.field_dimensions(value_field)

        # Sample values for each key
        unit_values_iter: Iterator[float] = iter(unit_values)
        sampled_data: dict[Any, Any] = {}

        for key in expected_keys:
            value_unit_values = list(islice(unit_values_iter, value_dims))
            sampled_data[key] = registry.sample_field(value_unit_values, value_field)

        return Table(sampled_data)


# Type alias for protocol compatibility with bounded_models.FieldHandler
# This allows TableFieldHandler to be used with FieldHandlerRegistry
# without requiring bounded_models as a hard dependency
__all__ = ["TableFieldHandler"]
