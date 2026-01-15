from enum import Enum, StrEnum
from typing import Annotated

import pytest
from pydantic import BaseModel, Field

from veriq._default import default


@pytest.mark.parametrize(
    ("type_", "expected"),
    [
        (int, 0),
        (float, 0.0),
        (str, ""),
    ],
)
def test_builtins[T](type_: type[T], expected: T) -> None:
    default_val = default(type_)
    assert default_val == expected


def test_enum() -> None:
    class E(Enum):
        A = 100  # This is the default, as it's the first member
        B = 1
        C = 0
        D = 101

    default_e = default(E)
    assert default_e is E.A


def test_strenum() -> None:
    class E(StrEnum):
        A = "z"
        B = "b"
        C = "a"

    default_e = default(E)
    assert default_e is E.A


def test_pydantic() -> None:
    class Inner(BaseModel):
        x: Annotated[int, Field(description="x")]
        y: int

    class M(BaseModel):
        a: int
        b: float
        c: str
        inner: Inner

    default_m = default(M)

    assert default_m == M(
        a=0,
        b=0.0,
        c="",
        inner=Inner(
            x=0,
            y=0,
        ),
    )


@pytest.mark.parametrize(
    ("type_", "expected"),
    [
        (tuple[int], (0,)),
        (tuple[str], ("",)),
        (tuple[int, int], (0, 0)),
        (tuple[int, str], (0, "")),
        (tuple, ()),
        (tuple[int, ...], ()),
        (tuple[str, ...], ()),
    ],
)
def test_tuple[T](type_: type[T], expected: T) -> None:
    default_val = default(type_)
    assert default_val == expected
