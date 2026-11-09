"""Rich rendering utilities for graph query commands."""

from typing import TYPE_CHECKING, Any

from rich.markup import escape
from rich.table import Table
from rich.tree import Tree

from veriq._ir import NodeKind
from veriq._path import format_for_display

if TYPE_CHECKING:
    from rich.console import Console

    from .graph_query import NodeDetail, NodeInfo, ScopeSummary, TreeNode
    from .upstream_query import UpstreamReport


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

    _render_metadata_section(console, "User Metadata", detail.user_metadata)
    _render_metadata_section(console, "Field Metadata", detail.field_metadata)


def _render_metadata_section(console: Console, title: str, metadata: dict[str, Any]) -> None:
    if not metadata:
        return
    console.print(f"[cyan]{title}:[/cyan]")
    for key, value in metadata.items():
        console.print(f"  {escape(str(key))}: {escape(repr(value))}")


def render_upstream_report(report: UpstreamReport, console: Console, *, show_bindings: bool = False) -> None:
    """Render the definition-level upstream report of a node.

    Args:
        report: The UpstreamReport to render.
        console: Rich Console to output to.
        show_bindings: Also list, per definition, which parameter reads which path.

    """
    sub = report.subgraph
    console.print(
        f"[bold]Upstream of {escape(str(sub.target))}[/bold] "
        f"[dim]({len(sub)} definitions, {len(sub.data_edges)} data edges, {len(sub.assume_edges)} assume edges)[/dim]",
    )
    console.print()
    _render_upstream_table(report, console)
    _render_upstream_aggregation(report, console)
    if show_bindings:
        _render_upstream_bindings(report, console)
    _render_upstream_inputs(report, console)


def _render_upstream_table(report: UpstreamReport, console: Console) -> None:
    sub = report.subgraph
    agg = report.aggregation
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Kind")
    table.add_column("Definition", style="bold")
    table.add_column("Inputs", justify="right")
    if agg is not None:
        table.add_column(escape(agg.key), justify="right")
        table.add_column(f"propagated ({agg.combine.value})", justify="right")

    for node_id in report.order:
        node = sub.nodes[node_id]
        kind_style = _get_kind_style(node.kind)
        n_inputs = len(sub.predecessors(node_id)) + len(sub.assumptions_of(node_id))
        label = escape(str(node_id)) + (" [dim](target)[/dim]" if node_id == sub.target else "")
        row = [f"[{kind_style}]{node.kind.upper()}[/{kind_style}]", label, str(n_inputs)]
        if agg is not None:
            row += [_fmt_num(agg.own[node_id]), _fmt_num(agg.propagated[node_id])]
        table.add_row(*row)
    console.print(table)


def _render_upstream_aggregation(report: UpstreamReport, console: Console) -> None:
    agg = report.aggregation
    propagated = report.propagated_at_target
    if agg is None or propagated is None:
        return
    console.print()
    console.print(f"[cyan]Sequential total of {escape(agg.key)} (each definition once):[/cyan] {_fmt_num(agg.total)}")
    note = " [dim](critical path)[/dim]" if agg.combine.value == "max" else ""
    console.print(f"[cyan]Propagated to target (combine={agg.combine.value}):[/cyan] {_fmt_num(propagated)}{note}")


def _render_upstream_bindings(report: UpstreamReport, console: Console) -> None:
    sub = report.subgraph
    console.print()
    console.print("[cyan]Bindings (parameter <- reference):[/cyan]")
    for node_id in report.order:
        bindings = sub.inputs_of(node_id)
        assumptions = sorted(sub.assumptions_of(node_id), key=str)
        if not bindings and not assumptions:
            continue
        console.print(f"  [bold]{escape(str(node_id))}[/bold]")
        for b in bindings:
            leaves = f" [dim]({len(b.leaves)} leaves)[/dim]" if len(b.leaves) != 1 else ""
            console.print(f"    {escape(b.param)} <- {escape(str(b.ref))}{leaves}")
        for assumed in assumptions:
            console.print(f"    [dim]assumes[/dim] {escape(str(assumed))}")


def _render_upstream_inputs(report: UpstreamReport, console: Console) -> None:
    console.print()
    console.print(f"[cyan]Inputs ({len(report.inputs)} root-model leaves):[/cyan]")
    for info in report.inputs:
        console.print(f"  {escape(str(info.path))}")
        for key, value in info.field_metadata.items():
            console.print(f"    [dim]field[/dim] {escape(str(key))}: {escape(repr(value))}")
        for key, value in info.provenance.items():
            console.print(f"    [dim]provenance[/dim] {escape(str(key))}: {escape(repr(value))}")
    if report.provenance_loaded and not any(info.provenance for info in report.inputs):
        console.print("  [dim]No provenance recorded for these inputs in the input file[/dim]")
    elif not report.provenance_loaded:
        console.print("  [dim]Pass -i/--input to include provenance from the input TOML[/dim]")


def _fmt_num(value: float) -> str:
    return f"{value:g}"


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
