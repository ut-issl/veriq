"""Requirement listing and detail pages for multi-page static site export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from htpy import Element, a, code, h2, h3, li, main, p, section, span, table, tbody, td, th, thead, tr, ul

from veriq._export._components import (
    requirement_status_class,
    requirement_status_icon,
    status_badge,
)
from veriq._export._layout import base_page, site_nav
from veriq._export._urls import (
    url_for_index,
    url_for_requirement,
    url_for_requirement_list,
    url_for_scope,
    url_for_verification,
)

if TYPE_CHECKING:
    from veriq._models import Project
    from veriq._traceability import RequirementTraceEntry, TraceabilityReport


# ---------------------------------------------------------------------------
# Requirement listing page
# ---------------------------------------------------------------------------


def render_requirement_list_page(
    project: Project,
    traceability: TraceabilityReport,
) -> str:
    """Render the requirement listing page."""
    scope_names = list(project.scopes.keys())
    return base_page(
        project_name=project.name,
        page_title=f"Requirements - {project.name}",
        sidebar=site_nav(scope_names=scope_names),
        content=_requirement_list_content(traceability),
        css_href="/styles.css",
        breadcrumbs=[("Home", url_for_index()), ("Requirements", url_for_requirement_list())],
    )


def _requirement_list_content(traceability: TraceabilityReport) -> Element:
    """Render the main content of the requirement listing page."""
    return main(".content")[
        section(id="requirements")[
            h2["Requirements"],
            _summary_panel(traceability),
            _requirements_table(traceability),
        ],
    ]


def _summary_panel(traceability: TraceabilityReport) -> Element:
    """Render the summary statistics panel."""
    return section(".summary-panel")[
        span[f"Total: {traceability.total_requirements}"],
        span(".status.pass")[f"Verified: {traceability.verified_count}"],
        span(".status.satisfied")[f"Satisfied: {traceability.satisfied_count}"],
        span(".status.fail")[f"Failed: {traceability.failed_count}"],
        span(".status.not-verified")[f"Not Verified: {traceability.not_verified_count}"],
    ]


def _requirements_table(traceability: TraceabilityReport) -> Element:
    """Render a table of all requirements with links to detail pages."""
    rows: list[Element] = []
    for entry in traceability.entries:
        status_cls = requirement_status_class(entry.status)
        status_icon = requirement_status_icon(entry.status)
        indent = "\u00a0\u00a0\u00a0\u00a0" * entry.depth

        rows.append(
            tr(class_=status_cls)[
                td[indent, a(href=url_for_requirement(entry.requirement_id))[entry.requirement_id]],
                td[entry.description],
                td[a(href=url_for_scope(entry.scope_name))[entry.scope_name]],
                td[span(class_=f"status-icon {status_cls}")[status_icon], f" {entry.status.value}"],
            ],
        )

    return table(".data-table")[
        thead[tr[th["Requirement"], th["Description"], th["Scope"], th["Status"]]],
        tbody[rows],
    ]


# ---------------------------------------------------------------------------
# Requirement detail page
# ---------------------------------------------------------------------------


def render_requirement_detail_page(
    project: Project,
    entry: RequirementTraceEntry,
    traceability: TraceabilityReport,
) -> str:
    """Render a requirement detail page."""
    scope_names = list(project.scopes.keys())
    return base_page(
        project_name=project.name,
        page_title=f"{entry.requirement_id} - {project.name}",
        sidebar=site_nav(scope_names=scope_names),
        content=_requirement_detail_content(entry, traceability),
        css_href="/styles.css",
        breadcrumbs=[
            ("Home", url_for_index()),
            ("Requirements", url_for_requirement_list()),
            (entry.requirement_id, url_for_requirement(entry.requirement_id)),
        ],
    )


def _requirement_detail_content(
    entry: RequirementTraceEntry,
    traceability: TraceabilityReport,
) -> Element:
    """Render the main content of a requirement detail page."""
    status_cls = requirement_status_class(entry.status)
    status_icon = requirement_status_icon(entry.status)

    sections: list[Element] = []

    # Status and description
    sections.append(
        section(id="overview")[
            p[
                "Status: ",
                span(class_=f"status-icon {status_cls}")[status_icon],
                f" {entry.status.value}",
            ],
            p["Scope: ", a(href=url_for_scope(entry.scope_name))[entry.scope_name]],
            p[entry.description] if entry.description else None,
        ],
    )

    # Parent requirement
    parent = _find_parent(entry, traceability)
    if parent is not None:
        sections.append(
            section(id="parent")[
                h3["Parent Requirement"],
                p[a(href=url_for_requirement(parent.requirement_id))[parent.requirement_id]],
            ],
        )

    # Child requirements
    if entry.child_ids:
        sections.append(_children_section(entry, traceability))

    if entry.depends_on_ids:
        sections.append(_dependencies_section(entry))

    # Linked verifications with results
    if entry.verification_results:
        sections.append(_verification_results_section(entry))

    return main(".content")[
        h2[entry.requirement_id],
        sections,
    ]


def _find_parent(
    entry: RequirementTraceEntry,
    traceability: TraceabilityReport,
) -> RequirementTraceEntry | None:
    """Find the parent requirement of a given entry."""
    for candidate in traceability.entries:
        if entry.requirement_id in candidate.child_ids:
            return candidate
    return None


def _children_section(
    entry: RequirementTraceEntry,
    traceability: TraceabilityReport,
) -> Element:
    """Render the child requirements section."""
    entries_by_id = {e.requirement_id: e for e in traceability.entries}
    items: list[Element] = []
    for child_id in entry.child_ids:
        child = entries_by_id.get(child_id)
        if child is not None:
            status_cls = requirement_status_class(child.status)
            status_icon = requirement_status_icon(child.status)
            items.append(
                li[
                    a(href=url_for_requirement(child_id))[child_id],
                    " ",
                    span(class_=f"status-icon {status_cls}")[status_icon],
                    f" - {child.description}" if child.description else None,
                ],
            )
        else:
            items.append(li[child_id])

    return section(id="children")[
        h3["Child Requirements"],
        ul[items],
    ]


def _dependencies_section(entry: RequirementTraceEntry) -> Element:
    """Render the depends_on requirements section."""
    items = [li[a(href=url_for_requirement(dep_id))[dep_id]] for dep_id in entry.depends_on_ids]
    return section(id="dependencies")[
        h3["Depends On"],
        ul[items],
    ]


def _verification_results_section(entry: RequirementTraceEntry) -> Element:
    """Render linked verification results."""
    rows: list[Element] = []
    for vr in entry.verification_results:
        key_display = ""
        if vr.table_key is not None:
            key_display = (
                f"[{','.join(vr.table_key)}]" if isinstance(vr.table_key, tuple) else f"[{vr.table_key}]"
            )

        rows.append(
            tr[
                td[
                    a(href=url_for_verification(vr.scope_name, vr.verification_name))[
                        code[f"?{vr.verification_name}{key_display}"],
                    ],
                ],
                td[a(href=url_for_scope(vr.scope_name))[vr.scope_name]],
                td[status_badge(passed=vr.passed)],
            ],
        )

    return section(id="verifications")[
        h3["Verification Results"],
        table(".verification-table")[
            thead[tr[th["Verification"], th["Scope"], th["Result"]]],
            tbody[rows],
        ],
    ]
