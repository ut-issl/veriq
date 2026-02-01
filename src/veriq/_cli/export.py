"""Export command for veriq CLI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console

from veriq._eval import evaluate_project
from veriq._export import generate_site, render_html
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
        msg = "No project specified. Provide a path argument or configure [tool.veriq].project in pyproject.toml."
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
        typer.Option("-o", "--output", help="Path to output file or directory"),
    ] = None,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    site: Annotated[
        bool,
        typer.Option("--site", help="Generate a multi-page static site (output is a directory)"),
    ] = False,
    serve: Annotated[
        bool,
        typer.Option("--serve", help="Start HTTP server after generating the report"),
    ] = False,
    port: Annotated[
        int,
        typer.Option("--port", help="Port for HTTP server (used with --serve)"),
    ] = 8000,
) -> None:
    """Export evaluation results as an HTML report.

    By default, generates a single self-contained HTML file.
    With --site, generates a multi-page static site in a directory.

    Examples:
        veriq export -o report.html          # Single-page HTML
        veriq export --site -o report/       # Multi-page site
        veriq export --site --serve          # Generate and serve locally

    """
    err_console.print()

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Resolve input from config if not provided
    effective_input = input if input is not None else config.input

    if effective_input is None:
        err_console.print("[red]Error: Input file required. Use -i/--input or configure [tool.veriq].input[/red]")
        raise typer.Exit(code=1)

    # Resolve output: default depends on mode
    if site:
        effective_output = output if output is not None else Path("report")
    else:
        effective_output = output if output is not None else Path("report.html")

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

    if site:
        # Multi-page static site
        err_console.print("[cyan]Generating static site...[/cyan]")
        generate_site(project, model_data, result, effective_output)
        err_console.print(f"[cyan]Site written to:[/cyan] {effective_output}/")
    else:
        # Single-page HTML
        err_console.print("[cyan]Generating HTML report...[/cyan]")
        html_content = render_html(project, model_data, result)
        err_console.print(f"[cyan]Writing report to:[/cyan] {effective_output}")
        effective_output.parent.mkdir(parents=True, exist_ok=True)
        effective_output.write_text(html_content)

    err_console.print()
    err_console.print("[green]✓ Export complete[/green]")
    err_console.print()

    # Serve if requested
    if serve:
        serve_path = effective_output if site else effective_output.parent
        serve_index = "index.html" if site else effective_output.name
        _serve_directory(serve_path, serve_index, port)

    raise typer.Exit(code=0)


def _serve_directory(directory: Path, index_file: str, port: int) -> None:
    """Start a simple HTTP server to serve HTML files from a directory."""
    import http.server  # noqa: PLC0415
    import socketserver  # noqa: PLC0415
    import webbrowser  # noqa: PLC0415
    from functools import partial  # noqa: PLC0415

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))

    url = f"http://localhost:{port}/{index_file}"
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
