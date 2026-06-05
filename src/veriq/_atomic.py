"""Atomic file writes.

Write to a temporary file in the *same directory* as the target, then rename it
into place with ``Path.replace`` (an atomic operation within one filesystem).
A reader therefore always sees either the complete old file or the complete new
file, never a half-written one; a crash mid-write leaves the existing file
untouched and only discards the temp file.
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically write ``data`` to ``path`` (creating parent dirs as needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp = Path(handle.name)
            handle.write(data)
        tmp.replace(path)
        tmp = None  # renamed into place; nothing left to clean up
    finally:
        if tmp is not None:
            with contextlib.suppress(OSError):
                tmp.unlink()


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Atomically write ``text`` to ``path``."""
    atomic_write_bytes(path, text.encode(encoding))
