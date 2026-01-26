"""Module providing a decorator to create IntEnum with range-based members."""

from enum import IntEnum
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

_IntEnumT = TypeVar("_IntEnumT", bound=IntEnum)


def with_range(
    stop: int,
    /,
    start: int = 0,
    step: int = 1,
    prefix: str = "_",
) -> Callable[[type[_IntEnumT]], type[_IntEnumT]]:
    """Decorator to generate range-based IntEnum members.

    Creates enum members with names "{prefix}{i}" for each i in range(start, stop, step).

    Args:
        stop: The end value (exclusive), like range().
        start: The start value (default 0).
        step: The step between values (default 1).
        prefix: Prefix for member names (default "_").

    Returns:
        A decorator that transforms an IntEnum class.

    Examples:
        >>> @with_range(3)
        ... class Status(IntEnum):
        ...     pass
        >>> list(Status)
        [<Status._0: 0>, <Status._1: 1>, <Status._2: 2>]

        >>> @with_range(10, start=5)
        ... class Levels(IntEnum):
        ...     pass
        >>> list(Levels)
        [<Levels._5: 5>, <Levels._6: 6>, ...]

        >>> @with_range(10, step=2, prefix="N_")
        ... class EvenNumbers(IntEnum):
        ...     pass
        >>> EvenNumbers.N_0
        <EvenNumbers.N_0: 0>

        >>> @with_range(3)
        ... class Mixed(IntEnum):
        ...     SPECIAL = 100
        >>> list(Mixed)
        [<Mixed._0: 0>, <Mixed._1: 1>, <Mixed._2: 2>, <Mixed.SPECIAL: 100>]

    """

    def decorator(cls: type[_IntEnumT]) -> type[_IntEnumT]:
        # Generate range-based members
        members = {f"{prefix}{i}": i for i in range(start, stop, step)}

        # Collect existing members defined in the class
        existing_members = {
            name: value
            for name, value in vars(cls).items()
            if not name.startswith("_") and isinstance(value, int)
        }
        members.update(existing_members)

        return IntEnum(cls.__name__, members)  # type: ignore[return-value]

    return decorator
