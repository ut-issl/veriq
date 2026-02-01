"""Calculation detail pages for multi-page static site export."""

from __future__ import annotations

from typing import TYPE_CHECKING

from htpy import Element, a, code, h2, h3, li, main, p, section, ul

from veriq._export._components import values_table
from veriq._export._layout import base_page, site_nav
from veriq._export._urls import url_for_calc, url_for_index, url_for_project_path, url_for_scope, url_for_scope_list

if TYPE_CHECKING:
    from veriq._export._data import ScopeData
    from veriq._models import Project
    from veriq._path import ProjectPath


def render_calc_detail_page(
    project: Project,
    scope_name: str,
    calc_name: str,
    data: ScopeData | None,
) -> str:
    """Render a calculation detail page."""
    scope_names = list(project.scopes.keys())
    scope = project.scopes[scope_name]
    calc = scope.calculations.get(calc_name)

    return base_page(
        project_name=project.name,
        page_title=f"@{calc_name} - {scope_name} - {project.name}",
        sidebar=site_nav(scope_names=scope_names),
        content=_calc_detail_content(scope_name, calc_name, calc, data),
        css_href="/styles.css",
        breadcrumbs=[
            ("Home", url_for_index()),
            ("Scopes", url_for_scope_list()),
            (scope_name, url_for_scope(scope_name)),
            (f"@{calc_name}", url_for_calc(scope_name, calc_name)),
        ],
    )


def _calc_detail_content(
    scope_name: str,
    calc_name: str,
    calc: object | None,
    data: ScopeData | None,
) -> Element:
    """Render the main content of a calculation detail page."""
    sections: list[Element] = []

    # Scope link
    sections.append(
        p["Scope: ", a(href=url_for_scope(scope_name))[scope_name]],
    )

    # Input references
    if calc is not None and hasattr(calc, "dep_ppaths") and calc.dep_ppaths:
        dep_items = [_render_input_item(param_name, ppath) for param_name, ppath in calc.dep_ppaths.items()]
        sections.append(
            section(id="inputs")[
                h3["Inputs"],
                ul[dep_items],
            ],
        )

    # Output values
    if data and calc_name in data.calc_values:
        outputs = data.calc_values[calc_name]
        anchor_id = f"{scope_name}-calc-{calc_name}"
        sections.append(
            section(id="outputs")[
                h3["Outputs"],
                values_table(outputs, anchor_id),
            ],
        )

    return main(".content")[
        h2[code[f"@{calc_name}"]],
        sections,
    ]


def _render_input_item(param_name: str, ppath: ProjectPath) -> Element:
    """Render a single input reference, linked to its source page if possible."""
    href = url_for_project_path(ppath)
    path_display = code[str(ppath)]
    linked_path = a(href=href)[path_display] if href else path_display
    return li[code[param_name], " \u2190 ", linked_path]
