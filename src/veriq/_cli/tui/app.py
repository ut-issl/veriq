"""Main TUI application for veriq table editing."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any, ClassVar

import tomli_w
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Label, TabbedContent, TabPane

from .data import TableData, load_tables_from_toml, save_tables_to_toml
from .screens import ConfirmQuitScreen
from .widgets import DimensionSelector, InlineCellInput, TableEditor, TableSelector

if TYPE_CHECKING:
    from pathlib import Path

    from veriq._models import Project


class VeriqEditApp(App[None]):
    """TUI application for editing veriq Table input files."""

    TITLE = "veriq edit"

    CSS = """
    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 0;
    }

    .scope-container {
        height: 1fr;
    }

    .table-selector {
        height: 3;
        padding: 0 1;
        background: $surface;
    }

    .dimension-selector {
        height: 3;
        padding: 0 1;
        background: $surface-darken-1;
    }

    TableEditor {
        height: 1fr;
    }

    .no-tables {
        height: 100%;
        width: 100%;
        content-align: center middle;
    }

    .modified-indicator {
        dock: right;
        width: auto;
        padding: 0 1;
        color: $warning;
    }

    #inline-edit {
        dock: bottom;
        height: 3;
        background: $boost;
        border: tall $primary;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("s", "save", "Save", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("tab", "next_table", "Next Table", show=True),
    ]

    def __init__(
        self,
        toml_path: Path,
        project: Project,
    ) -> None:
        """Initialize the app.

        Args:
            toml_path: Path to the input TOML file
            project: The veriq Project instance

        """
        super().__init__()
        self.toml_path = toml_path
        self.project = project
        self.toml_data: dict[str, Any] = {}
        self.tables: dict[str, dict[str, TableData]] = {}
        self._current_scope: str | None = None
        self._current_table_path: str | None = None
        self._editors: dict[str, TableEditor] = {}
        self._dimension_selectors: dict[str, DimensionSelector] = {}

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header()

        # Load data
        self._load_data()

        if not self.tables:
            yield Label("No tables found in the input file", classes="no-tables")
            yield Footer()
            return

        with TabbedContent():
            for scope_name, scope_tables in self.tables.items():
                with TabPane(scope_name, id=f"scope-{scope_name}"), Vertical(classes="scope-container"):
                    # Table selector
                    yield TableSelector(
                        scope_tables,
                        id=f"table-selector-{scope_name}",
                    )

                    # Dimension selector (initially hidden, shown for 3D+ tables)
                    yield Container(id=f"dim-container-{scope_name}")

                    # Table editor
                    editor = TableEditor(id=f"editor-{scope_name}")
                    self._editors[scope_name] = editor
                    yield editor

        yield Footer()

    def _load_data(self) -> None:
        """Load TOML data and extract tables."""
        with self.toml_path.open("rb") as f:
            self.toml_data = tomllib.load(f)

        self.tables = load_tables_from_toml(self.project, self.toml_data)

    def on_mount(self) -> None:
        """Initialize the display after mounting."""
        if not self.tables:
            return

        # Set initial scope
        self._current_scope = next(iter(self.tables.keys()))

        # Load the first table in the first scope
        if self._current_scope and self._current_scope in self.tables:
            scope_tables = self.tables[self._current_scope]
            if scope_tables:
                first_table_path = next(iter(scope_tables.keys()))
                self._load_table_in_editor(self._current_scope, first_table_path)

    def on_tabbed_content_tab_activated(
        self,
        event: TabbedContent.TabActivated,
    ) -> None:
        """Handle scope tab changes."""
        # Extract scope name from tab ID
        if event.tab.id and event.tab.id.startswith("scope-"):
            scope_name = event.tab.id[6:]  # Remove "scope-" prefix
            self._current_scope = scope_name

            # Load the first table in the new scope if not already loaded
            if scope_name in self.tables:
                scope_tables = self.tables[scope_name]
                if scope_tables:
                    selector = self.query_one(
                        f"#table-selector-{scope_name}",
                        TableSelector,
                    )
                    current_table = selector.current_table
                    if current_table:
                        self._load_table_in_editor(scope_name, current_table)

    def on_table_selector_table_selected(
        self,
        event: TableSelector.TableSelected,
    ) -> None:
        """Handle table selection changes."""
        if self._current_scope:
            self._load_table_in_editor(self._current_scope, event.field_path)

    def _load_table_in_editor(self, scope_name: str, field_path: str) -> None:
        """Load a specific table into the editor.

        Args:
            scope_name: The scope containing the table
            field_path: The field path of the table

        """
        if scope_name not in self.tables:
            return

        scope_tables = self.tables[scope_name]
        if field_path not in scope_tables:
            return

        table_data = scope_tables[field_path]
        self._current_table_path = field_path

        # Get or create editor
        editor = self._editors.get(scope_name)
        if editor is None:
            return

        # Update dimension selector if needed
        self._update_dimension_selector(scope_name, table_data)

        # Load the table
        dim_selector = self._dimension_selectors.get(scope_name)
        fixed_dims = dim_selector.get_fixed_dims() if dim_selector else {}
        editor.load_table(table_data, fixed_dims)

    def _update_dimension_selector(
        self,
        scope_name: str,
        table_data: TableData,
    ) -> None:
        """Update the dimension selector for the current table.

        Args:
            scope_name: The scope name
            table_data: The table being displayed

        """
        container = self.query_one(f"#dim-container-{scope_name}", Container)

        # Remove old selector if exists
        old_selector = self._dimension_selectors.get(scope_name)
        if old_selector is not None:
            old_selector.remove()
            del self._dimension_selectors[scope_name]

        # Create new selector if needed
        options = table_data.get_fixed_dimension_options()
        if options:
            selector = DimensionSelector(
                options,
                table_data.key_types,
                id=f"dim-selector-{scope_name}",
            )
            container.mount(selector)
            self._dimension_selectors[scope_name] = selector

    def on_dimension_selector_dimension_changed(
        self,
        _event: DimensionSelector.DimensionChanged,
    ) -> None:
        """Handle dimension selector changes."""
        if self._current_scope is None:
            return

        editor = self._editors.get(self._current_scope)
        dim_selector = self._dimension_selectors.get(self._current_scope)

        if editor and dim_selector:
            fixed_dims = dim_selector.get_fixed_dims()
            editor.update_slice(fixed_dims)

    def on_table_editor_cell_value_updated(
        self,
        _event: TableEditor.CellValueUpdated,
    ) -> None:
        """Handle cell value updates - update the title to show modified state."""
        self._update_title()

    def on_inline_cell_input_edit_confirmed(
        self,
        event: InlineCellInput.EditConfirmed,
    ) -> None:
        """Handle edit confirmation from inline input - forward to the current editor."""
        if self._current_scope is None:
            return
        editor = self._editors.get(self._current_scope)
        if editor:
            editor.confirm_inline_edit(event.value)

    def on_inline_cell_input_edit_cancelled(
        self,
        _event: InlineCellInput.EditCancelled,
    ) -> None:
        """Handle edit cancellation from inline input - forward to the current editor."""
        if self._current_scope is None:
            return
        editor = self._editors.get(self._current_scope)
        if editor:
            editor.cancel_inline_edit()

    def _update_title(self) -> None:
        """Update the title to show modified indicator."""
        has_modifications = any(
            table.modified
            for scope_tables in self.tables.values()
            for table in scope_tables.values()
        )
        if has_modifications:
            self.title = f"veriq edit: {self.toml_path.name} [modified]"
        else:
            self.title = f"veriq edit: {self.toml_path.name}"

    def _has_unsaved_changes(self) -> bool:
        """Check if there are any unsaved changes."""
        return any(
            table.modified
            for scope_tables in self.tables.values()
            for table in scope_tables.values()
        )

    def action_save(self) -> None:
        """Save the current changes to the TOML file."""
        self._save_changes()
        self.notify("Changes saved", severity="information")

    def _save_changes(self) -> None:
        """Save all modified tables back to the TOML file."""
        save_tables_to_toml(self.tables, self.toml_data)

        with self.toml_path.open("wb") as f:
            tomli_w.dump(self.toml_data, f)

        # Clear modified flags
        for scope_tables in self.tables.values():
            for table in scope_tables.values():
                table.modified = False

        self._update_title()

    async def action_quit(self) -> None:
        """Quit the application, prompting to save if needed."""
        if self._has_unsaved_changes():
            result = await self.push_screen_wait(ConfirmQuitScreen())
            if result is True:
                # Save and quit
                self._save_changes()
                self.exit()
            elif result is False:
                # Quit without saving
                self.exit()
            # else: result is None, cancel - do nothing
        else:
            self.exit()

    def action_next_table(self) -> None:
        """Switch to the next table in the current scope."""
        if self._current_scope is None:
            return

        scope_tables = self.tables.get(self._current_scope, {})
        if not scope_tables:
            return

        table_paths = list(scope_tables.keys())
        if self._current_table_path in table_paths:
            current_idx = table_paths.index(self._current_table_path)
            next_idx = (current_idx + 1) % len(table_paths)
            next_path = table_paths[next_idx]

            # Update the selector
            selector = self.query_one(
                f"#table-selector-{self._current_scope}",
                TableSelector,
            )
            selector.set_table(next_path)

            # Load the new table
            self._load_table_in_editor(self._current_scope, next_path)
