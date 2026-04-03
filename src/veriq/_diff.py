"""Compare two nested dictionaries and report differences."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class DiffKind(Enum):
    """Kind of difference between two values."""

    ADDED = auto()
    REMOVED = auto()
    CHANGED = auto()


@dataclass(slots=True, frozen=True)
class DiffEntry:
    """A single difference between two nested dictionaries.

    Attributes:
        path: Sequence of keys leading to the differing value (e.g. ("Power", "voltage")).
        kind: Whether the key was added, removed, or changed.
        left: Value in the first dict (None for ADDED).
        right: Value in the second dict (None for REMOVED).

    """

    path: tuple[str, ...]
    kind: DiffKind
    left: Any
    right: Any


def format_toml_path(path: tuple[str, ...]) -> str:
    """Format a path tuple as a TOML dotted key.

    Bare keys (matching ``[A-Za-z0-9_-]+``) are left unquoted.
    All other keys are double-quoted with internal backslashes and
    double-quotes escaped, following the TOML spec.
    """
    return ".".join(_quote_toml_key(k) for k in path)


def _quote_toml_key(key: str) -> str:
    if _BARE_KEY_RE.match(key):
        return key
    # Escape backslashes first, then double-quotes, for TOML basic strings.
    escaped = key.replace("\\", r"\\").replace('"', r"\"")
    return f'"{escaped}"'


def diff_dicts(left: dict[str, Any], right: dict[str, Any]) -> list[DiffEntry]:
    """Compare two nested dictionaries and return a list of differences.

    Keys present only in *left* are reported as REMOVED.
    Keys present only in *right* are reported as ADDED.
    Keys present in both with different values are reported as CHANGED;
    if both values are dicts, the comparison recurses.

    Returns an empty list when the dicts are equal.
    """
    entries: list[DiffEntry] = []
    _diff_recursive(left, right, prefix=(), out=entries)
    return entries


def _diff_recursive(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    prefix: tuple[str, ...],
    out: list[DiffEntry],
) -> None:
    all_keys = sorted(set(left) | set(right))
    for key in all_keys:
        path = (*prefix, key)
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
