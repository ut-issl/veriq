"""Implement `default` function to get the default value of a given type.

The default value of a type `T` will be determined as follows:
1. If `T` has a class method `T.default()`, it will be called.
2. If `T` is one of the following types, the predefined default values will be used.
    - int
    - float
    - str
"""

from collections.abc import Callable
from enum import Enum
from typing import Any, Final

from pydantic import BaseModel


def _default_enum[E: Enum](type_: type[E]) -> E:
    try:
        return next(iter(type_))
    except StopIteration:
        msg = f"Enum {type_} has no members to provide a default value."
        raise ValueError(msg) from None


def _default_pydantic_basemodel[M: BaseModel](type_: type[M]) -> M:
    default_values = {name: default(field_info.annotation) for name, field_info in type_.model_fields.items()}
    return type_(**default_values)


DEFAULT_IMPL: Final[dict[type, Callable[[Any], object]]] = {
    # `Enum` should come before `str` because `StrEnum` is subclass of `str`, but should be treated as `Enum`.
    Enum: _default_enum,
    int: lambda _: 0,
    float: lambda _: 0.0,
    str: lambda _: "",
    BaseModel: _default_pydantic_basemodel,
}


def default[T](type_: type[T]) -> T:
    if hasattr(type_, "default"):
        try:
            return type_.default()  # ty: ignore[call-non-callable] # It will be handled by the try-except
        except TypeError as e:
            msg = f"Failed to call default method of type {type_}. Make sure it is a class method with no arguments."
            raise TypeError(msg) from e
    for super_cls, default_impl in DEFAULT_IMPL.items():
        if issubclass(type_, super_cls):
            return default_impl(type_)  # ty: ignore[invalid-return-type] # We ensure key-value consistency in `DEFAULT_IMPL`

    msg = f"No default value defined for type {type_}"
    raise ValueError(msg)
