"""Compare two nested dictionaries and report differences."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class DiffKind(Enum):
    """Kind of difference between two values."""

    ADDED = auto()
    REMOVED = auto()
    CHANGED = auto()


@dataclass(slots=True, frozen=True)
class DiffEntry:
    """A single difference between two nested dictionaries.

    Attributes:
        path: Dot-separated path to the differing key (e.g. "Power.voltage").
        kind: Whether the key was added, removed, or changed.
        left: Value in the first dict (None for ADDED).
        right: Value in the second dict (None for REMOVED).

    """

    path: str
    kind: DiffKind
    left: Any
    right: Any


def diff_dicts(left: dict[str, Any], right: dict[str, Any]) -> list[DiffEntry]:
    """Compare two nested dictionaries and return a list of differences.

    Keys present only in *left* are reported as REMOVED.
    Keys present only in *right* are reported as ADDED.
    Keys present in both with different values are reported as CHANGED;
    if both values are dicts, the comparison recurses.

    Returns an empty list when the dicts are equal.
    """
    entries: list[DiffEntry] = []
    _diff_recursive(left, right, prefix="", out=entries)
    return entries


def _diff_recursive(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    prefix: str,
    out: list[DiffEntry],
) -> None:
    all_keys = sorted(set(left) | set(right))
    for key in all_keys:
        path = f"{prefix}.{key}" if prefix else key
        in_left = key in left
        in_right = key in right

        if in_left and not in_right:
            out.append(DiffEntry(path=path, kind=DiffKind.REMOVED, left=left[key], right=None))
        elif not in_left and in_right:
            out.append(DiffEntry(path=path, kind=DiffKind.ADDED, left=None, right=right[key]))
        elif left[key] != right[key]:
            lv, rv = left[key], right[key]
            if isinstance(lv, dict) and isinstance(rv, dict):
                _diff_recursive(lv, rv, prefix=path, out=out)
            else:
                out.append(DiffEntry(path=path, kind=DiffKind.CHANGED, left=lv, right=rv))
