from veriq._diff import DiffEntry, DiffKind, diff_dicts


def test_identical_dicts():
    d = {"a": 1, "b": {"c": 2}}
    assert diff_dicts(d, d) == []


def test_empty_dicts():
    assert diff_dicts({}, {}) == []


def test_added_key():
    result = diff_dicts({}, {"x": 1})
    assert result == [DiffEntry(path="x", kind=DiffKind.ADDED, left=None, right=1)]


def test_removed_key():
    result = diff_dicts({"x": 1}, {})
    assert result == [DiffEntry(path="x", kind=DiffKind.REMOVED, left=1, right=None)]


def test_changed_value():
    result = diff_dicts({"x": 1}, {"x": 2})
    assert result == [DiffEntry(path="x", kind=DiffKind.CHANGED, left=1, right=2)]


def test_nested_diff():
    left = {"scope": {"voltage": 3.3, "current": 1.0}}
    right = {"scope": {"voltage": 5.0, "current": 1.0}}
    result = diff_dicts(left, right)
    assert result == [DiffEntry(path="scope.voltage", kind=DiffKind.CHANGED, left=3.3, right=5.0)]


def test_nested_added_and_removed():
    left = {"scope": {"a": 1}}
    right = {"scope": {"b": 2}}
    result = diff_dicts(left, right)
    assert result == [
        DiffEntry(path="scope.a", kind=DiffKind.REMOVED, left=1, right=None),
        DiffEntry(path="scope.b", kind=DiffKind.ADDED, left=None, right=2),
    ]


def test_type_change_dict_to_scalar():
    left = {"x": {"nested": 1}}
    right = {"x": 42}
    result = diff_dicts(left, right)
    assert result == [DiffEntry(path="x", kind=DiffKind.CHANGED, left={"nested": 1}, right=42)]


def test_multiple_scopes():
    left = {"Power": {"voltage": 3.3}, "Thermal": {"temp": 25.0}}
    right = {"Power": {"voltage": 5.0}, "Thermal": {"temp": 25.0}}
    result = diff_dicts(left, right)
    assert result == [DiffEntry(path="Power.voltage", kind=DiffKind.CHANGED, left=3.3, right=5.0)]


def test_deeply_nested():
    left = {"a": {"b": {"c": {"d": 1}}}}
    right = {"a": {"b": {"c": {"d": 2}}}}
    result = diff_dicts(left, right)
    assert result == [DiffEntry(path="a.b.c.d", kind=DiffKind.CHANGED, left=1, right=2)]


def test_mixed_changes():
    left = {"a": 1, "b": 2, "c": 3}
    right = {"a": 1, "b": 99, "d": 4}
    result = diff_dicts(left, right)
    assert result == [
        DiffEntry(path="b", kind=DiffKind.CHANGED, left=2, right=99),
        DiffEntry(path="c", kind=DiffKind.REMOVED, left=3, right=None),
        DiffEntry(path="d", kind=DiffKind.ADDED, left=None, right=4),
    ]
