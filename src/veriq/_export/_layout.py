"""Shared page layout for veriq HTML export."""

from __future__ import annotations

from htpy import Element, Node, body, div, h1, head, header, html, meta, p, style, title
from markupsafe import Markup

from ._css import CSS


def base_page(
    *,
    project_name: str,
    page_title: str | None = None,
    sidebar: Node = None,
    content: Node,
) -> str:
    """Render a full HTML page as a string.

    Args:
        project_name: The project name for the header.
        page_title: Optional page title override. Defaults to "{project_name} - veriq Report".
        sidebar: Optional sidebar navigation element.
        content: The main content node.

    Returns:
        Complete HTML document as a string.

    """
    effective_title = page_title or f"{project_name} - veriq Report"

    page = html(lang="en")[
        _render_head(effective_title),
        body[
            _render_header(project_name),
            div(".container")[
                sidebar,
                content,
            ],
        ],
    ]
    return f"<!DOCTYPE html>\n{page}"


def _render_head(page_title: str) -> Element:
    """Render HTML <head> with inline CSS."""
    return head[
        meta(charset="UTF-8"),
        meta(name="viewport", content="width=device-width, initial-scale=1.0"),
        title[page_title],
        style[Markup(CSS)],  # noqa: S704 - CSS is a static constant, not user input
    ]


def _render_header(project_name: str) -> Element:
    """Render the page header."""
    return header[
        h1[project_name],
        p(".subtitle")["veriq Evaluation Report"],
    ]
