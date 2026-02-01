"""Verification detail pages for multi-page static site export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from htpy import Element, a, code, h2, h3, li, main, p, section, ul

from veriq._export._components import verifications_table
from veriq._export._layout import base_page, site_nav
from veriq._export._urls import (
    url_for_index,
    url_for_requirement,
    url_for_scope,
    url_for_scope_list,
    url_for_verification,
)

if TYPE_CHECKING:
    from veriq._export.html import ScopeData
    from veriq._models import Project
    from veriq._traceability import TraceabilityReport


def render_verification_detail_page(
    project: Project,
    scope_name: str,
    verif_name: str,
    data: ScopeData | None,
    traceability: TraceabilityReport,
) -> str:
    """Render a verification detail page."""
    scope_names = list(project.scopes.keys())
    scope = project.scopes[scope_name]
    verif = scope.verifications.get(verif_name)

    return base_page(
        project_name=project.name,
        page_title=f"?{verif_name} - {scope_name} - {project.name}",
        sidebar=site_nav(scope_names=scope_names),
        content=_verif_detail_content(scope_name, verif_name, verif, data, traceability),
        css_href="/styles.css",
        breadcrumbs=[
            ("Home", url_for_index()),
            ("Scopes", url_for_scope_list()),
            (scope_name, url_for_scope(scope_name)),
            (f"?{verif_name}", url_for_verification(scope_name, verif_name)),
        ],
    )


def _verif_detail_content(
    scope_name: str,
    verif_name: str,
    verif: object | None,
    data: ScopeData | None,
    traceability: TraceabilityReport,
) -> Element:
    """Render the main content of a verification detail page."""
    sections: list[Element] = []

    # Scope link
    sections.append(
        p["Scope: ", a(href=url_for_scope(scope_name))[scope_name]],
    )

    # Input references
    if verif is not None and hasattr(verif, "dep_ppaths") and verif.dep_ppaths:
        dep_items = [
            li[code[f"{param_name}"], " \u2190 ", code[str(ppath)]] for param_name, ppath in verif.dep_ppaths.items()
        ]
        sections.append(
            section(id="inputs")[
                h3["Inputs"],
                ul[dep_items],
            ],
        )

    # Result
    if data and verif_name in data.verification_values:
        result_value = data.verification_values[verif_name]
        sections.append(
            section(id="result")[
                h3["Result"],
                verifications_table({verif_name: result_value}, scope_name),
            ],
        )

    # Linked requirements
    linked_reqs = [
        entry for entry in traceability.entries if any(f"?{verif_name}" in v for v in entry.linked_verifications)
    ]
    if linked_reqs:
        req_items = [
            li[
                a(href=url_for_requirement(entry.requirement_id))[entry.requirement_id],
                f" - {entry.description}" if entry.description else None,
            ]
            for entry in linked_reqs
        ]
        sections.append(
            section(id="requirements")[
                h3["Satisfies Requirements"],
                ul[req_items],
            ],
        )

    return main(".content")[
        h2[code[f"?{verif_name}"]],
        sections,
    ]
