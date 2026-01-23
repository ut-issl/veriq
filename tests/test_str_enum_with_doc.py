from enum import unique

import pytest

from veriq import StrEnumWithDoc


class Mode(StrEnumWithDoc):
    NOMINAL = "nominal", "Normal operating mode"
    SAFE = "safe", "Safe mode with minimal power"
    STANDBY = "standby"  # No docstring provided


def test_enum_value() -> None:
    assert Mode.NOMINAL.value == "nominal"
    assert Mode.SAFE.value == "safe"
    assert Mode.STANDBY.value == "standby"


def test_enum_docstring() -> None:
    assert Mode.NOMINAL.__doc__ == "Normal operating mode"
    assert Mode.SAFE.__doc__ == "Safe mode with minimal power"


def test_enum_without_docstring_has_empty_doc() -> None:
    assert Mode.STANDBY.__doc__ == ""


def test_enum_is_str() -> None:
    assert isinstance(Mode.NOMINAL, str)
    assert Mode.NOMINAL == "nominal"
    assert f"{Mode.SAFE}" == "safe"


def test_enum_membership() -> None:
    assert Mode.NOMINAL in Mode
    assert "nominal" in Mode  # StrEnum supports string value membership check


def test_enum_iteration() -> None:
    members = list(Mode)
    assert len(members) == 3
    assert Mode.NOMINAL in members
    assert Mode.SAFE in members
    assert Mode.STANDBY in members


def test_enum_by_value() -> None:
    assert Mode("nominal") is Mode.NOMINAL
    assert Mode("safe") is Mode.SAFE


def test_enum_by_name() -> None:
    assert Mode["NOMINAL"] is Mode.NOMINAL
    assert Mode["SAFE"] is Mode.SAFE


@pytest.mark.parametrize(
    ("member", "expected_value", "expected_doc"),
    [
        (Mode.NOMINAL, "nominal", "Normal operating mode"),
        (Mode.SAFE, "safe", "Safe mode with minimal power"),
        (Mode.STANDBY, "standby", ""),
    ],
)
def test_enum_members_parametrized(
    member: Mode,
    expected_value: str,
    expected_doc: str,
) -> None:
    assert member.value == expected_value
    assert member.__doc__ == expected_doc


def test_unique_decorator_rejects_duplicate_values_with_different_docs() -> None:
    """Ensure @unique considers only values, not docstrings."""
    with pytest.raises(ValueError, match="duplicate values"):

        @unique
        class DuplicateMode(StrEnumWithDoc):
            NORMAL = "same_value", "First docstring"
            DUPLICATE = "same_value", "Different docstring"
