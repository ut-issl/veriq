"""Rich rendering utilities for graph query commands."""

from typing import TYPE_CHECKING

from rich.table import Table
from rich.tree import Tree

from veriq._ir import NodeKind
from veriq._path import format_for_display

if TYPE_CHECKING:
    from rich.console import Console

    from .graph_query import NodeDetail, NodeInfo, ScopeSummary, TreeNode


def render_scope_table(summaries: list[ScopeSummary], console: Console) -> None:
    """Render scope summaries as a Rich table.

    Args:
        summaries: List of ScopeSummary to render.
        console: Rich Console to output to.

    """
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Scope", style="bold")
    table.add_column("Models", justify="right")
    table.add_column("Calcs", justify="right")
    table.add_column("Verifications", justify="right")

    for summary in summaries:
        table.add_row(
            summary.name,
            str(summary.model_count),
            str(summary.calc_count),
            str(summary.verification_count),
        )

    console.print(table)


def render_node_table(nodes: list[NodeInfo], console: Console) -> None:
    """Render node list as a Rich table.

    Args:
        nodes: List of NodeInfo to render.
        console: Rich Console to output to.

    """
    if not nodes:
        console.print("[dim]No nodes match the given filters[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Path", style="dim")
    table.add_column("Kind")
    table.add_column("Deps", justify="right")

    for node in nodes:
        path_str = format_for_display(node.path, escape_markup=True)
        # Truncate long paths
        if len(path_str) > 60:
            path_str = path_str[:57] + "..."

        kind_style = _get_kind_style(node.kind)
        table.add_row(
            path_str,
            f"[{kind_style}]{node.kind.upper()}[/{kind_style}]",
            str(node.dependency_count),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(nodes)} nodes[/dim]")


def render_node_detail(detail: NodeDetail, console: Console) -> None:
    """Render detailed node information.

    Args:
        detail: NodeDetail to render.
        console: Rich Console to output to.

    """
    console.print(f"[bold]Node:[/bold] {format_for_display(detail.path, escape_markup=True)}")
    console.print()

    kind_style = _get_kind_style(detail.kind)
    console.print(f"[cyan]Kind:[/cyan]         [{kind_style}]{detail.kind.upper()}[/{kind_style}]")
    console.print(f"[cyan]Scope:[/cyan]        {detail.path.scope}")

    # Get type name
    type_name = format_for_display(detail.output_type, escape_markup=True)
    console.print(f"[cyan]Output Type:[/cyan]  {type_name}")
    console.print()

    # Dependencies
    if detail.direct_dependencies:
        console.print(f"[cyan]Dependencies ({len(detail.direct_dependencies)} direct):[/cyan]")
        deps_list = list(detail.direct_dependencies)
        deps_list.sort(key=str)
        for dep in deps_list:
            console.print(f"  {format_for_display(dep, escape_markup=True)}")
        console.print()
    else:
        console.print("[cyan]Dependencies:[/cyan] [dim]None[/dim]")
        console.print()

    # Dependents
    if detail.direct_dependents:
        console.print(f"[cyan]Dependents ({len(detail.direct_dependents)} direct):[/cyan]")
        dependents_list = list(detail.direct_dependents)
        dependents_list.sort(key=str)
        for dep in dependents_list:
            console.print(f"  {format_for_display(dep, escape_markup=True)}")
        console.print()
    else:
        console.print("[cyan]Dependents:[/cyan] [dim]None[/dim]")
        console.print()

    # Metadata
    if detail.metadata:
        console.print("[cyan]Metadata:[/cyan]")
        for key, value in detail.metadata.items():
            formatted_value = format_for_display(value, escape_markup=True)
            console.print(f"  {key}: {formatted_value}")


def render_tree(tree_node: TreeNode, console: Console) -> None:
    """Render a dependency tree using Rich Tree.

    Args:
        tree_node: TreeNode root to render.
        console: Rich Console to output to.

    """
    root_path = format_for_display(tree_node.path, escape_markup=True)
    rich_tree = Tree(f"[bold]{root_path}[/bold]")
    _add_tree_children(rich_tree, tree_node.children)
    console.print(rich_tree)


def _add_tree_children(parent: Tree, children: list[TreeNode]) -> None:
    """Recursively add children to a Rich Tree.

    Args:
        parent: Parent Tree node to add children to.
        children: List of TreeNode children.

    """
    for child in children:
        child_path = format_for_display(child.path, escape_markup=True)
        child_tree = parent.add(child_path)
        _add_tree_children(child_tree, child.children)


def _get_kind_style(kind: NodeKind) -> str:
    """Get Rich style string for a node kind.

    Args:
        kind: The NodeKind.

    Returns:
        Rich style string.

    """
    match kind:
        case NodeKind.MODEL:
            return "blue"
        case NodeKind.CALCULATION:
            return "green"
        case NodeKind.VERIFICATION:
            return "yellow"
