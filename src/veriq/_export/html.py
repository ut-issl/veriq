"""HTML rendering for veriq export."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any

from veriq._path import CalcPath, ModelPath, VerificationPath
from veriq._table import Table
from veriq._traceability import RequirementStatus, build_traceability_report

if TYPE_CHECKING:
    from pydantic import BaseModel

    from veriq._eval_engine import EvaluationResult
    from veriq._models import Project
    from veriq._traceability import TraceabilityReport


def render_html(
    project: Project,
    model_data: dict[str, BaseModel],
    result: EvaluationResult,
) -> str:
    """Render evaluation results as an HTML document.

    Args:
        project: The project that was evaluated.
        model_data: Input model data by scope name.
        result: The evaluation result containing all computed values.

    Returns:
        Complete HTML document as a string.

    """
    # Build traceability report
    traceability = build_traceability_report(project, result)

    # Group results by scope and type
    scope_data = _group_results_by_scope(project, model_data, result)

    # Generate HTML
    parts = [
        _render_head(project.name),
        _render_body_start(project.name),
        _render_sidebar(project, traceability),
        _render_main_content(project, scope_data, traceability),
        _render_body_end(),
    ]

    return "".join(parts)


def _render_head(project_name: str) -> str:
    """Render HTML head with inline CSS."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(project_name)} - veriq Report</title>
    <style>
{_get_css()}
    </style>
</head>
"""


def _render_body_start(project_name: str) -> str:
    """Render body opening and header."""
    return f"""<body>
<header>
    <h1>{html.escape(project_name)}</h1>
    <p class="subtitle">veriq Evaluation Report</p>
</header>
<div class="container">
"""


def _render_body_end() -> str:
    """Render body closing."""
    return """</div>
</body>
</html>
"""


def _render_sidebar(project: Project, _traceability: TraceabilityReport) -> str:
    """Render navigation sidebar."""
    parts = ['<nav class="sidebar">', "<h2>Navigation</h2>", "<ul>"]

    # Scopes section
    parts.append('<li><a href="#scopes">Scopes</a><ul>')
    parts.extend(
        f'<li><a href="#scope-{html.escape(scope_name)}">{html.escape(scope_name)}</a></li>'
        for scope_name in project.scopes
    )
    parts.append("</ul></li>")

    # Requirements section
    parts.append('<li><a href="#requirements">Requirements</a></li>')

    parts.append("</ul>")
    parts.append("</nav>")

    return "\n".join(parts)


def _render_main_content(
    project: Project,
    scope_data: dict[str, ScopeData],
    traceability: TraceabilityReport,
) -> str:
    """Render main content area."""
    parts = ['<main class="content">']

    # Scopes section
    parts.append('<section id="scopes">')
    parts.append("<h2>Scopes</h2>")

    for scope_name, scope in project.scopes.items():
        data = scope_data.get(scope_name)
        parts.append(_render_scope_section(scope_name, scope, data))

    parts.append("</section>")

    # Requirements section
    parts.append(_render_requirements_section(traceability))

    parts.append("</main>")

    return "\n".join(parts)


def _render_scope_section(scope_name: str, _scope: Any, data: ScopeData | None) -> str:
    """Render a single scope section."""
    parts = [
        f'<details open id="scope-{html.escape(scope_name)}">',
        f"<summary><h3>{html.escape(scope_name)}</h3></summary>",
        '<div class="scope-content">',
    ]

    # Model data
    if data and data.model_values:
        parts.append('<div class="section">')
        parts.append("<h4>Model</h4>")
        parts.append(_render_values_table(data.model_values, f"{scope_name}-model"))
        parts.append("</div>")

    # Calculations
    if data and data.calc_values:
        parts.append('<div class="section">')
        parts.append("<h4>Calculations</h4>")
        for calc_name, calc_outputs in data.calc_values.items():
            anchor_id = f"{scope_name}-calc-{calc_name}"
            parts.append(f'<div class="calc-block" id="{html.escape(anchor_id)}">')
            parts.append(f"<h5><code>@{html.escape(calc_name)}</code></h5>")
            parts.append(_render_values_table(calc_outputs, anchor_id))
            parts.append("</div>")
        parts.append("</div>")

    # Verifications
    if data and data.verification_values:
        parts.append('<div class="section">')
        parts.append("<h4>Verifications</h4>")
        parts.append(_render_verifications_table(data.verification_values, scope_name))
        parts.append("</div>")

    parts.append("</div>")
    parts.append("</details>")

    return "\n".join(parts)


def _render_values_table(values: dict[str, Any], prefix: str) -> str:
    """Render a table of path -> value pairs."""
    parts = ['<table class="data-table">', "<thead><tr><th>Path</th><th>Value</th></tr></thead>", "<tbody>"]

    for path, value in values.items():
        anchor_id = f"{prefix}-{path}".replace(".", "-").replace("[", "-").replace("]", "")
        rendered_value = _render_value(value)
        parts.append(
            f'<tr id="{html.escape(anchor_id)}">'
            f"<td><code>{html.escape(path)}</code></td>"
            f"<td>{rendered_value}</td>"
            f"</tr>",
        )

    parts.append("</tbody></table>")

    return "\n".join(parts)


def _render_verifications_table(verifications: dict[str, bool | dict[str, bool]], scope_name: str) -> str:
    """Render verification results table."""
    parts = [
        '<table class="verification-table">',
        "<thead><tr><th>Verification</th><th>Result</th></tr></thead>",
        "<tbody>",
    ]

    for name, value in verifications.items():
        anchor_id = f"{scope_name}-verif-{name}"

        if isinstance(value, dict):
            # Table[K, bool] verification - render as nested rows
            parts.append(
                f'<tr id="{html.escape(anchor_id)}">'
                f'<td colspan="2"><code>?{html.escape(name)}</code></td>'
                f"</tr>",
            )
            for key, passed in value.items():
                status = _render_status(passed=passed)
                parts.append(
                    f'<tr class="nested-row">'
                    f'<td class="nested-key"><code>[{html.escape(str(key))}]</code></td>'
                    f"<td>{status}</td>"
                    f"</tr>",
                )
        else:
            # Simple bool verification
            status = _render_status(passed=value)
            parts.append(
                f'<tr id="{html.escape(anchor_id)}">'
                f"<td><code>?{html.escape(name)}</code></td>"
                f"<td>{status}</td>"
                f"</tr>",
            )

    parts.append("</tbody></table>")

    return "\n".join(parts)


def _render_status(*, passed: bool) -> str:
    """Render pass/fail status indicator."""
    if passed:
        return '<span class="status pass">✓ PASS</span>'
    return '<span class="status fail">✗ FAIL</span>'


def _render_value(value: Any) -> str:  # noqa: PLR0911
    """Render a value for display in HTML."""
    if isinstance(value, bool):
        return _render_status(passed=value)

    if isinstance(value, Table):
        return _render_table_value(value)

    if isinstance(value, dict):
        return _render_dict_value(value)

    if isinstance(value, (list, tuple)):
        return _render_list_value(value)

    if isinstance(value, float):
        # Format floats nicely
        if value == int(value):
            return html.escape(str(int(value)))
        return html.escape(f"{value:.6g}")

    return html.escape(str(value))


def _render_table_value(table: Table) -> str:  # type: ignore[type-arg]
    """Render a vq.Table as an HTML table."""
    parts = ['<table class="inline-table">']

    # Check if keys are tuples (multi-dimensional)
    sample_key = next(iter(table.keys()))
    is_tuple_key = isinstance(sample_key, tuple)

    if is_tuple_key:
        # Multi-dimensional table with tuple keys
        # Group by first key element for rowspan
        grouped: dict[Any, list[tuple[tuple, Any]]] = {}  # type: ignore[type-arg]
        for key, val in table.items():
            first = key[0]  # type: ignore[index]
            if first not in grouped:
                grouped[first] = []
            grouped[first].append((key, val))  # type: ignore[arg-type]

        # Determine number of key columns
        num_key_cols = len(sample_key)  # type: ignore[arg-type]
        headers = [f"Key{i + 1}" for i in range(num_key_cols)] + ["Value"]
        parts.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead>")
        parts.append("<tbody>")

        for first_key, items in grouped.items():
            for i, (full_key, val) in enumerate(items):
                parts.append("<tr>")
                if i == 0:
                    # First row of group - add rowspan for first key
                    rowspan = len(items)
                    parts.append(f'<td rowspan="{rowspan}">{html.escape(str(first_key))}</td>')

                # Add remaining key parts
                parts.extend(f"<td>{html.escape(str(k))}</td>" for k in full_key[1:])  # type: ignore[index]

                # Add value
                parts.append(f"<td>{_render_value(val)}</td>")
                parts.append("</tr>")

        parts.append("</tbody>")
    else:
        # Simple 1D table
        parts.append("<thead><tr><th>Key</th><th>Value</th></tr></thead>")
        parts.append("<tbody>")
        for key, val in table.items():
            parts.append(f"<tr><td>{html.escape(str(key))}</td><td>{_render_value(val)}</td></tr>")
        parts.append("</tbody>")

    parts.append("</table>")

    return "\n".join(parts)


def _render_dict_value(d: dict) -> str:  # type: ignore[type-arg]
    """Render a dict as a compact table."""
    if not d:
        return "<em>empty</em>"

    parts = ['<table class="inline-table compact">', "<tbody>"]
    for key, val in d.items():
        parts.append(f"<tr><td><code>{html.escape(str(key))}</code></td><td>{_render_value(val)}</td></tr>")
    parts.append("</tbody></table>")

    return "\n".join(parts)


def _render_list_value(items: list | tuple) -> str:  # type: ignore[type-arg]
    """Render a list/tuple as a compact display."""
    if not items:
        return "<em>empty</em>"

    if len(items) <= 5:
        rendered = ", ".join(_render_value(item) for item in items)
        return f"[{rendered}]"

    # For longer lists, show first few items
    rendered = ", ".join(_render_value(item) for item in items[:3])
    return f"[{rendered}, ... ({len(items)} items)]"


def _render_requirements_section(traceability: TraceabilityReport) -> str:
    """Render the requirements traceability section."""
    parts = [
        '<section id="requirements">',
        "<h2>Requirements</h2>",
    ]

    # Summary panel
    parts.append('<div class="summary-panel">')
    parts.append(f"<span>Total: {traceability.total_requirements}</span>")
    parts.append(f'<span class="status pass">Verified: {traceability.verified_count}</span>')
    parts.append(f'<span class="status satisfied">Satisfied: {traceability.satisfied_count}</span>')
    parts.append(f'<span class="status fail">Failed: {traceability.failed_count}</span>')
    parts.append(f'<span class="status not-verified">Not Verified: {traceability.not_verified_count}</span>')
    parts.append("</div>")

    # Build tree structure from flat entries
    parts.append('<div class="requirements-tree">')
    parts.append(_render_requirements_tree(traceability))
    parts.append("</div>")

    parts.append("</section>")

    return "\n".join(parts)


def _render_requirements_tree(traceability: TraceabilityReport) -> str:
    """Render requirements as a nested tree."""
    # Build a lookup from ID to entry
    entries_by_id = {e.requirement_id: e for e in traceability.entries}

    # Find root entries (depth 0)
    root_entries = [e for e in traceability.entries if e.depth == 0]

    parts = ['<ul class="req-tree">']
    parts.extend(_render_requirement_node(entry, entries_by_id) for entry in root_entries)
    parts.append("</ul>")

    return "\n".join(parts)


def _render_requirement_node(entry: Any, entries_by_id: dict) -> str:  # type: ignore[type-arg]
    """Render a single requirement node with its children."""
    status_class = _get_status_class(entry.status)
    status_icon = _get_status_icon(entry.status)

    parts = [
        f'<li class="req-node {status_class}" id="req-{html.escape(entry.requirement_id)}">',
        "<details open>",
        f'<summary><span class="status-icon">{status_icon}</span> ',
        f"<strong>{html.escape(entry.requirement_id)}</strong>",
    ]

    if entry.description:
        parts.append(f' <span class="req-desc">- {html.escape(entry.description)}</span>')

    parts.append("</summary>")

    # Verification links
    if entry.linked_verifications:
        parts.append('<div class="req-verifications">')
        parts.append("<small>Verified by: ")
        verif_links = [f"<code>{html.escape(verif)}</code>" for verif in entry.linked_verifications]
        parts.append(", ".join(verif_links))
        parts.append("</small></div>")

    # Dependencies
    if entry.depends_on_ids:
        parts.append('<div class="req-deps">')
        parts.append("<small>Depends on: ")
        dep_links = [
            f'<a href="#req-{html.escape(dep_id)}">{html.escape(dep_id)}</a>'
            for dep_id in entry.depends_on_ids
        ]
        parts.append(", ".join(dep_links))
        parts.append("</small></div>")

    # Children
    if entry.child_ids:
        parts.append('<ul class="req-children">')
        parts.extend(
            _render_requirement_node(entries_by_id[child_id], entries_by_id)
            for child_id in entry.child_ids
            if child_id in entries_by_id
        )
        parts.append("</ul>")

    parts.append("</details>")
    parts.append("</li>")

    return "\n".join(parts)


def _get_status_class(status: RequirementStatus) -> str:
    """Get CSS class for requirement status."""
    return {
        RequirementStatus.VERIFIED: "verified",
        RequirementStatus.SATISFIED: "satisfied",
        RequirementStatus.FAILED: "failed",
        RequirementStatus.NOT_VERIFIED: "not-verified",
    }.get(status, "")


def _get_status_icon(status: RequirementStatus) -> str:
    """Get status icon for requirement."""
    return {
        RequirementStatus.VERIFIED: "✓",
        RequirementStatus.SATISFIED: "○",
        RequirementStatus.FAILED: "✗",
        RequirementStatus.NOT_VERIFIED: "?",
    }.get(status, "")


class ScopeData:
    """Container for scope-level data extracted from evaluation results."""

    def __init__(self) -> None:
        self.model_values: dict[str, Any] = {}
        self.calc_values: dict[str, dict[str, Any]] = {}
        self.verification_values: dict[str, bool | dict[str, bool]] = {}


def _group_results_by_scope(  # noqa: C901
    project: Project,
    _model_data: dict[str, Any],
    result: EvaluationResult,
) -> dict[str, ScopeData]:
    """Group evaluation results by scope and type."""
    scope_data: dict[str, ScopeData] = {}

    for scope_name in project.scopes:
        scope_data[scope_name] = ScopeData()

    for ppath, value in result.values.items():
        scope_name = ppath.scope
        if scope_name not in scope_data:
            scope_data[scope_name] = ScopeData()

        data = scope_data[scope_name]

        if isinstance(ppath.path, ModelPath):
            # Model value
            path_str = str(ppath.path)
            data.model_values[path_str] = value

        elif isinstance(ppath.path, CalcPath):
            # Calculation output
            calc_name = ppath.path.calc_name
            if calc_name not in data.calc_values:
                data.calc_values[calc_name] = {}

            # Build path string without the calculation name prefix
            if ppath.path.parts:
                parts_str = "".join(_format_part(p) for p in ppath.path.parts)
                data.calc_values[calc_name][parts_str] = value
            else:
                # Root calculation output
                data.calc_values[calc_name]["(output)"] = value

        elif isinstance(ppath.path, VerificationPath):
            # Verification result
            verif_name = ppath.path.verification_name
            if ppath.path.parts:
                # Table[K, bool] verification
                if verif_name not in data.verification_values:
                    data.verification_values[verif_name] = {}
                key_str = "".join(_format_part(p) for p in ppath.path.parts)
                data.verification_values[verif_name][key_str] = value  # type: ignore[index]
            else:
                # Simple bool verification
                data.verification_values[verif_name] = value

    return scope_data


def _format_part(part: Any) -> str:
    """Format a path part for display."""
    from veriq._path import AttributePart, ItemPart  # noqa: PLC0415

    if isinstance(part, AttributePart):
        return f".{part.name}"
    if isinstance(part, ItemPart):
        if isinstance(part.key, tuple):
            return f"[{','.join(str(k) for k in part.key)}]"
        return f"[{part.key}]"
    return str(part)


def _get_css() -> str:
    """Return inline CSS for the HTML document."""
    return """
:root {
    --bg-color: #f8f9fa;
    --text-color: #212529;
    --border-color: #dee2e6;
    --primary-color: #0d6efd;
    --success-color: #198754;
    --warning-color: #ffc107;
    --danger-color: #dc3545;
    --info-color: #0dcaf0;
    --sidebar-width: 250px;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    color: var(--text-color);
    background-color: var(--bg-color);
}

header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 2rem;
    text-align: center;
}

header h1 {
    margin-bottom: 0.5rem;
}

header .subtitle {
    opacity: 0.9;
}

.container {
    display: flex;
    min-height: calc(100vh - 120px);
}

.sidebar {
    width: var(--sidebar-width);
    background: white;
    border-right: 1px solid var(--border-color);
    padding: 1.5rem;
    position: sticky;
    top: 0;
    height: fit-content;
    max-height: 100vh;
    overflow-y: auto;
}

.sidebar h2 {
    font-size: 1rem;
    text-transform: uppercase;
    color: #6c757d;
    margin-bottom: 1rem;
}

.sidebar ul {
    list-style: none;
}

.sidebar li {
    margin: 0.25rem 0;
}

.sidebar a {
    color: var(--text-color);
    text-decoration: none;
    display: block;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
}

.sidebar a:hover {
    background: var(--bg-color);
}

.sidebar ul ul {
    margin-left: 1rem;
}

.content {
    flex: 1;
    padding: 2rem;
    max-width: calc(100% - var(--sidebar-width));
}

section {
    margin-bottom: 2rem;
}

h2 {
    border-bottom: 2px solid var(--primary-color);
    padding-bottom: 0.5rem;
    margin-bottom: 1.5rem;
}

h3 {
    display: inline;
    font-size: 1.25rem;
}

h4 {
    color: #6c757d;
    margin-bottom: 0.75rem;
}

h5 {
    margin-bottom: 0.5rem;
}

details {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-bottom: 1rem;
}

details summary {
    padding: 1rem;
    cursor: pointer;
    background: #f8f9fa;
    border-radius: 8px 8px 0 0;
}

details[open] summary {
    border-bottom: 1px solid var(--border-color);
}

.scope-content {
    padding: 1rem;
}

.section {
    margin-bottom: 1.5rem;
}

.calc-block {
    margin-bottom: 1rem;
    padding: 0.75rem;
    background: #f8f9fa;
    border-radius: 4px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 0.5rem;
}

.data-table, .verification-table {
    background: white;
}

th, td {
    padding: 0.5rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

th {
    background: #f1f3f4;
    font-weight: 600;
}

.inline-table {
    width: auto;
    margin: 0;
    font-size: 0.9em;
}

.inline-table.compact td {
    padding: 0.25rem 0.5rem;
}

.nested-row td {
    padding-left: 2rem;
}

.nested-key {
    color: #6c757d;
}

code {
    background: #e9ecef;
    padding: 0.125rem 0.375rem;
    border-radius: 3px;
    font-size: 0.9em;
}

.status {
    display: inline-block;
    padding: 0.125rem 0.5rem;
    border-radius: 4px;
    font-weight: 500;
}

.status.pass {
    background: #d1e7dd;
    color: #0f5132;
}

.status.fail {
    background: #f8d7da;
    color: #842029;
}

.status.satisfied {
    background: #cff4fc;
    color: #055160;
}

.status.not-verified {
    background: #fff3cd;
    color: #664d03;
}

.summary-panel {
    display: flex;
    gap: 1.5rem;
    padding: 1rem;
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
}

.summary-panel span {
    font-weight: 500;
}

.requirements-tree {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
}

.req-tree {
    list-style: none;
}

.req-tree ul {
    list-style: none;
    margin-left: 1.5rem;
    border-left: 2px solid var(--border-color);
    padding-left: 1rem;
}

.req-node {
    margin: 0.5rem 0;
}

.req-node details {
    border: none;
    background: transparent;
}

.req-node summary {
    padding: 0.5rem;
    background: transparent;
    border-radius: 4px;
}

.req-node summary:hover {
    background: var(--bg-color);
}

.req-node.verified .status-icon { color: var(--success-color); }
.req-node.satisfied .status-icon { color: var(--info-color); }
.req-node.failed .status-icon { color: var(--danger-color); }
.req-node.not-verified .status-icon { color: var(--warning-color); }

.req-desc {
    color: #6c757d;
}

.req-verifications, .req-deps {
    margin-left: 1.5rem;
    padding: 0.25rem 0;
    color: #6c757d;
}

.req-verifications code {
    font-size: 0.85em;
}

.req-deps a {
    color: var(--primary-color);
}

.req-children {
    margin-top: 0.5rem;
}

@media (max-width: 768px) {
    .container {
        flex-direction: column;
    }

    .sidebar {
        width: 100%;
        position: relative;
        border-right: none;
        border-bottom: 1px solid var(--border-color);
    }

    .content {
        max-width: 100%;
    }
}
"""
