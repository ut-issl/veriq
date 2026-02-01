"""Multi-page static site generation orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from veriq._traceability import build_traceability_report

from ._css import CSS
from ._data import group_results_by_scope
from ._pages.index import render_index_page
from ._pages.node import render_node_page
from ._pages.requirement import render_requirement_detail_page, render_requirement_list_page
from ._pages.scope import render_scope_detail_page, render_scope_list_page
from ._urls import url_for_node

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel

    from veriq._eval_engine import EvaluationResult
    from veriq._eval_engine._tree import PathNode
    from veriq._models import Project
    from veriq._traceability import TraceabilityReport


def generate_site(
    project: Project,
    model_data: dict[str, BaseModel],
    result: EvaluationResult,
    output_dir: Path,
) -> None:
    """Generate a multi-page static site from evaluation results.

    Creates a directory structure with:
    - index.html: Landing page with project overview and summary
    - styles.css: Shared CSS stylesheet
    - scopes/: Scope listing, detail, and per-node pages
    - requirements/: Requirement listing and detail pages
    - .nojekyll: Marker file for GitHub Pages compatibility

    Args:
        project: The project that was evaluated.
        model_data: Input model data by scope name.
        result: The evaluation result containing all computed values.
        output_dir: Directory to write the site into. Created if it doesn't exist.

    """
    # Prepare shared data
    traceability = build_traceability_report(project, result)
    scope_data = group_results_by_scope(project, model_data, result)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write shared CSS
    _write_file(output_dir / "styles.css", CSS)

    # Write .nojekyll for GitHub Pages
    _write_file(output_dir / ".nojekyll", "")

    # Generate pages
    _write_file(
        output_dir / "index.html",
        render_index_page(project, scope_data, traceability),
    )

    # Scope pages (with nested per-node pages)
    _write_file(
        output_dir / "scopes" / "index.html",
        render_scope_list_page(project, scope_data),
    )

    # Extract field descriptions for model nodes
    from veriq._export._data import _extract_field_descriptions  # noqa: PLC0415

    for scope_name in project.scopes:
        data = scope_data.get(scope_name)
        scope_dir = output_dir / "scopes" / scope_name

        # Scope detail page
        _write_file(
            scope_dir / "index.html",
            render_scope_detail_page(project, scope_name, data, traceability),
        )

        # Build field descriptions for model nodes
        model_descriptions: dict[str, str] = {}
        if scope_name in model_data:
            model_descriptions = _extract_field_descriptions(model_data[scope_name])

        # Generate per-node pages
        scope_tree = result.scopes.get(scope_name)

        if scope_tree is not None and scope_tree.model is not None:
            _generate_node_pages(
                output_dir,
                project,
                scope_tree.model,
                traceability,
                descriptions=model_descriptions,
            )
        elif scope_name in model_data:
            # Scope has a registered root model but it's empty (no fields/leaves).
            # Generate a model root page so cross-scope links don't 404.
            _generate_empty_model_root_page(
                output_dir,
                project,
                scope_name,
                traceability,
                descriptions=model_descriptions,
            )

        if scope_tree is not None:
            for calc_node in scope_tree.calculations:
                _generate_node_pages(output_dir, project, calc_node, traceability)
            for verif_node in scope_tree.verifications:
                _generate_node_pages(output_dir, project, verif_node, traceability)

    # Requirement pages
    _write_file(
        output_dir / "requirements" / "index.html",
        render_requirement_list_page(project, traceability),
    )
    for entry in traceability.entries:
        _write_file(
            output_dir / "requirements" / f"{entry.requirement_id}.html",
            render_requirement_detail_page(project, entry, traceability),
        )


def _generate_empty_model_root_page(
    output_dir: Path,
    project: Project,
    scope_name: str,
    traceability: TraceabilityReport,
    *,
    descriptions: dict[str, str] | None = None,
) -> None:
    """Generate a model root page for a scope with an empty model (no fields)."""
    from veriq._eval_engine._tree import PathNode  # noqa: PLC0415
    from veriq._path import ModelPath, ProjectPath  # noqa: PLC0415

    empty_model_node = PathNode(
        path=ProjectPath(scope=scope_name, path=ModelPath(root="$", parts=())),
    )
    file_path = output_dir / "scopes" / scope_name / "model" / "index.html"
    _write_file(
        file_path,
        render_node_page(project, empty_model_node, traceability, descriptions=descriptions),
    )


def _generate_node_pages(
    output_dir: Path,
    project: Project,
    node: PathNode | None,
    traceability: TraceabilityReport,
    *,
    descriptions: dict[str, str] | None = None,
) -> None:
    """Recursively generate pages for a node and all its descendants."""
    if node is None:
        return

    # Map node URL to filesystem path
    node_url = url_for_node(node)
    # URL starts with /, strip it to get relative path
    file_path = output_dir / node_url.lstrip("/")

    _write_file(
        file_path,
        render_node_page(project, node, traceability, descriptions=descriptions),
    )

    # Recurse into children
    for child in node.children:
        _generate_node_pages(output_dir, project, child, traceability, descriptions=descriptions)


def _write_file(path: Path, content: str) -> None:
    """Write content to a file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
