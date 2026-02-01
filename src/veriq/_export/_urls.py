"""URL resolution for multi-page static site export.

All URLs are root-relative (start with /) for GitHub Pages compatibility.

Structure:
    /index.html
    /scopes/index.html
    /scopes/{scope}/index.html
    /scopes/{scope}/model/...                 (per-node pages for model)
    /scopes/{scope}/calculations/{calc}/...   (per-node pages for calculations)
    /scopes/{scope}/verifications/{verif}/... (per-node pages for verifications)
    /requirements/index.html
    /requirements/{id}.html
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from veriq._eval_engine._tree import PathNode
    from veriq._path import ProjectPath


def url_for_index() -> str:
    """URL for the landing page."""
    return "/index.html"


def url_for_scope_list() -> str:
    """URL for the scope listing page."""
    return "/scopes/index.html"


def url_for_scope(scope_name: str) -> str:
    """URL for a scope detail page."""
    return f"/scopes/{scope_name}/index.html"


def url_for_model_root(scope_name: str) -> str:
    """URL for the model root page of a scope."""
    return f"/scopes/{scope_name}/model/index.html"


def url_for_calc(scope_name: str, calc_name: str) -> str:
    """URL for a calculation root page (directory-style)."""
    return f"/scopes/{scope_name}/calculations/{calc_name}/index.html"


def url_for_verification(scope_name: str, verif_name: str) -> str:
    """URL for a verification root page (directory-style)."""
    return f"/scopes/{scope_name}/verifications/{verif_name}/index.html"


def url_for_requirement_list() -> str:
    """URL for the requirement listing page."""
    return "/requirements/index.html"


def url_for_requirement(req_id: str) -> str:
    """URL for a requirement detail page."""
    return f"/requirements/{req_id}.html"


def url_for_node(node: PathNode) -> str:
    """URL for any PathNode in the tree.

    All nodes use directory-style URLs (index.html) for consistency with
    url_for_project_path(), which cannot distinguish leaf from non-leaf nodes.

    Rules:
    - AttributePart("name") → directory segment `name/`
    - ItemPart("key") → directory segment `[key]/` (or `[a,b]/` for tuple keys)
    - All nodes → `index.html` inside their directory
    """
    from veriq._path import CalcPath, ModelPath, VerificationPath  # noqa: PLC0415

    ppath = node.path
    scope_name = ppath.scope
    path = ppath.path

    # Determine the base directory and root segment
    if isinstance(path, ModelPath):
        base = f"/scopes/{scope_name}/model"
    elif isinstance(path, CalcPath):
        base = f"/scopes/{scope_name}/calculations/{path.calc_name}"
    elif isinstance(path, VerificationPath):
        base = f"/scopes/{scope_name}/verifications/{path.verification_name}"
    else:
        msg = f"Unknown path type: {type(path)}"
        raise TypeError(msg)

    parts = path.parts

    if not parts:
        return f"{base}/index.html"

    segments = [_part_to_segment(part) for part in parts]
    return f"{base}/{'/'.join(segments)}/index.html"


def _part_to_segment(part: object) -> str:
    """Convert a path part to a URL segment."""
    from veriq._path import AttributePart, ItemPart  # noqa: PLC0415

    if isinstance(part, AttributePart):
        return part.name
    if isinstance(part, ItemPart):
        if isinstance(part.key, tuple):
            return f"[{','.join(str(k) for k in part.key)}]"
        return f"[{part.key}]"
    return str(part)


def url_for_project_path(ppath: ProjectPath) -> str | None:
    """URL for a ProjectPath, resolving to the precise per-node page.

    Maps:
    - ModelPath ($...) -> model node page
    - CalcPath (@calc_name...) -> calculation node page
    - VerificationPath (?verif_name...) -> verification node page
    """
    from veriq._path import CalcPath, ModelPath, VerificationPath  # noqa: PLC0415

    path = ppath.path
    scope_name = ppath.scope

    if isinstance(path, ModelPath):
        base = f"/scopes/{scope_name}/model"
    elif isinstance(path, CalcPath):
        base = f"/scopes/{scope_name}/calculations/{path.calc_name}"
    elif isinstance(path, VerificationPath):
        base = f"/scopes/{scope_name}/verifications/{path.verification_name}"
    else:
        return None

    parts = path.parts

    if not parts:
        return f"{base}/index.html"

    segments = [_part_to_segment(p) for p in parts]
    return f"{base}/{'/'.join(segments)}/index.html"
