"""Export command for veriq CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

from veriq._eval import evaluate_project
from veriq._export import render_html
from veriq._io import load_model_data_from_toml

from .config import ConfigError, get_config
from .discover import load_project_from_module_path, load_project_from_script

if TYPE_CHECKING:
    from veriq._models import Project

# Console for stderr (info/errors)
err_console = Console(stderr=True)


def _load_project(
    path: str | None,
    config: object,
    project_var: str | None = None,
) -> Project:
    """Load project from CLI path or config."""
    if path is not None:
        if ":" in path:
            err_console.print(f"[cyan]Loading project from module:[/cyan] {path}")
            return load_project_from_module_path(path)
        script_path = Path(path)
        err_console.print(f"[cyan]Loading project from script:[/cyan] {script_path}")
        return load_project_from_script(script_path, project_var)

    # No CLI path - try config
    if not hasattr(config, "project") or config.project is None:
        msg = (
            "No project specified. Provide a path argument or configure "
            "[tool.veriq].project in pyproject.toml."
        )
        raise typer.BadParameter(msg)

    # Load from config
    from .config import ModuleSource, ScriptSource  # noqa: PLC0415

    match config.project:
        case ScriptSource(script=script, name=name):
            err_console.print(f"[cyan]Loading project from script:[/cyan] {script}")
            effective_name = project_var if project_var else name
            return load_project_from_script(script, effective_name)
        case ModuleSource(module_path=module_path):
            err_console.print(f"[cyan]Loading project from module:[/cyan] {module_path}")
            return load_project_from_module_path(module_path)

    msg = "Invalid project configuration"
    raise typer.BadParameter(msg)


def export_command(  # noqa: PLR0913
    path: Annotated[
        str | None,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
    *,
    input: Annotated[  # noqa: A002
        Path | None,
        typer.Option("-i", "--input", help="Path to input TOML file"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Path to output HTML file"),
    ] = None,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    serve: Annotated[
        bool,
        typer.Option("--serve", help="Start HTTP server after generating the report"),
    ] = False,
    port: Annotated[
        int,
        typer.Option("--port", help="Port for HTTP server (used with --serve)"),
    ] = 8000,
) -> None:
    """Export evaluation results as an interactive HTML report.

    Generates a self-contained HTML file with:
    - Model data, calculations, and verifications grouped by scope
    - Interactive Table display for multi-dimensional data
    - Requirement traceability tree with status indicators
    - Navigation sidebar with links to all sections
    """
    err_console.print()

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Resolve input/output from config if not provided
    effective_input = input if input is not None else config.input
    effective_output = output if output is not None else Path("report.html")

    if effective_input is None:
        err_console.print("[red]Error: Input file required. Use -i/--input or configure [tool.veriq].input[/red]")
        raise typer.Exit(code=1)

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Load model data
    err_console.print(f"[cyan]Loading input from:[/cyan] {effective_input}")
    model_data = load_model_data_from_toml(project, effective_input)

    # Evaluate the project
    err_console.print("[cyan]Evaluating project...[/cyan]")
    result = evaluate_project(project, model_data)
    err_console.print()

    # Generate HTML
    err_console.print("[cyan]Generating HTML report...[/cyan]")
    html_content = render_html(project, model_data, result)

    # Write to file
    err_console.print(f"[cyan]Writing report to:[/cyan] {effective_output}")
    effective_output.parent.mkdir(parents=True, exist_ok=True)
    effective_output.write_text(html_content)

    err_console.print()
    err_console.print("[green]✓ Export complete[/green]")
    err_console.print()

    # Serve if requested
    if serve:
        _serve_file(effective_output, port)

    raise typer.Exit(code=0)


def _serve_file(file_path: Path, port: int) -> None:
    """Start a simple HTTP server to serve the HTML file."""
    import http.server  # noqa: PLC0415
    import socketserver  # noqa: PLC0415
    import webbrowser  # noqa: PLC0415
    from functools import partial  # noqa: PLC0415

    directory = file_path.parent
    filename = file_path.name

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))

    url = f"http://localhost:{port}/{filename}"
    err_console.print(f"[cyan]Starting server at:[/cyan] {url}")
    err_console.print("[dim]Press Ctrl+C to stop[/dim]")
    err_console.print()

    # Open browser
    webbrowser.open(url)

    with socketserver.TCPServer(("", port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            err_console.print()
            err_console.print("[dim]Server stopped[/dim]")
