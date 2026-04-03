import pytest

from veriq._diff import DiffEntry, DiffKind, diff_dicts, format_toml_path


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (("voltage",), "voltage"),
        (("Power", "voltage"), "Power.voltage"),
        (("a", "b", "c"), "a.b.c"),
        # Key with a period must be quoted
        (("a.b",), '"a.b"'),
        (("scope", "x.y"), 'scope."x.y"'),
        # Key with spaces must be quoted
        (("has space",), '"has space"'),
        # Key with double-quote must be escaped
        (('say "hi"',), r'"say \"hi\""'),
        # Key with backslash must be escaped
        (("back\\slash",), r'"back\\slash"'),
        # Bare keys allow alphanumerics, dashes, underscores
        (("my-key_2",), "my-key_2"),
        # Empty key must be quoted
        (("",), '""'),
    ],
)
def test_format_toml_path(path: tuple[str, ...], expected: str):
    assert format_toml_path(path) == expected


def test_identical_dicts():
    d = {"a": 1, "b": {"c": 2}}
    assert diff_dicts(d, d) == []


def test_empty_dicts():
    assert diff_dicts({}, {}) == []


def test_added_key():
    result = diff_dicts({}, {"x": 1})
    assert result == [DiffEntry(path=("x",), kind=DiffKind.ADDED, left=None, right=1)]


def test_removed_key():
    result = diff_dicts({"x": 1}, {})
    assert result == [DiffEntry(path=("x",), kind=DiffKind.REMOVED, left=1, right=None)]


def test_changed_value():
    result = diff_dicts({"x": 1}, {"x": 2})
    assert result == [DiffEntry(path=("x",), kind=DiffKind.CHANGED, left=1, right=2)]


def test_nested_diff():
    left = {"scope": {"voltage": 3.3, "current": 1.0}}
    right = {"scope": {"voltage": 5.0, "current": 1.0}}
    result = diff_dicts(left, right)
    assert result == [DiffEntry(path=("scope", "voltage"), kind=DiffKind.CHANGED, left=3.3, right=5.0)]


def test_nested_added_and_removed():
    left = {"scope": {"a": 1}}
    right = {"scope": {"b": 2}}
    result = diff_dicts(left, right)
    assert result == [
        DiffEntry(path=("scope", "a"), kind=DiffKind.REMOVED, left=1, right=None),
        DiffEntry(path=("scope", "b"), kind=DiffKind.ADDED, left=None, right=2),
    ]


def test_type_change_dict_to_scalar():
    left = {"x": {"nested": 1}}
    right = {"x": 42}
    result = diff_dicts(left, right)
    assert result == [DiffEntry(path=("x",), kind=DiffKind.CHANGED, left={"nested": 1}, right=42)]


def test_multiple_scopes():
    left = {"Power": {"voltage": 3.3}, "Thermal": {"temp": 25.0}}
    right = {"Power": {"voltage": 5.0}, "Thermal": {"temp": 25.0}}
    result = diff_dicts(left, right)
    assert result == [DiffEntry(path=("Power", "voltage"), kind=DiffKind.CHANGED, left=3.3, right=5.0)]


def test_deeply_nested():
    left = {"a": {"b": {"c": {"d": 1}}}}
    right = {"a": {"b": {"c": {"d": 2}}}}
    result = diff_dicts(left, right)
    assert result == [DiffEntry(path=("a", "b", "c", "d"), kind=DiffKind.CHANGED, left=1, right=2)]


def test_mixed_changes():
    left = {"a": 1, "b": 2, "c": 3}
    right = {"a": 1, "b": 99, "d": 4}
    result = diff_dicts(left, right)
    assert result == [
        DiffEntry(path=("b",), kind=DiffKind.CHANGED, left=2, right=99),
        DiffEntry(path=("c",), kind=DiffKind.REMOVED, left=3, right=None),
        DiffEntry(path=("d",), kind=DiffKind.ADDED, left=None, right=4),
    ]


# --- Tolerance tests ---


def test_rel_tol_suppresses_small_difference():
    left = {"x": 1.0}
    right = {"x": 1.0 + 1e-10}
    assert diff_dicts(left, right, rel_tol=1e-9) == []


def test_rel_tol_reports_large_difference():
    left = {"x": 1.0}
    right = {"x": 1.1}
    result = diff_dicts(left, right, rel_tol=1e-9)
    assert len(result) == 1
    assert result[0].kind is DiffKind.CHANGED


def test_rel_tol_suppresses_close_values():
    left = {"x": 1000.0}
    right = {"x": 1000.0 * (1 + 1e-10)}
    assert diff_dicts(left, right, rel_tol=1e-9) == []


def test_tolerance_nested():
    left = {"scope": {"voltage": 3.3, "current": 1.0}}
    right = {"scope": {"voltage": 3.3 * (1 + 1e-12), "current": 1.0}}
    assert diff_dicts(left, right, rel_tol=1e-9) == []


def test_tolerance_does_not_affect_non_numeric():
    left = {"name": "foo"}
    right = {"name": "bar"}
    result = diff_dicts(left, right, rel_tol=1e-9)
    assert len(result) == 1
    assert result[0].kind is DiffKind.CHANGED


def test_tolerance_int_and_float():
    left = {"x": 1}
    right = {"x": 1.0 + 1e-12}
    assert diff_dicts(left, right, rel_tol=1e-9) == []


def test_tolerance_does_not_affect_booleans():
    """Booleans should always be compared exactly, even with tolerance."""
    left = {"flag": True}
    right = {"flag": False}
    result = diff_dicts(left, right, rel_tol=1e9)
    assert result == [DiffEntry(path=("flag",), kind=DiffKind.CHANGED, left=True, right=False)]


def test_zero_tolerance_is_default_exact():
    """With default tolerances (0.0), behavior is exact comparison."""
    left = {"x": 1.0}
    right = {"x": 1.0 + 1e-15}
    result = diff_dicts(left, right)
    # 1.0 + 1e-15 != 1.0 in Python, so this should be reported
    if left["x"] != right["x"]:
        assert len(result) == 1
