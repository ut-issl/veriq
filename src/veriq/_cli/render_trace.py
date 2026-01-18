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
    return "\n".join(escape(name) for name in entry.linked_verifications)


def _format_verification_results(entry: RequirementTraceEntry) -> str:
    """Format verification results with pass/fail status for display."""
    if not entry.verification_results:
        return "[dim]-[/dim]"

    parts = []
    for result in entry.verification_results:
        # Format as Scope::?verification_name
        name = f"{result.scope_name}::?{result.verification_name}"
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

    return "\n".join(parts)


def _build_tree_prefixes(
    entries: tuple[RequirementTraceEntry, ...],
    index: int,
) -> tuple[str, str]:
    """Build tree prefixes with unicode box-drawing characters.

    Args:
        entries: All entries in the report.
        index: Index of the current entry.

    Returns:
        Tuple of (first_line_prefix, continuation_prefix).
        First line uses ├── or └──, continuation uses │ or spaces.

    """
    entry = entries[index]
    if entry.depth == 0:
        return "", ""

    # Build prefix from left to right for each depth level
    first_line_parts: list[str] = []
    continuation_parts: list[str] = []

    for level in range(1, entry.depth + 1):
        if level == entry.depth:
            # Current level: determine if this is the last sibling
            is_last = True
            for future_idx in range(index + 1, len(entries)):
                future_entry = entries[future_idx]
                if future_entry.depth < level:
                    # Exited to a shallower level, so this was the last at this level
                    break
                if future_entry.depth == level:
                    # Found another sibling at the same level
                    is_last = False
                    break
            first_line_parts.append("└── " if is_last else "├── ")
            # Continuation: if last sibling, use spaces; otherwise use vertical line
            continuation_parts.append("    " if is_last else "│   ")
        else:
            # Ancestor level: check if there are more siblings at this level after current entry
            has_more_at_level = False
            for future_idx in range(index + 1, len(entries)):
                future_entry = entries[future_idx]
                if future_entry.depth < level:
                    # Exited to shallower level
                    break
                if future_entry.depth == level:
                    # Found a sibling at this ancestor level
                    has_more_at_level = True
                    break
            first_line_parts.append("│   " if has_more_at_level else "    ")
            continuation_parts.append("│   " if has_more_at_level else "    ")

    return "".join(first_line_parts), "".join(continuation_parts)


def render_traceability_table(
    report: TraceabilityReport,
    console: Console,
    *,
    has_evaluation: bool = False,
) -> None:
    """Render traceability report as a Rich table.

    Args:
        report: The traceability report to render.
        console: Rich console to print to.
        has_evaluation: If True, show Status and Verifications columns.

    """
    entries = report.entries

    if not entries:
        console.print("[dim]No requirements defined[/dim]")
        return

    # Create table
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Requirement", style="dim", no_wrap=True)
    table.add_column("Description")
    if has_evaluation:
        table.add_column("Status", no_wrap=True)
    table.add_column("Verifications", no_wrap=True)

    for i, entry in enumerate(entries):
        # Build tree prefixes with unicode symbols
        first_prefix, cont_prefix = _build_tree_prefixes(entries, i)

        # Get verification content (may be multi-line)
        if has_evaluation:
            verif_content = _format_verification_results(entry)
        else:
            verif_content = _format_linked_verifications(entry)

        # Count lines in verification content to build matching requirement column
        verif_lines = verif_content.count("\n") + 1

        # Build requirement column with continuation prefixes for multi-line rows
        req_first_line = f"{first_prefix}{escape(entry.requirement_id)}"
        if verif_lines > 1:
            req_id = req_first_line + "\n" + "\n".join([cont_prefix] * (verif_lines - 1))
        else:
            req_id = req_first_line

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
                verif_content,
            )
        else:
            table.add_row(
                req_id,
                escape(description),
                verif_content,
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
