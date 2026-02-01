"""Shared page layout for veriq HTML export."""

from __future__ import annotations

from htpy import Element, Node, a, body, div, h1, h2, head, header, html, li, link, meta, nav, p, style, title, ul
from markupsafe import Markup

from ._css import CSS


def base_page(  # noqa: PLR0913
    *,
    project_name: str,
    page_title: str | None = None,
    sidebar: Node = None,
    content: Node,
    css_href: str | None = None,
    breadcrumbs: list[tuple[str, str]] | None = None,
) -> str:
    """Render a full HTML page as a string.

    Args:
        project_name: The project name for the header.
        page_title: Optional page title override. Defaults to "{project_name} - veriq Report".
        sidebar: Optional sidebar navigation element.
        content: The main content node.
        css_href: If provided, link to external CSS instead of inline styles.
        breadcrumbs: Optional list of (label, href) for breadcrumb navigation.

    Returns:
        Complete HTML document as a string.

    """
    effective_title = page_title or f"{project_name} - veriq Report"

    page = html(lang="en")[
        _render_head(effective_title, css_href=css_href),
        body[
            _render_header(project_name),
            _render_breadcrumbs(breadcrumbs) if breadcrumbs else None,
            div(".container")[
                sidebar,
                content,
            ],
        ],
    ]
    return f"<!DOCTYPE html>\n{page}"


def site_nav(
    *,
    scope_names: list[str],
) -> Element:
    """Render a navigation sidebar for the multi-page site."""
    from ._urls import url_for_index, url_for_requirement_list, url_for_scope, url_for_scope_list  # noqa: PLC0415

    return nav(".sidebar")[
        h2["Navigation"],
        ul[
            li[a(href=url_for_index())["Home"]],
            li[
                a(href=url_for_scope_list())["Scopes"],
                ul[(li[a(href=url_for_scope(name))[name]] for name in scope_names),],
            ],
            li[a(href=url_for_requirement_list())["Requirements"]],
        ],
    ]


def _render_head(page_title: str, *, css_href: str | None = None) -> Element:
    """Render HTML <head> with inline or external CSS."""
    css_node: Node = link(rel="stylesheet", href=css_href) if css_href else style[Markup(CSS)]  # noqa: S704

    return head[
        meta(charset="UTF-8"),
        meta(name="viewport", content="width=device-width, initial-scale=1.0"),
        title[page_title],
        css_node,
    ]


def _render_header(project_name: str) -> Element:
    """Render the page header."""
    return header[
        h1[project_name],
        p(".subtitle")["veriq Evaluation Report"],
    ]


def _render_breadcrumbs(breadcrumbs: list[tuple[str, str]]) -> Element:
    """Render breadcrumb navigation."""
    items: list[Node] = []
    for i, (label, href) in enumerate(breadcrumbs):
        if i > 0:
            items.append(" / ")
        if i < len(breadcrumbs) - 1:
            items.append(a(href=href)[label])
        else:
            # Last item is current page, no link
            items.append(label)

    return nav(".breadcrumbs")[items]
