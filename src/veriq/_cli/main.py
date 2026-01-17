import importlib
import io
import json
import logging
import sys
import tomllib
from pathlib import Path
from typing import Annotated

import tomli_w
import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from veriq._default import default
from veriq._eval import evaluate_project
from veriq._external_data import validate_external_data
from veriq._io import export_to_toml, load_model_data_from_toml
from veriq._ir import build_graph_spec
from veriq._models import Project
from veriq._path import VerificationPath
from veriq._update import update_input_data

from .discover import get_module_data_from_path

app = typer.Typer()

logger = logging.getLogger(__name__)
# Console for stderr (info/errors)
err_console = Console(stderr=True)
# Console for stdout (results)
out_console = Console()


@app.callback()
def callback(
    *,
    verbose: bool = typer.Option(default=False, help="Enable verbose output"),
) -> None:
    """Veriq CLI."""
    log_level = logging.DEBUG if verbose else logging.INFO

    # Configure rich logging handler to output to stderr
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[
            RichHandler(
                console=err_console,
                show_time=False,
                show_path=verbose,
                rich_tracebacks=True,
            ),
        ],
    )


def _load_project_from_script(script_path: Path, project_name: str | None = None) -> Project:
    """Load a project from a Python script path.

    Args:
        script_path: Path to the Python script containing the project
        project_name: Name of the project variable. If None, infers from the script

    Returns:
        The loaded Project instance

    """
    module_data = get_module_data_from_path(script_path)
    sys.path.insert(0, str(module_data.extra_sys_path))

    try:
        module = importlib.import_module(module_data.module_import_str)
    except (ImportError, ValueError):
        logger.exception("Import error")
        logger.warning("Ensure all the package directories have an __init__.py file")
        raise

    if project_name:
        if not hasattr(module, project_name):
            msg = f"Could not find project '{project_name}' in {module_data.module_import_str}"
            raise ValueError(msg)
        project = getattr(module, project_name)
        if not isinstance(project, Project):
            msg = f"'{project_name}' in {module_data.module_import_str} is not a Project instance"
            raise TypeError(msg)
        return project

    # Infer project from module
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, Project):
            logger.debug(f"Found project: {name}")
            return obj

    msg = "Could not find Project in module, try using --project"
    raise ValueError(msg)


def _load_project_from_module_path(module_path: str) -> Project:
    """Load a project from a module path (e.g., 'examples.dummysat:project').

    Args:
        module_path: Module path in format 'module.path:variable_name'

    Returns:
        The loaded Project instance

    """
    if ":" not in module_path:
        msg = "Module path must be in format 'module.path:variable_name'"
        raise ValueError(msg)

    module_name, project_name = module_path.split(":", 1)
    module = importlib.import_module(module_name)
    project = getattr(module, project_name)

    if not isinstance(project, Project):
        msg = f"'{project_name}' in module '{module_name}' is not a Project instance"
        raise TypeError(msg)

    return project


@app.command()
def calc(  # noqa: C901, PLR0912, PLR0915
    path: Annotated[
        str,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ],
    *,
    input: Annotated[  # noqa: A002
        Path,
        typer.Option("-i", "--input", help="Path to input TOML file"),
    ],
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="Path to output TOML file"),
    ],
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    verify: Annotated[
        bool,
        typer.Option("--verify", help="Verify that all verifications pass (exit non-zero if any fail)"),
    ] = False,
) -> None:
    """Perform calculations on a project and export results."""
    err_console.print()

    # Load the project
    if ":" in path:
        # Module path format
        err_console.print(f"[cyan]Loading project from module:[/cyan] {path}")
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        err_console.print(f"[cyan]Loading project from script:[/cyan] {script_path}")
        project = _load_project_from_script(script_path, project_var)

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Load model data
    err_console.print(f"[cyan]Loading input from:[/cyan] {input}")
    model_data = load_model_data_from_toml(project, input)

    # Validate external data checksums
    validation_result = validate_external_data(model_data)
    if validation_result.entries:
        err_console.print("[cyan]Validating external data checksums...[/cyan]")

        # Report new checksums (first run)
        if validation_result.has_new_checksums:
            err_console.print()
            err_console.print("[yellow]⚠ New external data references detected (no stored checksum):[/yellow]")
            for entry in validation_result.new_entries:
                err_console.print(f"  [yellow]•[/yellow] {entry.scope}::{entry.path}")
                err_console.print(f"    [dim]Computed: {entry.computed_checksum}[/dim]")
            err_console.print()
            err_console.print("[yellow]  Add checksums to your input TOML to track data changes.[/yellow]")

        # Report and abort on mismatches
        if validation_result.has_mismatches:
            err_console.print()
            err_console.print("[red]✗ External data checksum mismatch detected:[/red]")
            for entry in validation_result.mismatched_entries:
                err_console.print(f"  [red]•[/red] {entry.scope}::{entry.path}")
                err_console.print(f"    [dim]Stored:   {entry.stored_checksum}[/dim]")
                err_console.print(f"    [dim]Computed: {entry.computed_checksum}[/dim]")
            err_console.print()
            err_console.print("[red]  External data has changed since last run. Update checksums to continue.[/red]")
            raise typer.Exit(code=1)

        # Report valid checksums
        if validation_result.valid_entries:
            n_valid = len(validation_result.valid_entries)
            err_console.print(f"[green]✓ {n_valid} external data checksum(s) verified[/green]")

        err_console.print()

    # Evaluate the project
    err_console.print("[cyan]Evaluating project...[/cyan]")
    results = evaluate_project(project, model_data)
    err_console.print()

    # Check verifications if requested
    exit_as_err = False
    if verify:
        verification_results: list[tuple[str, bool, bool]] = []

        for ppath, value in results.items():
            if isinstance(ppath.path, VerificationPath):
                verification_name = ppath.path.verification_name
                scope_name = ppath.scope
                scope = project.scopes[scope_name]
                verification = scope.verifications[verification_name]
                # Build display name including path parts for Table[K, bool] verifications
                display_name = f"{scope_name}::?{verification_name}"
                if ppath.path.parts:
                    display_name += str(ppath.path)[len(f"?{verification_name}") :]
                verification_results.append((display_name, value, verification.xfail))
                if (not value) ^ verification.xfail:
                    exit_as_err = True

        # Create a table for verification results
        if verification_results:
            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("Verification", style="dim")
            table.add_column("Result")

            for verif_name, passed, xfail in verification_results:
                # Escape markup characters in verification name to display literally
                escaped_verif_name = escape(verif_name)
                status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
                if xfail and not passed:
                    status += " [yellow](expected failure)[/yellow]"
                elif xfail and passed:
                    status += " [red](unexpected pass)[/red]"
                table.add_row(escaped_verif_name, status)

            err_console.print(Panel(table, title="[bold]Verification Results[/bold]", border_style="cyan"))
            err_console.print()

        if any(not passed for _, passed, _ in verification_results):
            err_console.print("[red]✗ Some verifications failed[/red]")

    # Export results
    err_console.print(f"[cyan]Exporting results to:[/cyan] {output}")
    export_to_toml(project, model_data, results, output)

    err_console.print()
    err_console.print("[green]✓ Calculation complete[/green]")
    err_console.print()

    if exit_as_err:
        raise typer.Exit(code=1)

    raise typer.Exit(code=0)


@app.command()
def check(
    path: Annotated[
        str,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ],
    *,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
) -> None:
    """Check the validity of a project without performing calculations."""
    err_console.print()

    # Load the project
    if ":" in path:
        # Module path format
        err_console.print(f"[cyan]Loading project from module:[/cyan] {path}")
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        err_console.print(f"[cyan]Loading project from script:[/cyan] {script_path}")
        project = _load_project_from_script(script_path, project_var)

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Check if building the graph spec raises any errors
    err_console.print("[cyan]Validating dependencies...[/cyan]")
    build_graph_spec(project)
    err_console.print()

    # Create a table for project information
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Scope", style="bold")
    table.add_column("Calculations", justify="right", style="yellow")
    table.add_column("Verifications", justify="right", style="green")

    for scope_name, scope in project.scopes.items():
        num_calcs = len(scope.calculations)
        num_verifs = len(scope.verifications)
        table.add_row(scope_name, str(num_calcs), str(num_verifs))

    err_console.print(
        Panel(
            table,
            title=f"[bold]Project: {project.name}[/bold]",
            subtitle=f"[dim]{len(project.scopes)} scopes[/dim]",
            border_style="cyan",
        ),
    )

    err_console.print()
    err_console.print("[green]✓ Project is valid[/green]")
    err_console.print()


@app.command()
def schema(
    path: Annotated[
        str,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ],
    *,
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="Path to output JSON schema file"),
    ],
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    indent: Annotated[
        int,
        typer.Option("--indent", help="JSON indentation spaces"),
    ] = 2,
) -> None:
    """Generate JSON schema for the project input model."""
    err_console.print()

    # Load the project
    if ":" in path:
        # Module path format
        err_console.print(f"[cyan]Loading project from module:[/cyan] {path}")
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        err_console.print(f"[cyan]Loading project from script:[/cyan] {script_path}")
        project = _load_project_from_script(script_path, project_var)

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Generate input model schema
    err_console.print("[cyan]Generating input model JSON schema...[/cyan]")
    input_model = project.input_model()
    json_schema = input_model.model_json_schema()

    # Write to file
    err_console.print(f"[cyan]Writing schema to:[/cyan] {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as f:
        json.dump(json_schema, f, indent=indent)

    err_console.print()
    err_console.print("[green]✓ Schema generation complete[/green]")
    err_console.print()


@app.command()
def init(
    path: Annotated[
        str,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ],
    *,
    output: Annotated[
        Path,
        typer.Option("-o", "--output", help="Path to output TOML file"),
    ],
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
) -> None:
    """Generate a sample input TOML file with default values."""
    err_console.print()

    # Load the project
    if ":" in path:
        # Module path format
        err_console.print(f"[cyan]Loading project from module:[/cyan] {path}")
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        err_console.print(f"[cyan]Loading project from script:[/cyan] {script_path}")
        project = _load_project_from_script(script_path, project_var)

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Generate default input data
    err_console.print("[cyan]Generating default input data...[/cyan]")
    input_data_model = project.input_model()
    input_default_data = default(input_data_model)

    # Write to TOML file
    err_console.print(f"[cyan]Writing sample input to:[/cyan] {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("wb") as f:
        tomli_w.dump(input_default_data.model_dump(), f)

    err_console.print()
    err_console.print("[green]✓ Sample input file generated[/green]")
    err_console.print()


@app.command()
def update(  # noqa: PLR0913, PLR0915
    path: Annotated[
        str,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ],
    *,
    input: Annotated[  # noqa: A002
        Path,
        typer.Option("-i", "--input", help="Path to existing input TOML file"),
    ],
    output: Annotated[
        Path | None,
        typer.Option("-o", "--output", help="Path to output TOML file (defaults to input file)"),
    ] = None,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview changes without writing to file"),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("-y", "--yes", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Update an existing input TOML file with new schema defaults.

    This command intelligently merges your existing input file with the current
    project schema. It preserves all your existing values while adding new fields
    with default values and warning about removed fields.
    """
    # Default output to input if not specified
    if output is None:
        output = input

    err_console.print()

    # Load the project
    if ":" in path:
        # Module path format
        err_console.print(f"[cyan]Loading project from module:[/cyan] {path}")
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        err_console.print(f"[cyan]Loading project from script:[/cyan] {script_path}")
        project = _load_project_from_script(script_path, project_var)

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Load existing input file
    err_console.print(f"[cyan]Loading existing input from:[/cyan] {input}")
    with input.open("rb") as f:
        existing_data = tomllib.load(f)

    # Generate new default data from current schema
    err_console.print("[cyan]Generating defaults from current schema...[/cyan]")
    project_input_model = project.input_model()
    new_default_data = default(project_input_model)

    # Perform the update (functional core)
    err_console.print("[cyan]Merging existing data with new defaults...[/cyan]")
    result = update_input_data(new_default_data.model_dump(), existing_data)

    # Display warnings if any
    if result.warnings:
        err_console.print()
        err_console.print("[yellow]⚠ Warnings:[/yellow]")
        for warning in result.warnings:
            err_console.print(f"  [yellow]•[/yellow] {warning.message}")
        err_console.print()

    # Preview or write
    if dry_run:
        err_console.print("[yellow]🔍 Dry run - no files will be modified[/yellow]")
        err_console.print()
        err_console.print("[cyan]Preview of updated data:[/cyan]")

        # Show a preview using TOML format
        preview_buffer = io.BytesIO()
        tomli_w.dump(result.updated_data, preview_buffer)
        preview_text = preview_buffer.getvalue().decode("utf-8")

        # Display first 50 lines
        max_preview_lines = 50
        lines = preview_text.split("\n")
        if len(lines) > max_preview_lines:
            err_console.print("\n".join(lines[:max_preview_lines]))
            err_console.print(f"\n[dim]... ({len(lines) - max_preview_lines} more lines)[/dim]")
        else:
            err_console.print(preview_text)

        err_console.print()
        err_console.print("[yellow]i Run without --dry-run to write changes[/yellow]")
    else:
        # Confirm before writing (comments will be lost)
        if not yes:
            err_console.print()
            err_console.print(
                "[yellow]Warning: TOML comments in the input file will NOT be preserved.[/yellow]",
            )
            typer.confirm("Do you want to continue?", abort=True)

        # Write the updated data
        err_console.print(f"[cyan]Writing updated input to:[/cyan] {output}")
        output.parent.mkdir(parents=True, exist_ok=True)

        with output.open("wb") as f:
            tomli_w.dump(result.updated_data, f)

        err_console.print()
        err_console.print("[green]✓ Input file updated successfully[/green]")

    err_console.print()


@app.command()
def diff(
    file1: Annotated[
        Path,
        typer.Argument(help="Path to the first TOML file"),
    ],
    file2: Annotated[
        Path,
        typer.Argument(help="Path to the second TOML file"),
    ],
) -> None:
    """Compare two TOML files and check if they are identical."""
    with file1.open("rb") as f1, file2.open("rb") as f2:
        toml1 = tomllib.load(f1)
        toml2 = tomllib.load(f2)

    if toml1 == toml2:
        err_console.print("[green]✓ The TOML files are identical.[/green]")
        raise typer.Exit(0)

    err_console.print("[red]✗ The TOML files differ.[/red]")
    raise typer.Exit(1)


@app.command()
def edit(
    path: Annotated[
        str,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ],
    *,
    input: Annotated[  # noqa: A002
        Path,
        typer.Option("-i", "--input", help="Path to input TOML file to edit"),
    ],
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("-y", "--yes", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Edit input TOML file with interactive TUI.

    Opens a spreadsheet-like interface for editing Table fields in the input file.
    Supports 2D and 3D tables with dimension slicing.

    Controls:
    - Arrow keys: Navigate cells
    - Enter: Edit selected cell
    - Tab: Switch to next table
    - S: Save changes
    - Q: Quit (prompts to save if unsaved changes)
    """
    # Import TUI components here to avoid loading textual for other commands
    from .tui.app import VeriqEditApp  # noqa: PLC0415

    # Load the project
    if ":" in path:
        # Module path format
        project = _load_project_from_module_path(path)
    else:
        # Script path format
        script_path = Path(path)
        project = _load_project_from_script(script_path, project_var)

    # Verify input file exists
    if not input.exists():
        err_console.print(f"[red]Error: Input file not found: {input}[/red]")
        raise typer.Exit(code=1)

    # Confirm before editing (comments will be lost when saving)
    if not yes:
        err_console.print()
        err_console.print(
            "[yellow]Warning: TOML comments in the input file will NOT be preserved when saving.[/yellow]",
        )
        typer.confirm("Do you want to continue?", abort=True)

    # Launch the TUI
    tui_app = VeriqEditApp(input, project)
    tui_app.run()


def main() -> None:
    app()
