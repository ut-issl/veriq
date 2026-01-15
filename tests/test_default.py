from enum import Enum, StrEnum
from typing import Annotated

import pytest
from pydantic import BaseModel, Field

import veriq as vq
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


def test_pydantic_with_tuple_field() -> None:
    class M(BaseModel):
        s: tuple[str]
        t: tuple[int, str]
        u: tuple
        v: tuple[int, ...]
        x: int

    default_m = default(M)
    assert default_m == M(
        s=("",),
        t=(0, ""),
        u=(),
        v=(),
        x=0,
    )


class Mode(StrEnum):
    MODE_A = "A"
    MODE_B = "B"


class Phase(StrEnum):
    PHASE_1 = "1"
    PHASE_2 = "2"


@pytest.mark.parametrize(
    ("type_", "expected"),
    [
        (vq.Table[Mode, int], vq.Table({Mode.MODE_A: 0, Mode.MODE_B: 0})),
        (vq.Table[tuple[Mode, Phase], int], vq.Table({(mode, phase): 0 for mode in Mode for phase in Phase})),
    ],
)
def test_table[T](type_: type[T], expected: T) -> None:
    default_val = default(type_)
    assert default_val == expected
