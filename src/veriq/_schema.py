"""Compare JSON schema artifacts independently of file I/O and CLI presentation."""

from __future__ import annotations

import json
from typing import Any

from veriq._diff import DiffEntry, DiffKind


def diff_schemas(committed: dict[str, Any], generated: dict[str, Any]) -> list[DiffEntry]:
    """Return structured differences between parsed JSON schemas.

    Object key order and source formatting are ignored. Numeric and boolean
    distinctions are preserved, including inside arrays (unlike Python equality,
    which considers ``100 == 100.0`` and ``True == 1``). Arrays are reported as
    whole values, with their ordering preserved.

    An empty result means the artifact is up to date. Neither input is modified.
    """
    return _diff_objects(committed, generated, prefix=())


def _diff_objects(
    committed: dict[str, Any],
    generated: dict[str, Any],
    *,
    prefix: tuple[str, ...],
) -> list[DiffEntry]:
    entries: list[DiffEntry] = []
    for key in sorted(committed.keys() | generated.keys()):
        path = (*prefix, key)
        if key not in committed:
            entries.append(DiffEntry(path, DiffKind.ADDED, None, generated[key]))
        elif key not in generated:
            entries.append(DiffEntry(path, DiffKind.REMOVED, committed[key], None))
        else:
            left, right = committed[key], generated[key]
            if isinstance(left, dict) and isinstance(right, dict):
                entries.extend(_diff_objects(left, right, prefix=path))
            elif json.dumps(left, sort_keys=True) != json.dumps(right, sort_keys=True):
                entries.append(DiffEntry(path, DiffKind.CHANGED, left, right))
    return entries
