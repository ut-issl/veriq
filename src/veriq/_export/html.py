"""HTML rendering for veriq export."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from htpy import (
    Element,
    Node,
    a,
    code,
    details,
    div,
    h2,
    h3,
    h4,
    h5,
    li,
    main,
    nav,
    section,
    small,
    span,
    strong,
    summary,
    ul,
)

from veriq._path import CalcPath, ModelPath, VerificationPath
from veriq._traceability import build_traceability_report

from ._components import (
    format_part,
    requirement_status_class,
    requirement_status_icon,
    values_table,
    verifications_table,
)
from ._layout import base_page

if TYPE_CHECKING:
    from pydantic import BaseModel

    from veriq._eval_engine import EvaluationResult
    from veriq._models import Project
    from veriq._traceability import RequirementTraceEntry, TraceabilityReport


def render_html(
    project: Project,
    model_data: dict[str, BaseModel],
    result: EvaluationResult,
) -> str:
    """Render evaluation results as an HTML document.

    Args:
        project: The project that was evaluated.
        model_data: Input model data by scope name.
        result: The evaluation result containing all computed values.

    Returns:
        Complete HTML document as a string.

    """
    traceability = build_traceability_report(project, result)
    scope_data = _group_results_by_scope(project, model_data, result)

    return base_page(
        project_name=project.name,
        sidebar=_render_sidebar(project, traceability),
        content=_render_main_content(project, scope_data, traceability),
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _render_sidebar(project: Project, _traceability: TraceabilityReport) -> Element:
    """Render navigation sidebar."""
    return nav(".sidebar")[
        h2["Navigation"],
        ul[
            li[
                a(href="#scopes")["Scopes"],
                ul[(li[a(href=f"#scope-{scope_name}")[scope_name]] for scope_name in project.scopes)],
            ],
            li[a(href="#requirements")["Requirements"]],
        ],
    ]


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------


def _render_main_content(
    project: Project,
    scope_data: dict[str, ScopeData],
    traceability: TraceabilityReport,
) -> Element:
    """Render main content area."""
    return main(".content")[
        section(id="scopes")[
            h2["Scopes"],
            [
                _render_scope_section(scope_name, scope, scope_data.get(scope_name))
                for scope_name, scope in project.scopes.items()
            ],
        ],
        _render_requirements_section(traceability),
    ]


def _render_scope_section(scope_name: str, _scope: Any, data: ScopeData | None) -> Element:
    """Render a single scope section."""
    return details(open=True, id=f"scope-{scope_name}")[
        summary[h3[scope_name]],
        div(".scope-content")[
            _render_model_section(data) if data and data.model_values else None,
            _render_calcs_section(scope_name, data) if data and data.calc_values else None,
            _render_verifs_section(scope_name, data) if data and data.verification_values else None,
        ],
    ]


def _render_model_section(data: ScopeData) -> Element:
    """Render model data section within a scope."""
    return div(".section")[
        h4["Model"],
        values_table(data.model_values, "model", data.model_descriptions),
    ]


def _render_calcs_section(scope_name: str, data: ScopeData | None) -> Element:
    """Render calculations section within a scope."""
    if data is None:
        return div(".section")[h4["Calculations"]]

    calc_blocks: list[Element] = []
    for calc_name, calc_outputs in data.calc_values.items():
        anchor_id = f"{scope_name}-calc-{calc_name}"
        calc_blocks.append(
            div(".calc-block", id=anchor_id)[
                h5[code[f"@{calc_name}"]],
                values_table(calc_outputs, anchor_id),
            ],
        )

    return div(".section")[
        h4["Calculations"],
        calc_blocks,
    ]


def _render_verifs_section(scope_name: str, data: ScopeData | None) -> Element:
    """Render verifications section within a scope."""
    if data is None:
        return div(".section")[h4["Verifications"]]

    return div(".section")[
        h4["Verifications"],
        verifications_table(data.verification_values, scope_name),
    ]


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


def _render_requirements_section(traceability: TraceabilityReport) -> Element:
    """Render the requirements traceability section."""
    return section(id="requirements")[
        h2["Requirements"],
        div(".summary-panel")[
            span[f"Total: {traceability.total_requirements}"],
            span(".status.pass")[f"Verified: {traceability.verified_count}"],
            span(".status.satisfied")[f"Satisfied: {traceability.satisfied_count}"],
            span(".status.fail")[f"Failed: {traceability.failed_count}"],
            span(".status.not-verified")[f"Not Verified: {traceability.not_verified_count}"],
        ],
        div(".requirements-tree")[_render_requirements_tree(traceability),],
    ]


def _render_requirements_tree(traceability: TraceabilityReport) -> Element:
    """Render requirements as a nested tree."""
    entries_by_id = {e.requirement_id: e for e in traceability.entries}
    root_entries = [e for e in traceability.entries if e.depth == 0]

    return ul(".req-tree")[(_render_requirement_node(entry, entries_by_id) for entry in root_entries)]


def _render_requirement_node(
    entry: RequirementTraceEntry,
    entries_by_id: dict[str, RequirementTraceEntry],
) -> Element:
    """Render a single requirement node with its children."""
    status_class = requirement_status_class(entry.status)
    status_icon_text = requirement_status_icon(entry.status)

    children_ul: Node = None
    if entry.child_ids:
        children_ul = ul(".req-children")[
            (
                _render_requirement_node(entries_by_id[child_id], entries_by_id)
                for child_id in entry.child_ids
                if child_id in entries_by_id
            )
        ]

    return li(class_=f"req-node {status_class}", id=f"req-{entry.requirement_id}")[
        details(open=True)[
            summary[
                span(".status-icon")[status_icon_text],
                " ",
                strong[entry.requirement_id],
                " " if entry.description else None,
                span(".req-desc")[f"- {entry.description}"] if entry.description else None,
            ],
            _render_verification_links(entry),
            _render_dependency_links(entry),
            children_ul,
        ],
    ]


def _render_verification_links(entry: RequirementTraceEntry) -> Node:
    """Render verification links for a requirement."""
    if not entry.linked_verifications:
        return None
    return div(".req-verifications")[
        small[
            "Verified by: ",
            _intersperse(
                ", ",
                [code[verif] for verif in entry.linked_verifications],
            ),
        ],
    ]


def _render_dependency_links(entry: RequirementTraceEntry) -> Node:
    """Render dependency links for a requirement."""
    if not entry.depends_on_ids:
        return None
    return div(".req-deps")[
        small[
            "Depends on: ",
            _intersperse(
                ", ",
                [a(href=f"#req-{dep_id}")[dep_id] for dep_id in entry.depends_on_ids],
            ),
        ],
    ]


def _intersperse(separator: str, items: list[Node]) -> list[Node]:
    """Intersperse a separator between items."""
    result: list[Node] = []
    for i, item in enumerate(items):
        if i > 0:
            result.append(separator)
        result.append(item)
    return result


# ---------------------------------------------------------------------------
# Data grouping (no HTML — pure data logic)
# ---------------------------------------------------------------------------


class ScopeData:
    """Container for scope-level data extracted from evaluation results."""

    def __init__(self) -> None:
        self.model_values: dict[str, Any] = {}
        self.model_descriptions: dict[str, str] = {}
        self.calc_values: dict[str, dict[str, Any]] = {}
        self.calc_descriptions: dict[str, dict[str, str]] = {}
        self.verification_values: dict[str, bool | dict[str, bool]] = {}


def _extract_field_descriptions(model: BaseModel, prefix: str = "$") -> dict[str, str]:
    """Extract field descriptions from a Pydantic model recursively.

    Args:
        model: The Pydantic model instance.
        prefix: The path prefix (e.g., "$" for root model).

    Returns:
        Dictionary mapping field paths to their descriptions.

    """
    descriptions: dict[str, str] = {}
    model_class = type(model)

    for field_name, field_info in model_class.model_fields.items():
        path = f"{prefix}.{field_name}"

        if field_info.description:
            descriptions[path] = field_info.description

        field_value = getattr(model, field_name, None)
        if field_value is not None and hasattr(field_value, "model_fields"):
            nested_descriptions = _extract_field_descriptions(field_value, path)
            descriptions.update(nested_descriptions)

    return descriptions


def _group_results_by_scope(  # noqa: C901, PLR0912
    project: Project,
    model_data: dict[str, BaseModel],
    result: EvaluationResult,
) -> dict[str, ScopeData]:
    """Group evaluation results by scope and type."""
    scope_data: dict[str, ScopeData] = {}

    for scope_name in project.scopes:
        scope_data[scope_name] = ScopeData()

    for scope_name, model in model_data.items():
        if scope_name in scope_data:
            scope_data[scope_name].model_descriptions = _extract_field_descriptions(model)

    for scope_name, scope_tree in result.scopes.items():
        if scope_name not in scope_data:
            scope_data[scope_name] = ScopeData()

        data = scope_data[scope_name]

        for node in scope_tree.iter_all_nodes():
            for leaf in node.iter_leaves():
                ppath = leaf.path
                value = leaf.value

                if isinstance(ppath.path, ModelPath):
                    path_str = str(ppath.path)
                    data.model_values[path_str] = value

                elif isinstance(ppath.path, CalcPath):
                    calc_name = ppath.path.calc_name
                    if calc_name not in data.calc_values:
                        data.calc_values[calc_name] = {}

                    if ppath.path.parts:
                        parts_str = "".join(format_part(p) for p in ppath.path.parts)
                        data.calc_values[calc_name][parts_str] = value
                    else:
                        data.calc_values[calc_name]["(output)"] = value

                elif isinstance(ppath.path, VerificationPath):
                    verif_name = ppath.path.verification_name
                    if ppath.path.parts:
                        if verif_name not in data.verification_values:
                            data.verification_values[verif_name] = {}
                        key_str = "".join(format_part(p) for p in ppath.path.parts)
                        data.verification_values[verif_name][key_str] = value  # type: ignore[index]
                    else:
                        data.verification_values[verif_name] = value

    return scope_data
