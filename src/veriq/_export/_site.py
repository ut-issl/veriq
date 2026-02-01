"""Multi-page static site generation orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from veriq._traceability import build_traceability_report

from ._css import CSS
from ._pages.calculation import render_calc_detail_page
from ._pages.index import render_index_page
from ._pages.requirement import render_requirement_detail_page, render_requirement_list_page
from ._pages.scope import render_scope_detail_page, render_scope_list_page
from ._pages.verification import render_verification_detail_page
from .html import _group_results_by_scope

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel

    from veriq._eval_engine import EvaluationResult
    from veriq._models import Project


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
    - scopes/: Scope listing, detail, calculation, and verification pages
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
    scope_data = _group_results_by_scope(project, model_data, result)

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

    # Scope pages (with nested calculation and verification pages)
    _write_file(
        output_dir / "scopes" / "index.html",
        render_scope_list_page(project, scope_data),
    )
    for scope_name, scope in project.scopes.items():
        data = scope_data.get(scope_name)
        scope_dir = output_dir / "scopes" / scope_name

        # Scope detail page
        _write_file(
            scope_dir / "index.html",
            render_scope_detail_page(project, scope_name, data, traceability),
        )

        # Calculation pages under scope
        for calc_name in scope.calculations:
            _write_file(
                scope_dir / "calculations" / f"{calc_name}.html",
                render_calc_detail_page(project, scope_name, calc_name, data),
            )

        # Verification pages under scope
        for verif_name in scope.verifications:
            _write_file(
                scope_dir / "verifications" / f"{verif_name}.html",
                render_verification_detail_page(project, scope_name, verif_name, data, traceability),
            )

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


def _write_file(path: Path, content: str) -> None:
    """Write content to a file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
