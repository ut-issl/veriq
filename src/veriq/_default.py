"""Implement `default` function to get the default value of a given type.

The default value of a type `T` will be determined as follows:
1. If `T` has a class method `T.default()`, it will be called.
2. If `T` is one of the following types, the predefined default values will be used.
    - int
    - float
    - str
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Final, get_args, get_origin

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Callable


def _default_enum[E: Enum](type_: type[E]) -> E:
    try:
        return next(iter(type_))
    except StopIteration:
        msg = f"Enum {type_} has no members to provide a default value."
        raise ValueError(msg) from None


def _default_pydantic_basemodel[M: BaseModel](type_: type[M]) -> M:
    default_values = {
        name: default(field_info.annotation)
        for name, field_info in type_.model_fields.items()
    }
    return type_(**default_values)


def _default_tuple(type_: Any) -> tuple[Any, ...]:
    """Create default tuple based on type annotation.

    Handles:
    - tuple[int] → (0,)
    - tuple[int, str] → (0, "")
    - tuple → ()
    - tuple[int, ...] → ()
    """
    args = get_args(type_)

    # Empty tuple: tuple or tuple[int, ...]
    if not args or (len(args) == 2 and args[1] is Ellipsis):
        return ()

    # Fixed-length tuple: tuple[int], tuple[int, str], etc.
    return tuple(default(arg) for arg in args)


DEFAULT_IMPL: Final[dict[type, Callable[[Any], object]]] = {
    # `Enum` should come before `str` because `StrEnum` is subclass of `str`, but should be treated as `Enum`.
    Enum: _default_enum,
    int: lambda _: 0,
    float: lambda _: 0.0,
    str: lambda _: "",
    BaseModel: _default_pydantic_basemodel,
}


def default[T](type_: type[T]) -> T:
    # Handle tuple types (both generic like tuple[int] and plain tuple class)
    origin = get_origin(type_)
    if origin is tuple or type_ is tuple:
        return _default_tuple(type_)  # ty: ignore[invalid-return-type]

    # Handle types with custom default method
    if hasattr(type_, "default"):
        try:
            return type_.default()  # ty: ignore[call-non-callable] # It will be handled by the try-except
        except TypeError as e:
            msg = f"Failed to call default method of type {type_}. Make sure it is a class method with no arguments."
            raise TypeError(msg) from e

    # Handle predefined types via issubclass check
    for super_cls, default_impl in DEFAULT_IMPL.items():
        try:
            if issubclass(type_, super_cls):
                return default_impl(type_)  # ty: ignore[invalid-return-type] # We ensure key-value consistency in `DEFAULT_IMPL`
        except TypeError:
            # issubclass() raises TypeError for non-class types
            continue

    msg = f"No default value defined for type {type_}"
    raise ValueError(msg)
