from __future__ import annotations

import importlib.metadata
import json
import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from veriq._models import Project

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
from veriq._path import VerificationPath
from veriq._toml_edit import dumps_toml, merge_into_document, parse_toml_preserving
from veriq._traceability import RequirementStatus, build_traceability_report
from veriq._update import update_input_data

from .config import ConfigError, VeriqConfig, get_config
from .discover import load_project_from_module_path, load_project_from_script
from .render_trace import render_traceability_summary, render_traceability_table


def _get_version() -> str:
    """Get the package version."""
    try:
        return importlib.metadata.version("veriq")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


app = typer.Typer()

logger = logging.getLogger(__name__)
# Console for stderr (info/errors)
err_console = Console(stderr=True)
# Console for stdout (results)
out_console = Console()


def _version_callback(value: bool) -> None:  # noqa: FBT001
    """Print version and exit."""
    if value:
        print(f"veriq {_get_version()}")  # noqa: T201
        raise typer.Exit(code=0)


@app.callback()
def callback(
    *,
    verbose: bool = typer.Option(default=False, help="Enable verbose output"),
    version: bool = typer.Option(  # noqa: ARG001
        default=False,
        help="Show version and exit",
        callback=_version_callback,
        is_eager=True,
    ),
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


def _load_project(
    path: str | None,
    config: VeriqConfig,
    project_var: str | None = None,
) -> Project:
    """Load project from CLI path or config.

    Args:
        path: CLI-provided path (script path or module path), or None to use config
        config: VeriqConfig instance
        project_var: Optional variable name (for script paths only)

    Returns:
        The loaded Project instance

    Raises:
        typer.BadParameter: If no project is specified and no default in config

    """
    if path is not None:
        # CLI path provided - use it
        if ":" in path:
            # Module path format
            err_console.print(f"[cyan]Loading project from module:[/cyan] {path}")
            return load_project_from_module_path(path)
        # Script path format
        script_path = Path(path)
        err_console.print(f"[cyan]Loading project from script:[/cyan] {script_path}")
        return load_project_from_script(script_path, project_var)

    # No CLI path - try config
    if config.project is None:
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
            # CLI --project overrides config name
            effective_name = project_var if project_var else name
            return load_project_from_script(script, effective_name)
        case ModuleSource(module_path=module_path):
            err_console.print(f"[cyan]Loading project from module:[/cyan] {module_path}")
            return load_project_from_module_path(module_path)


@app.command()
def calc(  # noqa: C901, PLR0912, PLR0915
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
        typer.Option("-o", "--output", help="Path to output TOML file"),
    ] = None,
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

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Resolve input/output from config if not provided
    effective_input = input if input is not None else config.input
    effective_output = output if output is not None else config.output

    if effective_input is None:
        err_console.print("[red]Error: Input file required. Use -i/--input or configure [tool.veriq].input[/red]")
        raise typer.Exit(code=1)
    if effective_output is None:
        err_console.print("[red]Error: Output file required. Use -o/--output or configure [tool.veriq].output[/red]")
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
    result = evaluate_project(project, model_data)
    err_console.print()

    # Check verifications if requested
    exit_as_err = False
    if verify:
        # Group verification results by scope
        grouped_results: dict[str, list[tuple[str, bool, bool]]] = {}

        for ppath, value in result.values.items():
            if isinstance(ppath.path, VerificationPath):
                verification_name = ppath.path.verification_name
                scope_name = ppath.scope
                scope = project.scopes[scope_name]
                verification = scope.verifications[verification_name]
                # Build display name WITHOUT scope prefix
                display_name = f"?{verification_name}"
                if ppath.path.parts:
                    display_name += str(ppath.path)[len(f"?{verification_name}") :]

                if scope_name not in grouped_results:
                    grouped_results[scope_name] = []
                grouped_results[scope_name].append((display_name, value, verification.xfail))

                if (not value) ^ verification.xfail:
                    exit_as_err = True

        # Create a table for verification results grouped by scope
        if grouped_results:
            table = Table(show_header=False, box=None)
            table.add_column("Verification")
            table.add_column("Result")

            total_passed = 0
            total_count = 0
            total_xfail_failed = 0

            # Iterate scopes in project order for consistent display
            for scope_name in project.scopes:
                if scope_name not in grouped_results:
                    continue

                results = grouped_results[scope_name]

                # Calculate per-scope statistics
                scope_passed = sum(1 for _, passed, _ in results if passed)
                scope_total = len(results)
                scope_xfail_failed = sum(1 for _, passed, xfail in results if xfail and not passed)

                total_passed += scope_passed
                total_count += scope_total
                total_xfail_failed += scope_xfail_failed

                # Add scope header row
                scope_header = f"[bold]{scope_name}[/bold] [dim]({scope_passed}/{scope_total} passed)[/dim]"
                table.add_row(scope_header, "")

                # Add verification rows with indentation
                for verif_name, passed, xfail in results:
                    escaped_verif_name = f"[dim]  {escape(verif_name)}[/dim]"
                    status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
                    if xfail and not passed:
                        status += " [yellow](expected failure)[/yellow]"
                    elif xfail and passed:
                        status += " [red](unexpected pass)[/red]"
                    table.add_row(escaped_verif_name, status)

            err_console.print(Panel(table, title="[bold]Verification Results[/bold]", border_style="cyan"))

            # Summary line
            if total_xfail_failed > 0:
                err_console.print(
                    f"[dim]Summary: {total_passed}/{total_count} passed, "
                    f"{total_xfail_failed} expected failure(s)[/dim]",
                )
            else:
                err_console.print(f"[dim]Summary: {total_passed}/{total_count} passed[/dim]")
            err_console.print()

        has_failures = any(
            not passed for results in grouped_results.values() for _, passed, _ in results
        )
        if has_failures:
            err_console.print("[red]✗ Some verifications failed[/red]")

    # Export results
    err_console.print(f"[cyan]Exporting results to:[/cyan] {effective_output}")
    export_to_toml(project, model_data, result.values, effective_output)

    err_console.print()
    err_console.print("[green]✓ Calculation complete[/green]")
    err_console.print()

    if exit_as_err:
        raise typer.Exit(code=1)

    raise typer.Exit(code=0)


@app.command()
def check(
    path: Annotated[
        str | None,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
    *,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
) -> None:
    """Check the validity of a project without performing calculations."""
    err_console.print()

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

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
        str | None,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
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

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

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
        str | None,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
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

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Generate default input data
    err_console.print("[cyan]Generating default input data...[/cyan]")
    input_data_model = project.input_model()
    input_default_data = default(input_data_model)

    # Write to TOML file (new file, no comments to preserve)
    import tomli_w  # noqa: PLC0415

    err_console.print(f"[cyan]Writing sample input to:[/cyan] {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("wb") as f:
        tomli_w.dump(input_default_data.model_dump(), f)

    err_console.print()
    err_console.print("[green]✓ Sample input file generated[/green]")
    err_console.print()


@app.command()
def update(  # noqa: PLR0915
    path: Annotated[
        str | None,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
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

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Load existing input file (preserving comments with tomlkit)
    err_console.print(f"[cyan]Loading existing input from:[/cyan] {input}")
    original_content = input.read_text()
    toml_doc = parse_toml_preserving(original_content)
    # Also parse with tomllib for the update logic (dict-based)
    with input.open("rb") as f:
        existing_data = tomllib.load(f)

    # Generate new default data from current schema
    err_console.print("[cyan]Generating defaults from current schema...[/cyan]")
    project_input_model = project.input_model()
    new_default_data = default(project_input_model)

    # Perform the update (functional core for warnings/logic)
    err_console.print("[cyan]Merging existing data with new defaults...[/cyan]")
    new_default_dict = new_default_data.model_dump()
    result = update_input_data(new_default_dict, existing_data)

    # Also merge into the TOML document to preserve comments
    merge_into_document(toml_doc, new_default_dict, existing_data)

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

        # Show a preview using TOML format (with comments preserved)
        preview_text = dumps_toml(toml_doc)

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
        # Write the updated data (comments are now preserved)
        err_console.print(f"[cyan]Writing updated input to:[/cyan] {output}")
        output.parent.mkdir(parents=True, exist_ok=True)

        output.write_text(dumps_toml(toml_doc))

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
        str | None,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
    *,
    input: Annotated[  # noqa: A002
        Path | None,
        typer.Option("-i", "--input", help="Path to input TOML file to edit"),
    ] = None,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
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

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Verify input file exists
    if not effective_input.exists():
        err_console.print(f"[red]Error: Input file not found: {effective_input}[/red]")
        raise typer.Exit(code=1)

    # Launch the TUI (comments are now preserved when saving)
    tui_app = VeriqEditApp(effective_input, project)
    tui_app.run()


@app.command()
def trace(
    path: Annotated[
        str | None,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
    *,
    input: Annotated[  # noqa: A002
        Path | None,
        typer.Option("-i", "--input", help="Path to input TOML file (optional, enables verification evaluation)"),
    ] = None,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
) -> None:
    """Display requirement-verification traceability.

    Shows the requirement tree with verification status for each requirement.

    Without --input: Shows requirement tree structure only.
    With --input: Runs evaluation and shows pass/fail status.

    Exit codes:
    - 0: All requirements pass (or only expected failures)
    - 1: Some requirements failed unexpectedly
    """
    err_console.print()

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    err_console.print(f"[cyan]Project:[/cyan] [bold]{project.name}[/bold]")
    err_console.print()

    # Load model data and evaluate if input provided
    evaluation_results = None
    if input is not None:
        err_console.print(f"[cyan]Loading input from:[/cyan] {input}")
        model_data = load_model_data_from_toml(project, input)

        err_console.print("[cyan]Evaluating project...[/cyan]")
        evaluation_results = evaluate_project(project, model_data)
        err_console.print()

    # Build traceability report
    try:
        report = build_traceability_report(project, evaluation_results)
    except ValueError as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Render the report
    has_evaluation = evaluation_results is not None
    render_traceability_table(report, err_console, has_evaluation=has_evaluation)
    err_console.print()
    render_traceability_summary(report, err_console, has_evaluation=has_evaluation)
    err_console.print()

    # Determine exit code
    exit_as_err = False
    if evaluation_results is not None:
        for entry in report.entries:
            # Failed requirement that is not xfail -> error
            if entry.status == RequirementStatus.FAILED and not entry.xfail:
                exit_as_err = True
                break

    if exit_as_err:
        err_console.print("[red]✗ Some requirements failed[/red]")
        raise typer.Exit(code=1)

    if evaluation_results is not None:
        err_console.print("[green]✓ All requirements satisfied[/green]")
    else:
        err_console.print("[dim]Run with --input to evaluate requirement status[/dim]")

    err_console.print()
    raise typer.Exit(code=0)


@app.command()
def scopes(
    path: Annotated[
        str | None,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
    *,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """List all scopes in the project with summary information."""
    from .graph_query import get_scope_summaries  # noqa: PLC0415
    from .graph_render import render_scope_table  # noqa: PLC0415

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    summaries = get_scope_summaries(project)

    if as_json:
        data = [
            {
                "name": s.name,
                "models": s.model_count,
                "calcs": s.calc_count,
                "verifications": s.verification_count,
            }
            for s in summaries
        ]
        out_console.print_json(data=data)
    else:
        render_scope_table(summaries, err_console)


@app.command("list")
def list_nodes_cmd(  # noqa: PLR0913
    path: Annotated[
        str | None,
        typer.Argument(help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
    *,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    kind: Annotated[
        list[str] | None,
        typer.Option("--kind", help="Filter by kind: model, calc, verification (repeatable)"),
    ] = None,
    scope: Annotated[
        list[str] | None,
        typer.Option("--scope", help="Filter by scope name (repeatable)"),
    ] = None,
    leaves: Annotated[
        bool,
        typer.Option("--leaves", help="Show only leaf nodes (nothing depends on them)"),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """List nodes in the dependency graph with optional filtering."""
    from veriq._ir import NodeKind  # noqa: PLC0415

    from .graph_query import get_available_scopes, list_nodes  # noqa: PLC0415
    from .graph_render import render_node_table  # noqa: PLC0415

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Convert kind strings to NodeKind enum
    kinds: list[NodeKind] | None = None
    if kind:
        kind_map = {
            "model": NodeKind.MODEL,
            "calc": NodeKind.CALCULATION,
            "calculation": NodeKind.CALCULATION,
            "verification": NodeKind.VERIFICATION,
            "verif": NodeKind.VERIFICATION,
        }
        kinds = []
        for k in kind:
            k_lower = k.lower()
            if k_lower not in kind_map:
                err_console.print(f"[red]Error: Unknown kind '{k}'[/red]")
                err_console.print("[dim]Valid kinds: model, calc, verification[/dim]")
                raise typer.Exit(code=1)
            kinds.append(kind_map[k_lower])

    # Validate scope names
    if scope:
        available_scopes = get_available_scopes(project)
        for s in scope:
            if s not in available_scopes:
                err_console.print(f"[red]Error: Unknown scope '{s}'[/red]")
                err_console.print(f"[dim]Available scopes: {', '.join(available_scopes)}[/dim]")
                raise typer.Exit(code=1)

    nodes = list_nodes(project, kinds=kinds, scopes=scope, leaves_only=leaves)

    if as_json:
        data = [
            {
                "path": str(n.path),
                "kind": n.kind.value,
                "dependencies": n.dependency_count,
            }
            for n in nodes
        ]
        out_console.print_json(data=data)
    else:
        render_node_table(nodes, err_console)


@app.command()
def show(
    node_path: Annotated[
        str,
        typer.Argument(help="Node path in format 'Scope::path' (e.g., 'Power::$.design')"),
    ],
    path: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
    *,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """View detailed information about a specific node."""
    from veriq._path import parse_project_path  # noqa: PLC0415

    from .graph_query import NonLeafPathError, get_available_scopes, get_node_detail  # noqa: PLC0415
    from .graph_render import render_node_detail  # noqa: PLC0415

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Parse the node path
    try:
        ppath = parse_project_path(node_path)
    except ValueError as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Validate scope exists
    available_scopes = get_available_scopes(project)
    if ppath.scope not in available_scopes:
        err_console.print(f"[red]Error: Unknown scope '{ppath.scope}'[/red]")
        err_console.print(f"[dim]Available scopes: {', '.join(available_scopes)}[/dim]")
        raise typer.Exit(code=1)

    # Get node detail
    try:
        detail = get_node_detail(project, ppath)
    except NonLeafPathError as e:
        from veriq._path import format_for_display  # noqa: PLC0415

        escaped_node_path = escape(node_path)
        err_console.print(f"[red]Error: '{escaped_node_path}' is not a leaf node[/red]")
        err_console.print()
        err_console.print(f"[cyan]This path has {len(e.leaf_paths)} leaf output(s):[/cyan]")
        for leaf_path in e.leaf_paths:
            err_console.print(f"  {format_for_display(leaf_path, escape_markup=True)}")
        err_console.print()
        err_console.print("[dim]Use one of the leaf paths above with 'veriq show'[/dim]")
        raise typer.Exit(code=1) from None
    except KeyError:
        escaped_node_path = escape(node_path)
        err_console.print(f"[red]Error: Node not found: {escaped_node_path}[/red]")
        err_console.print("[dim]Use 'veriq list' to see available nodes[/dim]")
        raise typer.Exit(code=1) from None

    if as_json:
        data = {
            "path": str(detail.path),
            "kind": detail.kind.value,
            "scope": detail.path.scope,
            "output_type": (
                detail.output_type.__name__
                if hasattr(detail.output_type, "__name__")
                else str(detail.output_type)
            ),
            "dependencies": [str(d) for d in sorted(detail.direct_dependencies, key=str)],
            "dependents": [str(d) for d in sorted(detail.direct_dependents, key=str)],
            "metadata": detail.metadata,
        }
        out_console.print_json(data=data)
    else:
        render_node_detail(detail, err_console)


@app.command()
def tree(  # noqa: PLR0913
    node_path: Annotated[
        str,
        typer.Argument(help="Node path in format 'Scope::path' (e.g., 'Power::$.design')"),
    ],
    path: Annotated[
        str | None,
        typer.Option("--path", "-p", help="Path to Python script or module path (e.g., examples.dummysat:project)"),
    ] = None,
    *,
    project_var: Annotated[
        str | None,
        typer.Option("--project", help="Name of the project variable (for script paths only)"),
    ] = None,
    invert: Annotated[
        bool,
        typer.Option("-i", "--invert", help="Show reverse dependencies (what depends on this node)"),
    ] = False,
    depth: Annotated[
        int | None,
        typer.Option("--depth", help="Maximum tree depth (default: unlimited)"),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON"),
    ] = False,
) -> None:
    """Show dependency tree for a node.

    By default, shows what the node depends on.
    Use --invert/-i to show what depends on the node (impact analysis).
    """
    from veriq._path import parse_project_path  # noqa: PLC0415

    from .graph_query import get_available_scopes, get_dependency_tree  # noqa: PLC0415
    from .graph_render import render_tree  # noqa: PLC0415

    # Load config
    try:
        config = get_config()
    except ConfigError as e:
        err_console.print(f"[red]Configuration error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Load the project
    try:
        project = _load_project(path, config, project_var)
    except typer.BadParameter as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Parse the node path
    try:
        ppath = parse_project_path(node_path)
    except ValueError as e:
        err_console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e

    # Validate scope exists
    available_scopes = get_available_scopes(project)
    if ppath.scope not in available_scopes:
        err_console.print(f"[red]Error: Unknown scope '{ppath.scope}'[/red]")
        err_console.print(f"[dim]Available scopes: {', '.join(available_scopes)}[/dim]")
        raise typer.Exit(code=1)

    # Get dependency tree
    try:
        tree_node = get_dependency_tree(project, ppath, invert=invert, max_depth=depth)
    except KeyError:
        escaped_node_path = escape(node_path)
        err_console.print(f"[red]Error: Node not found: {escaped_node_path}[/red]")
        err_console.print("[dim]Use 'veriq list' to see available nodes[/dim]")
        raise typer.Exit(code=1) from None

    if as_json:
        from .graph_query import TreeNode as TreeNodeType  # noqa: PLC0415

        def tree_to_dict(node: TreeNodeType) -> dict:
            return {
                "path": str(node.path),
                "children": [tree_to_dict(c) for c in node.children],
            }

        out_console.print_json(data=tree_to_dict(tree_node))
    elif not tree_node.children:
        escaped_node_path = escape(node_path)
        if invert:
            err_console.print(f"[dim]No nodes depend on {escaped_node_path}[/dim]")
        else:
            err_console.print(f"[dim]{escaped_node_path} has no dependencies[/dim]")
    else:
        render_tree(tree_node, err_console)


def main() -> None:
    app()
