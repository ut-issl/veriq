"""Landing page for multi-page static site export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from htpy import Element, a, div, h2, h3, li, main, section, span, table, tbody, td, th, thead, tr, ul

from veriq._export._components import requirement_status_class, requirement_status_icon, status_badge
from veriq._export._layout import base_page, site_nav
from veriq._export._urls import url_for_requirement, url_for_scope, url_for_verification

if TYPE_CHECKING:
    from veriq._export.html import ScopeData
    from veriq._models import Project
    from veriq._traceability import TraceabilityReport


def render_index_page(
    project: Project,
    scope_data: dict[str, ScopeData],
    traceability: TraceabilityReport,
) -> str:
    """Render the landing page."""
    return base_page(
        project_name=project.name,
        page_title=f"{project.name} - veriq Report",
        sidebar=site_nav(scope_names=list(project.scopes.keys())),
        content=_index_content(project, scope_data, traceability),
        css_href="/styles.css",
    )


def _index_content(
    project: Project,
    scope_data: dict[str, ScopeData],
    traceability: TraceabilityReport,
) -> Element:
    """Render the main content of the landing page."""
    return main(".content")[
        _overview_section(project, scope_data),
        _requirements_summary_section(traceability),
    ]


def _overview_section(project: Project, scope_data: dict[str, ScopeData]) -> Element:
    """Render project overview with scope summary cards."""
    return section(id="overview")[
        h2["Project Overview"],
        div(".scope-cards")[[_scope_card(name, scope_data.get(name)) for name in project.scopes],],
    ]


def _scope_card(scope_name: str, data: ScopeData | None) -> Element:
    """Render a summary card for a scope."""
    calc_count = len(data.calc_values) if data else 0
    verif_count = len(data.verification_values) if data else 0

    verif_summary: list[Element] = []
    if data and data.verification_values:
        for name, value in data.verification_values.items():
            all_passed = all(value.values()) if isinstance(value, dict) else value
            verif_summary.append(
                li[
                    a(href=url_for_verification(scope_name, name))[
                        status_badge(passed=all_passed),
                        f" ?{name}",
                    ],
                ],
            )

    return div(".scope-card")[
        h3[a(href=url_for_scope(scope_name))[scope_name]],
        div(".scope-stats")[
            span[f"{calc_count} calculations"],
            span[f" | {verif_count} verifications"],
        ],
        ul(".scope-verif-list")[verif_summary] if verif_summary else None,
    ]


def _requirements_summary_section(traceability: TraceabilityReport) -> Element:
    """Render requirement summary table."""
    return section(id="requirements")[
        h2["Requirements Summary"],
        div(".summary-panel")[
            span[f"Total: {traceability.total_requirements}"],
            span(".status.pass")[f"Verified: {traceability.verified_count}"],
            span(".status.satisfied")[f"Satisfied: {traceability.satisfied_count}"],
            span(".status.fail")[f"Failed: {traceability.failed_count}"],
            span(".status.not-verified")[f"Not Verified: {traceability.not_verified_count}"],
        ],
        _requirements_summary_table(traceability),
    ]


def _requirements_summary_table(traceability: TraceabilityReport) -> Element:
    """Render a summary table of all requirements."""
    rows: list[Element] = []
    for entry in traceability.entries:
        status_cls = requirement_status_class(entry.status)
        status_icon = requirement_status_icon(entry.status)
        indent = "\u00a0\u00a0\u00a0\u00a0" * entry.depth  # non-breaking spaces for depth

        rows.append(
            tr(class_=status_cls)[
                td[indent, a(href=url_for_requirement(entry.requirement_id))[entry.requirement_id]],
                td[entry.description],
                td[span(class_=f"status-icon {status_cls}")[status_icon], f" {entry.status.value}"],
            ],
        )

    return table(".data-table")[
        thead[tr[th["Requirement"], th["Description"], th["Status"]]],
        tbody[rows],
    ]
