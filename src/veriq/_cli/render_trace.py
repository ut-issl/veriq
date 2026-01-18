"""Rendering utilities for traceability reports.

This module provides functions to render traceability reports in various formats.
It separates presentation from business logic, enabling future format extensions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from veriq._traceability import RequirementStatus

if TYPE_CHECKING:
    from rich.console import Console

    from veriq._traceability import RequirementTraceEntry, TraceabilityReport


def _status_style(status: RequirementStatus) -> str:
    """Get Rich style for a requirement status."""
    match status:
        case RequirementStatus.VERIFIED:
            return "green"
        case RequirementStatus.SATISFIED:
            return "cyan"
        case RequirementStatus.FAILED:
            return "red"
        case RequirementStatus.NOT_VERIFIED:
            return "yellow"


def _status_symbol(status: RequirementStatus) -> str:
    """Get symbol for a requirement status."""
    match status:
        case RequirementStatus.VERIFIED:
            return "✓"
        case RequirementStatus.SATISFIED:
            return "○"
        case RequirementStatus.FAILED:
            return "✗"
        case RequirementStatus.NOT_VERIFIED:
            return "?"


def _format_status(entry: RequirementTraceEntry) -> str:
    """Format status with color and symbol."""
    style = _status_style(entry.status)
    symbol = _status_symbol(entry.status)
    status_text = f"[{style}]{symbol} {entry.status.upper()}[/{style}]"

    if entry.xfail and entry.status == RequirementStatus.FAILED:
        status_text += " [yellow](expected)[/yellow]"

    return status_text


def _format_linked_verifications(entry: RequirementTraceEntry) -> str:
    """Format linked verification names for display (without results)."""
    if not entry.linked_verifications:
        return "[dim]-[/dim]"
    return ", ".join(escape(name) for name in entry.linked_verifications)


def _format_verification_results(entry: RequirementTraceEntry) -> str:
    """Format verification results with pass/fail status for display."""
    if not entry.verification_results:
        return "[dim]-[/dim]"

    parts = []
    for result in entry.verification_results:
        name = result.verification_name
        if result.table_key is not None:
            if isinstance(result.table_key, tuple):
                key_str = ",".join(str(k) for k in result.table_key)
            else:
                key_str = str(result.table_key)
            name = f"{name}[{key_str}]"

        if result.passed:
            parts.append(f"[green]✓[/green] {escape(name)}")
        else:
            parts.append(f"[red]✗[/red] {escape(name)}")

    return ", ".join(parts)


def render_traceability_table(
    report: TraceabilityReport,
    console: Console,
    *,
    show_gaps_only: bool = False,
    has_evaluation: bool = False,
) -> None:
    """Render traceability report as a Rich table.

    Args:
        report: The traceability report to render.
        console: Rich console to print to.
        show_gaps_only: If True, only show requirements with NOT_VERIFIED status.
        has_evaluation: If True, show Status and Verifications columns.

    """
    # Filter entries if needed
    entries = report.entries
    if show_gaps_only:
        entries = tuple(e for e in entries if e.status == RequirementStatus.NOT_VERIFIED)

    if not entries:
        if show_gaps_only:
            console.print("[green]✓ No coverage gaps found[/green]")
        else:
            console.print("[dim]No requirements defined[/dim]")
        return

    # Create table
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Requirement", style="dim")
    table.add_column("Description")
    if has_evaluation:
        table.add_column("Status")
    table.add_column("Verifications")

    for entry in entries:
        # Indent requirement ID based on depth
        indent = "  " * entry.depth
        req_id = f"{indent}{escape(entry.requirement_id)}"

        # Truncate description if too long
        description = entry.description
        max_desc_len = 50
        if len(description) > max_desc_len:
            description = description[: max_desc_len - 3] + "..."

        if has_evaluation:
            table.add_row(
                req_id,
                escape(description),
                _format_status(entry),
                _format_verification_results(entry),
            )
        else:
            table.add_row(
                req_id,
                escape(description),
                _format_linked_verifications(entry),
            )

    console.print(table)


def render_traceability_summary(
    report: TraceabilityReport,
    console: Console,
    *,
    has_evaluation: bool = False,
) -> None:
    """Render summary statistics panel.

    Args:
        report: The traceability report to render.
        console: Rich console to print to.
        has_evaluation: If True, show status counts.

    """
    summary_lines = [f"Total requirements: {report.total_requirements}"]

    if has_evaluation:
        summary_lines.extend([
            f"[green]✓ Verified:[/green] {report.verified_count}",
            f"[cyan]○ Satisfied:[/cyan] {report.satisfied_count}",
            f"[red]✗ Failed:[/red] {report.failed_count}",
            f"[yellow]? Not verified:[/yellow] {report.not_verified_count}",
        ])

    console.print(Panel("\n".join(summary_lines), title="Summary", border_style="cyan"))


def render_traceability_tree(
    report: TraceabilityReport,
    console: Console,
) -> None:
    """Render traceability report as a tree structure.

    Args:
        report: The traceability report to render.
        console: Rich console to print to.

    """
    if not report.entries:
        console.print("[dim]No requirements defined[/dim]")
        return

    # Build tree structure
    tree = Tree(f"[bold]{report.project_name}[/bold]")

    # Track nodes by requirement ID for building tree
    nodes: dict[str, Tree] = {}

    # First pass: create all nodes
    for entry in report.entries:
        style = _status_style(entry.status)
        symbol = _status_symbol(entry.status)
        label = f"[{style}]{symbol}[/{style}] {escape(entry.requirement_id)}: {escape(entry.description[:40])}"
        if entry.xfail and entry.status == RequirementStatus.FAILED:
            label += " [yellow](expected)[/yellow]"
        nodes[entry.requirement_id] = Tree(label)

    # Second pass: build hierarchy
    root_entries = [e for e in report.entries if e.depth == 0]
    for entry in root_entries:
        tree.add(nodes[entry.requirement_id])
        _add_children_to_tree(entry, nodes, report.entries)

    console.print(tree)


def _add_children_to_tree(
    parent_entry: RequirementTraceEntry,
    nodes: dict[str, Tree],
    all_entries: tuple[RequirementTraceEntry, ...],
) -> None:
    """Recursively add children to tree nodes."""
    for child_id in parent_entry.child_ids:
        if child_id in nodes:
            nodes[parent_entry.requirement_id].add(nodes[child_id])
            # Find child entry and recurse
            for entry in all_entries:
                if entry.requirement_id == child_id:
                    _add_children_to_tree(entry, nodes, all_entries)
                    break
