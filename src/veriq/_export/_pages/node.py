"""Per-node pages for model, calculation, and verification tree nodes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from htpy import Element, a, code, h2, h3, li, main, p, section, ul

from veriq._export._components import children_table, format_part, render_value, status_badge
from veriq._export._layout import base_page, site_nav
from veriq._export._urls import (
    url_for_index,
    url_for_node,
    url_for_project_path,
    url_for_requirement,
    url_for_scope,
    url_for_scope_list,
)
from veriq._path import CalcPath, ModelPath, VerificationPath

if TYPE_CHECKING:
    from veriq._eval_engine._tree import PathNode
    from veriq._models import Project
    from veriq._traceability import TraceabilityReport


def render_node_page(
    project: Project,
    node: PathNode,
    traceability: TraceabilityReport,
    *,
    descriptions: dict[str, str] | None = None,
) -> str:
    """Render a page for any PathNode (leaf or non-leaf, any path type).

    Args:
        project: The project for context (scope names, etc.).
        node: The PathNode to render.
        traceability: Traceability report for requirement links.
        descriptions: Optional field descriptions (for model nodes).

    """
    scope_names = list(project.scopes.keys())
    scope_name = node.path.scope
    path = node.path.path

    return base_page(
        project_name=project.name,
        page_title=f"{path} - {scope_name} - {project.name}",
        sidebar=site_nav(scope_names=scope_names),
        content=_node_content(project, node, traceability, descriptions=descriptions),
        css_href="/styles.css",
        breadcrumbs=_build_breadcrumbs(node),
    )


def _build_breadcrumbs(node: PathNode) -> list[tuple[str, str]]:
    """Build breadcrumb trail for a node."""
    ppath = node.path
    scope_name = ppath.scope
    path = ppath.path

    crumbs: list[tuple[str, str]] = [
        ("Home", url_for_index()),
        ("Scopes", url_for_scope_list()),
        (scope_name, url_for_scope(scope_name)),
    ]

    # Type label breadcrumb
    if isinstance(path, ModelPath):
        type_label = "Model"
    elif isinstance(path, CalcPath):
        type_label = f"@{path.calc_name}"
    elif isinstance(path, VerificationPath):
        type_label = f"?{path.verification_name}"
    else:
        type_label = str(path.root)

    # For the root node, the type label IS the current page
    if not path.parts:
        crumbs.append((type_label, url_for_node(node)))
        return crumbs

    # Add root node breadcrumb (linked via ProjectPath URL)
    from veriq._path import ProjectPath  # noqa: PLC0415

    root_path = type(path)(root=path.root, parts=())
    root_ppath = ProjectPath(scope=scope_name, path=root_path)
    crumbs.append((type_label, url_for_project_path(root_ppath) or "#"))

    # Add intermediate path parts as breadcrumbs
    for i in range(len(path.parts)):
        part = path.parts[i]
        part_label = format_part(part)
        intermediate_parts = path.parts[: i + 1]
        intermediate_path = type(path)(root=path.root, parts=intermediate_parts)
        intermediate_ppath = ProjectPath(scope=scope_name, path=intermediate_path)

        if i < len(path.parts) - 1:
            crumbs.append((part_label, url_for_project_path(intermediate_ppath) or "#"))
        else:
            # Current node (last crumb)
            crumbs.append((part_label, url_for_node(node)))

    return crumbs


def _node_content(
    project: Project,
    node: PathNode,
    traceability: TraceabilityReport,
    *,
    descriptions: dict[str, str] | None = None,
) -> Element:
    """Render the main content of a node page."""
    ppath = node.path
    scope_name = ppath.scope
    path = ppath.path
    sections: list[Element] = []

    # Scope link
    sections.append(
        p["Scope: ", a(href=url_for_scope(scope_name))[scope_name]],
    )

    # Description (for model nodes from Pydantic field descriptions)
    if descriptions:
        path_str = str(path)
        desc = descriptions.get(path_str)
        if desc:
            sections.append(p(".description")[desc])

    # For calc/verif root nodes: show inputs
    if not path.parts and isinstance(path, (CalcPath, VerificationPath)):
        sections.extend(_render_inputs_section(project, scope_name, path))

    if node.is_leaf:
        sections.append(_render_leaf_section(node))
    else:
        sections.append(_render_children_section(node))

    # For verif root nodes: show linked requirements
    if not path.parts and isinstance(path, VerificationPath):
        sections.extend(_render_requirements_section(path, traceability))

    return main(".content")[
        h2[code[str(path)]],
        sections,
    ]


def _render_inputs_section(
    project: Project,
    scope_name: str,
    path: CalcPath | VerificationPath,
) -> list[Element]:
    """Render the inputs section for a calc/verif root node."""
    scope = project.scopes.get(scope_name)
    if scope is None:
        return []

    if isinstance(path, CalcPath):
        obj = scope.calculations.get(path.calc_name)
    else:
        obj = scope.verifications.get(path.verification_name)

    if obj is None or not hasattr(obj, "dep_ppaths") or not obj.dep_ppaths:
        return []

    dep_items = [_render_input_item(param_name, ppath) for param_name, ppath in obj.dep_ppaths.items()]
    return [
        section(id="inputs")[
            h3["Inputs"],
            ul[dep_items],
        ],
    ]


def _render_input_item(param_name: str, ppath: object) -> Element:
    """Render a single input reference, linked to its source page if possible."""
    from veriq._path import ProjectPath  # noqa: PLC0415

    if isinstance(ppath, ProjectPath):
        href = url_for_project_path(ppath)
        path_display = code[str(ppath)]
        linked_path = a(href=href)[path_display] if href else path_display
    else:
        linked_path = code[str(ppath)]
    return li[code[param_name], " \u2190 ", linked_path]


def _render_leaf_section(node: PathNode) -> Element:
    """Render the value section for a leaf node."""
    path = node.path.path
    value = node.value

    # Verification leaves get a status badge
    if isinstance(path, VerificationPath) and isinstance(value, bool):
        return section(id="value")[
            h3["Value"],
            p[status_badge(passed=value)],
        ]

    return section(id="value")[
        h3["Value"],
        p[render_value(value)],
    ]


def _render_children_section(node: PathNode) -> Element:
    """Render the children table for a non-leaf node."""
    return section(id="children")[
        h3["Children"],
        children_table(node.children),
    ]


def _render_requirements_section(
    path: VerificationPath,
    traceability: TraceabilityReport,
) -> list[Element]:
    """Render linked requirements for a verification root node."""
    verif_name = path.verification_name
    linked_reqs = [
        entry for entry in traceability.entries if any(f"?{verif_name}" in v for v in entry.linked_verifications)
    ]
    if not linked_reqs:
        return []

    req_items = [
        li[
            a(href=url_for_requirement(entry.requirement_id))[entry.requirement_id],
            f" - {entry.description}" if entry.description else None,
        ]
        for entry in linked_reqs
    ]
    return [
        section(id="requirements")[
            h3["Satisfies Requirements"],
            ul[req_items],
        ],
    ]
