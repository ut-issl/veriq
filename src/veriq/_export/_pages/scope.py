"""Scope listing and detail pages for multi-page static site export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from htpy import Element, a, code, h2, h3, h4, li, main, p, section, ul

from veriq._export._components import status_badge, values_table, verifications_table
from veriq._export._layout import base_page, site_nav
from veriq._export._urls import (
    url_for_calc,
    url_for_index,
    url_for_requirement,
    url_for_scope,
    url_for_scope_list,
    url_for_verification,
)

if TYPE_CHECKING:
    from veriq._export._data import ScopeData
    from veriq._models import Project
    from veriq._traceability import RequirementTraceEntry, TraceabilityReport


# ---------------------------------------------------------------------------
# Scope listing page
# ---------------------------------------------------------------------------


def render_scope_list_page(
    project: Project,
    scope_data: dict[str, ScopeData],
) -> str:
    """Render the scope listing page."""
    scope_names = list(project.scopes.keys())
    return base_page(
        project_name=project.name,
        page_title=f"Scopes - {project.name}",
        sidebar=site_nav(scope_names=scope_names),
        content=_scope_list_content(project, scope_data),
        css_href="/styles.css",
        breadcrumbs=[("Home", url_for_index()), ("Scopes", url_for_scope_list())],
    )


def _scope_list_content(project: Project, scope_data: dict[str, ScopeData]) -> Element:
    """Render the main content of the scope listing page."""
    items: list[Element] = []
    for scope_name in project.scopes:
        data = scope_data.get(scope_name)
        calc_count = len(data.calc_values) if data else 0
        verif_count = len(data.verification_values) if data else 0
        items.append(
            li[
                a(href=url_for_scope(scope_name))[h3[scope_name]],
                p[f"{calc_count} calculations, {verif_count} verifications"],
            ],
        )

    return main(".content")[
        section(id="scope-list")[
            h2["Scopes"],
            ul(".scope-list")[items],
        ],
    ]


# ---------------------------------------------------------------------------
# Scope detail page
# ---------------------------------------------------------------------------


def render_scope_detail_page(
    project: Project,
    scope_name: str,
    data: ScopeData | None,
    traceability: TraceabilityReport,
) -> str:
    """Render a scope detail page."""
    scope_names = list(project.scopes.keys())
    return base_page(
        project_name=project.name,
        page_title=f"{scope_name} - {project.name}",
        sidebar=site_nav(scope_names=scope_names),
        content=_scope_detail_content(scope_name, data, traceability),
        css_href="/styles.css",
        breadcrumbs=[
            ("Home", url_for_index()),
            ("Scopes", url_for_scope_list()),
            (scope_name, url_for_scope(scope_name)),
        ],
    )


def _scope_detail_content(
    scope_name: str,
    data: ScopeData | None,
    traceability: TraceabilityReport,
) -> Element:
    """Render the main content of a scope detail page."""
    sections: list[Element] = []

    # Model section
    if data and data.model_values:
        sections.append(
            section(id="model")[
                h2["Model"],
                values_table(data.model_values, "model", data.model_descriptions),
            ],
        )

    # Calculations section
    if data and data.calc_values:
        sections.append(_calculations_section(scope_name, data))

    # Verifications section
    if data and data.verification_values:
        sections.append(_verifications_section(scope_name, data))

    # Related requirements
    scope_requirements = [e for e in traceability.entries if e.scope_name == scope_name]
    if scope_requirements:
        sections.append(_requirements_section(scope_requirements))

    return main(".content")[
        h2[scope_name],
        sections,
    ]


def _calculations_section(scope_name: str, data: ScopeData) -> Element:
    """Render linked calculations for a scope."""
    items: list[Element] = []
    for calc_name, calc_outputs in data.calc_values.items():
        output_keys = list(calc_outputs.keys())
        summary = f"{len(output_keys)} output{'s' if len(output_keys) != 1 else ''}"
        items.append(
            li[
                a(href=url_for_calc(scope_name, calc_name))[code[f"@{calc_name}"]],
                f" ({summary})",
            ],
        )

    return section(id="calculations")[
        h2["Calculations"],
        ul[items],
    ]


def _verifications_section(scope_name: str, data: ScopeData) -> Element:
    """Render verification results for a scope."""
    items: list[Element] = []
    for name, value in data.verification_values.items():
        all_passed = all(value.values()) if isinstance(value, dict) else value
        items.append(
            li[
                a(href=url_for_verification(scope_name, name))[code[f"?{name}"]],
                " ",
                status_badge(passed=all_passed),
            ],
        )

    return section(id="verifications")[
        h2["Verifications"],
        ul[items],
        h4["Details"],
        verifications_table(data.verification_values, scope_name),
    ]


def _requirements_section(entries: list[RequirementTraceEntry]) -> Element:
    """Render related requirements for a scope."""
    items = [
        li[
            a(href=url_for_requirement(entry.requirement_id))[entry.requirement_id],
            f" - {entry.description}" if entry.description else None,
        ]
        for entry in entries
    ]

    return section(id="requirements")[
        h2["Related Requirements"],
        ul[items],
    ]
