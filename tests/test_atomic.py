"""Tests for atomic file writes.

Atomic = all-or-nothing: a write either fully succeeds or leaves the target
untouched. A failure mid-write must never corrupt or truncate an existing file,
and must not leave a stray temp file behind.
"""

from pathlib import Path

import pytest

from veriq import _atomic


def test_creates_new_file(tmp_path: Path) -> None:
    target = tmp_path / "out.toml"
    _atomic.atomic_write_text(target, "hello = 1\n")
    assert target.read_text() == "hello = 1\n"


def test_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "out.toml"
    target.write_text("old = 0\n")
    _atomic.atomic_write_text(target, "new = 1\n")
    assert target.read_text() == "new = 1\n"


def test_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "out.toml"
    _atomic.atomic_write_bytes(target, b"x = 1\n")
    assert target.read_bytes() == b"x = 1\n"


def test_failure_preserves_existing_and_leaves_no_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "out.toml"
    target.write_text("ORIGINAL\n")

    # Simulate a crash exactly at the rename step (after the temp file is written).
    def boom(self: Path, _target: Path) -> None:  # noqa: ARG001
        msg = "simulated failure during replace"
        raise OSError(msg)

    monkeypatch.setattr(Path, "replace", boom)

    with pytest.raises(OSError, match="simulated failure"):
        _atomic.atomic_write_text(target, "NEW CONTENT\n")

    # The existing file must be completely untouched...
    assert target.read_text() == "ORIGINAL\n"
    # ...and the temp file must have been cleaned up.
    assert list(tmp_path.glob("out.toml.*")) == []
