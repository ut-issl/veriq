"""URL resolution for multi-page static site export.

All URLs are root-relative (start with /) for GitHub Pages compatibility.

Structure:
    /index.html
    /scopes/index.html
    /scopes/{scope}/index.html
    /scopes/{scope}/calculations/{calc}.html
    /scopes/{scope}/verifications/{verif}.html
    /requirements/index.html
    /requirements/{id}.html
"""

from __future__ import annotations


def url_for_index() -> str:
    """URL for the landing page."""
    return "/index.html"


def url_for_scope_list() -> str:
    """URL for the scope listing page."""
    return "/scopes/index.html"


def url_for_scope(scope_name: str) -> str:
    """URL for a scope detail page."""
    return f"/scopes/{scope_name}/index.html"


def url_for_calc(scope_name: str, calc_name: str) -> str:
    """URL for a calculation detail page (under its scope)."""
    return f"/scopes/{scope_name}/calculations/{calc_name}.html"


def url_for_verification(scope_name: str, verif_name: str) -> str:
    """URL for a verification detail page (under its scope)."""
    return f"/scopes/{scope_name}/verifications/{verif_name}.html"


def url_for_requirement_list() -> str:
    """URL for the requirement listing page."""
    return "/requirements/index.html"


def url_for_requirement(req_id: str) -> str:
    """URL for a requirement detail page."""
    return f"/requirements/{req_id}.html"
