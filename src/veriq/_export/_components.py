"""Reusable htpy components for veriq HTML export."""

from __future__ import annotations

from typing import Any

from htpy import Element, Node, code, em, fragment, span, table, tbody, td, th, thead, tr

from veriq._path import AttributePart, ItemPart
from veriq._table import Table
from veriq._traceability import RequirementStatus


def status_badge(*, passed: bool) -> Element:
    """Render pass/fail status indicator."""
    if passed:
        return span(".status.pass")["✓ PASS"]
    return span(".status.fail")["✗ FAIL"]


def requirement_status_class(status: RequirementStatus) -> str:
    """Get CSS class for requirement status."""
    return {
        RequirementStatus.VERIFIED: "verified",
        RequirementStatus.SATISFIED: "satisfied",
        RequirementStatus.FAILED: "failed",
        RequirementStatus.NOT_VERIFIED: "not-verified",
    }.get(status, "")


def requirement_status_icon(status: RequirementStatus) -> str:
    """Get status icon for requirement."""
    return {
        RequirementStatus.VERIFIED: "✓",
        RequirementStatus.SATISFIED: "○",
        RequirementStatus.FAILED: "✗",
        RequirementStatus.NOT_VERIFIED: "?",
    }.get(status, "")


def render_value(value: Any) -> Node:  # noqa: PLR0911
    """Render a value for display in HTML."""
    if isinstance(value, bool):
        return status_badge(passed=value)

    if isinstance(value, Table):
        return _render_table_value(value)

    if isinstance(value, dict):
        return _render_dict_value(value)

    if isinstance(value, (list, tuple)):
        return _render_list_value(value)

    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return f"{value:.6g}"

    return str(value)


def _render_table_value(tbl: Table) -> Element:  # type: ignore[type-arg]
    """Render a vq.Table as an HTML table."""
    sample_key = next(iter(tbl.keys()))
    is_tuple_key = isinstance(sample_key, tuple)

    if is_tuple_key:
        return _render_multi_dim_table(tbl, sample_key)
    return _render_simple_table(tbl)


def _render_simple_table(tbl: Table) -> Element:  # type: ignore[type-arg]
    """Render a simple 1D Table as an HTML table."""
    return table(".inline-table")[
        thead[tr[th["Key"], th["Value"]]],
        tbody[(tr[td[str(key)], td[render_value(val)]] for key, val in tbl.items())],
    ]


def _render_multi_dim_table(tbl: Table, sample_key: Any) -> Element:  # type: ignore[type-arg]
    """Render a multi-dimensional Table with rowspan grouping."""
    # Group by first key element
    grouped: dict[Any, list[tuple[tuple, Any]]] = {}  # type: ignore[type-arg]
    for key, val in tbl.items():
        first = key[0]  # type: ignore[index]
        if first not in grouped:
            grouped[first] = []
        grouped[first].append((key, val))  # type: ignore[arg-type]

    num_key_cols = len(sample_key)  # type: ignore[arg-type]
    headers = [f"Key{i + 1}" for i in range(num_key_cols)] + ["Value"]

    rows: list[Element] = []
    for first_key, items in grouped.items():
        for i, (full_key, val) in enumerate(items):
            cells: list[Element] = []
            if i == 0:
                cells.append(td(rowspan=str(len(items)))[str(first_key)])
            cells.extend(td[str(k)] for k in full_key[1:])  # type: ignore[index]
            cells.append(td[render_value(val)])
            rows.append(tr[cells])

    return table(".inline-table")[
        thead[tr[(th[h] for h in headers)]],
        tbody[rows],
    ]


def _render_dict_value(d: dict) -> Node:  # type: ignore[type-arg]
    """Render a dict as a compact table."""
    if not d:
        return em["empty"]

    return table(".inline-table.compact")[
        tbody[(tr[td[code[str(key)]], td[render_value(val)]] for key, val in d.items())],
    ]


def _render_list_value(items: list | tuple) -> Node:  # type: ignore[type-arg]
    """Render a list/tuple as a compact display."""
    if not items:
        return em["empty"]

    def _intersperse_values(values: list | tuple) -> list[Node]:  # type: ignore[type-arg]
        parts: list[Node] = []
        for i, item in enumerate(values):
            if i > 0:
                parts.append(", ")
            parts.append(render_value(item))
        return parts

    if len(items) <= 5:
        return fragment["[", _intersperse_values(items), "]"]

    return fragment["[", _intersperse_values(items[:3]), f", ... ({len(items)} items)]"]


def values_table(
    values: dict[str, Any],
    prefix: str,
    descriptions: dict[str, str] | None = None,
) -> Element:
    """Render a table of path -> value pairs with optional descriptions."""
    if descriptions is None:
        descriptions = {}

    has_descriptions = bool(descriptions)

    header_cells = [th["Path"], th["Value"]]
    if has_descriptions:
        header_cells.append(th["Description"])

    rows: list[Element] = []
    for path, value in values.items():
        anchor_id = f"{prefix}-{path}".replace(".", "-").replace("[", "-").replace("]", "")
        cells: list[Element] = [
            td[code[path]],
            td[render_value(value)],
        ]
        if has_descriptions:
            cells.append(td[descriptions.get(path, "")])
        rows.append(tr(id=anchor_id)[cells])

    return table(".data-table")[
        thead[tr[header_cells]],
        tbody[rows],
    ]


def verifications_table(
    verifications: dict[str, bool | dict[str, bool]],
    scope_name: str,
) -> Element:
    """Render verification results table."""
    rows: list[Element] = []

    for name, value in verifications.items():
        anchor_id = f"{scope_name}-verif-{name}"

        if isinstance(value, dict):
            # Table[K, bool] - header row + nested rows
            rows.append(
                tr(id=anchor_id)[td(colspan="2")[code[f"?{name}"]]],
            )
            for key, passed in value.items():
                rows.append(
                    tr(".nested-row")[
                        td(".nested-key")[code[f"[{key}]"]],
                        td[status_badge(passed=passed)],
                    ],
                )
        else:
            rows.append(
                tr(id=anchor_id)[
                    td[code[f"?{name}"]],
                    td[status_badge(passed=value)],
                ],
            )

    return table(".verification-table")[
        thead[tr[th["Verification"], th["Result"]]],
        tbody[rows],
    ]


def format_part(part: Any) -> str:
    """Format a path part for display."""
    if isinstance(part, AttributePart):
        return f".{part.name}"
    if isinstance(part, ItemPart):
        if isinstance(part.key, tuple):
            return f"[{','.join(str(k) for k in part.key)}]"
        return f"[{part.key}]"
    return str(part)
