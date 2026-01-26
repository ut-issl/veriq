from enum import IntEnum

import pytest

from veriq import with_range


@with_range(3)
class SimpleEnum(IntEnum):
    pass


@with_range(10, start=5)
class StartEnum(IntEnum):
    pass


@with_range(10, step=2)
class StepEnum(IntEnum):
    pass


@with_range(10, start=2, step=3)
class StartStepEnum(IntEnum):
    pass


@with_range(3, prefix="IDX_")
class PrefixEnum(IntEnum):
    pass


@with_range(3)
class MixedEnum(IntEnum):
    SPECIAL = 100
    ERROR = -1


def test_simple_range() -> None:
    members = list(SimpleEnum)
    assert len(members) == 3
    assert SimpleEnum._0 == 0  # ty: ignore[unresolved-attribute]
    assert SimpleEnum._1 == 1  # ty: ignore[unresolved-attribute]
    assert SimpleEnum._2 == 2  # ty: ignore[unresolved-attribute]


def test_range_with_start() -> None:
    members = list(StartEnum)
    assert len(members) == 5
    assert StartEnum._5 == 5  # ty: ignore[unresolved-attribute]
    assert StartEnum._9 == 9  # ty: ignore[unresolved-attribute]
    assert not hasattr(StartEnum, "_0")
    assert not hasattr(StartEnum, "_10")


def test_range_with_step() -> None:
    members = list(StepEnum)
    assert len(members) == 5
    assert StepEnum._0 == 0  # ty: ignore[unresolved-attribute]
    assert StepEnum._2 == 2  # ty: ignore[unresolved-attribute]
    assert StepEnum._4 == 4  # ty: ignore[unresolved-attribute]
    assert StepEnum._6 == 6  # ty: ignore[unresolved-attribute]
    assert StepEnum._8 == 8  # ty: ignore[unresolved-attribute]
    assert not hasattr(StepEnum, "_1")
    assert not hasattr(StepEnum, "_10")


def test_range_with_start_and_step() -> None:
    members = list(StartStepEnum)
    assert len(members) == 3
    assert StartStepEnum._2 == 2  # ty: ignore[unresolved-attribute]
    assert StartStepEnum._5 == 5  # ty: ignore[unresolved-attribute]
    assert StartStepEnum._8 == 8  # ty: ignore[unresolved-attribute]


def test_custom_prefix() -> None:
    members = list(PrefixEnum)
    assert len(members) == 3
    assert PrefixEnum.IDX_0 == 0  # ty: ignore[unresolved-attribute]
    assert PrefixEnum.IDX_1 == 1  # ty: ignore[unresolved-attribute]
    assert PrefixEnum.IDX_2 == 2  # ty: ignore[unresolved-attribute]
    assert not hasattr(PrefixEnum, "_0")


def test_mixed_with_explicit_members() -> None:
    members = list(MixedEnum)
    assert len(members) == 5
    # Range members
    assert MixedEnum._0 == 0  # ty: ignore[unresolved-attribute]
    assert MixedEnum._1 == 1  # ty: ignore[unresolved-attribute]
    assert MixedEnum._2 == 2  # ty: ignore[unresolved-attribute]
    # Explicit members
    assert MixedEnum.SPECIAL == 100
    assert MixedEnum.ERROR == -1


def test_enum_is_int() -> None:
    assert isinstance(SimpleEnum._0, int)  # ty: ignore[unresolved-attribute]
    assert SimpleEnum._0 + 1 == 1  # ty: ignore[unresolved-attribute]
    assert SimpleEnum._2 * 2 == 4  # ty: ignore[unresolved-attribute]


def test_enum_by_value() -> None:
    assert SimpleEnum(0) is SimpleEnum._0  # ty: ignore[unresolved-attribute]
    assert SimpleEnum(2) is SimpleEnum._2  # ty: ignore[unresolved-attribute]


def test_enum_by_name() -> None:
    assert SimpleEnum["_0"] is SimpleEnum._0  # ty: ignore[unresolved-attribute]
    assert SimpleEnum["_2"] is SimpleEnum._2  # ty: ignore[unresolved-attribute]


def test_enum_iteration_order() -> None:
    # IntEnum iterates in definition order, which should be value order for range
    values = [m.value for m in SimpleEnum]
    assert values == [0, 1, 2]


def test_enum_membership() -> None:
    assert SimpleEnum._0 in SimpleEnum  # ty: ignore[unresolved-attribute]
    assert 0 in [m.value for m in SimpleEnum]


@pytest.mark.parametrize(
    ("member", "expected_value"),
    [
        (SimpleEnum._0, 0),  # ty: ignore[unresolved-attribute]
        (SimpleEnum._1, 1),  # ty: ignore[unresolved-attribute]
        (SimpleEnum._2, 2),  # ty: ignore[unresolved-attribute]
    ],
)
def test_simple_enum_parametrized(member: SimpleEnum, expected_value: int) -> None:
    assert member.value == expected_value


@pytest.mark.parametrize(
    ("stop", "start", "step", "expected_count"),
    [
        (5, 0, 1, 5),
        (10, 5, 1, 5),
        (10, 0, 2, 5),
        (10, 1, 3, 3),
        (0, 0, 1, 0),
        (1, 0, 1, 1),
    ],
)
def test_range_parameters(stop: int, start: int, step: int, expected_count: int) -> None:
    @with_range(stop, start=start, step=step)
    class DynamicEnum(IntEnum):
        pass

    assert len(list(DynamicEnum)) == expected_count


def test_empty_range() -> None:
    @with_range(0)
    class EmptyEnum(IntEnum):
        pass

    assert len(list(EmptyEnum)) == 0


def test_single_member() -> None:
    @with_range(1)
    class SingleEnum(IntEnum):
        pass

    assert len(list(SingleEnum)) == 1
    assert SingleEnum._0 == 0  # ty: ignore[unresolved-attribute]


def test_class_name_preserved() -> None:
    @with_range(3)
    class MyCustomName(IntEnum):
        pass

    assert MyCustomName.__name__ == "MyCustomName"
