"""Custom widgets for TUI table editing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from textual.binding import Binding
from textual.containers import Horizontal
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable, Input, Label, Select, Static
from textual.widgets._select import NoSelection

if TYPE_CHECKING:
    from enum import StrEnum

    from textual.app import ComposeResult

    from .data import TableData


class DimensionSelector(Static):
    """Widget for selecting fixed dimension values (slice control).

    For 3D+ tables, this shows dropdown(s) to select which slice to view.
    """

    class DimensionChanged(Message):
        """Message sent when a dimension selection changes."""

        def __init__(self, dimension: int, value: StrEnum) -> None:
            super().__init__()
            self.dimension = dimension
            self.value = value

    def __init__(
        self,
        options: list[tuple[int, str, list[str]]],
        key_types: tuple[type[StrEnum], ...],
        *,
        id: str | None = None,  # noqa: A002
    ) -> None:
        """Initialize the dimension selector.

        Args:
            options: List of (dimension_index, enum_type_name, [enum_values])
            key_types: The enum types for each dimension
            id: Widget ID

        """
        super().__init__(id=id)
        self.options = options
        self.key_types = key_types
        self._selects: dict[int, Select[str | None]] = {}

    def compose(self) -> ComposeResult:
        """Compose the widget."""
        if not self.options:
            return

        with Horizontal(classes="dimension-selector"):
            for dim_idx, enum_name, values in self.options:
                yield Label(f"{enum_name}: ")
                select = Select(
                    [(v, v) for v in values],
                    value=values[0] if values else None,
                    id=f"dim-select-{dim_idx}",
                )
                self._selects[dim_idx] = select
                yield select

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle selection changes."""
        # Extract dimension index from select ID
        if event.select.id and event.select.id.startswith("dim-select-"):
            dim_idx = int(event.select.id.split("-")[-1])
            if event.value is not None and isinstance(event.value, str):
                # Convert string value back to enum
                enum_type = self.key_types[dim_idx]
                enum_value = enum_type(event.value)
                self.post_message(self.DimensionChanged(dim_idx, enum_value))

    def get_fixed_dims(self) -> dict[int, StrEnum]:
        """Get the current fixed dimension values."""
        result: dict[int, StrEnum] = {}
        for dim_idx, select in self._selects.items():
            if select.value is not None and isinstance(select.value, str):
                enum_type = self.key_types[dim_idx]
                result[dim_idx] = enum_type(select.value)
        return result


class InlineCellInput(Input):
    """Input widget for inline cell editing."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    class EditConfirmed(Message):
        """Message sent when edit is confirmed."""

        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    class EditCancelled(Message):
        """Message sent when edit is cancelled."""

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Handle Enter key - confirm the edit."""
        self.post_message(self.EditConfirmed(self.value))

    def action_cancel(self) -> None:
        """Handle Escape key - cancel the edit."""
        self.post_message(self.EditCancelled())


class TableEditor(DataTable):
    """DataTable subclass with cell editing support for veriq Tables."""

    class CellValueUpdated(Message):
        """Message sent when a cell value has been updated."""

        def __init__(
            self,
            row_label: str,
            col_label: str,
            new_value: Any,
        ) -> None:
            super().__init__()
            self.row_label = row_label
            self.col_label = col_label
            self.new_value = new_value

    def __init__(self, *, id: str | None = None) -> None:  # noqa: A002
        """Initialize the table editor."""
        super().__init__(cursor_type="cell", id=id)
        self.table_data: TableData | None = None
        self.fixed_dims: dict[int, StrEnum] = {}
        self._row_labels: list[str] = []
        self._col_labels: list[str] = []
        # Inline editing state
        self._editing: bool = False
        self._edit_coordinate: Coordinate | None = None
        self._edit_row_label: str = ""
        self._edit_col_label: str = ""
        self._inline_input: InlineCellInput | None = None

    def load_table(
        self,
        table_data: TableData,
        fixed_dims: dict[int, StrEnum] | None = None,
    ) -> None:
        """Populate the grid from TableData slice.

        Args:
            table_data: The TableData to display
            fixed_dims: Fixed dimension values for slicing (for 3D+ tables)

        """
        self.clear(columns=True)
        self.table_data = table_data
        self.fixed_dims = fixed_dims or {}

        # Initialize fixed dims with first values if not provided
        for dim_idx, _enum_name, values in table_data.get_fixed_dimension_options():
            if dim_idx not in self.fixed_dims and values:
                self.fixed_dims[dim_idx] = table_data.key_types[dim_idx](values[0])

        # Get labels
        self._row_labels = table_data.row_labels(self.fixed_dims)
        self._col_labels = table_data.column_labels(self.fixed_dims)

        # Add columns (first column is for row labels)
        self.add_column("", key="__label__")
        for col_label in self._col_labels:
            self.add_column(col_label, key=col_label)

        # Add rows
        for row_label in self._row_labels:
            row_values: list[str] = [row_label]
            for col_label in self._col_labels:
                value = table_data.get_cell(self.fixed_dims, row_label, col_label)
                row_values.append(self._format_value(value))
            self.add_row(*row_values, key=row_label)

    def _format_value(self, value: Any) -> str:
        """Format a cell value for display."""
        if value is None:
            return ""
        if isinstance(value, float):
            # Format floats with reasonable precision
            if value == int(value):
                return str(int(value))
            return f"{value:.6g}"
        return str(value)

    def update_slice(self, fixed_dims: dict[int, StrEnum]) -> None:
        """Update the display for a new slice (when dimension selector changes)."""
        if self.table_data is not None:
            self.load_table(self.table_data, fixed_dims)

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Handle cell selection - start inline edit for non-label cells."""
        # Skip the first column (row labels)
        if event.coordinate.column == 0:
            return

        if self.table_data is None:
            return

        # Get the row and column labels
        row_idx = event.coordinate.row
        col_idx = event.coordinate.column - 1  # Adjust for label column

        if row_idx >= len(self._row_labels) or col_idx >= len(self._col_labels):
            return

        row_label = self._row_labels[row_idx]
        col_label = self._col_labels[col_idx]

        # Get current value
        current_value = self.table_data.get_cell(self.fixed_dims, row_label, col_label)

        # Start inline editing
        self._start_inline_edit(event.coordinate, current_value, row_label, col_label)

    def _start_inline_edit(
        self,
        coordinate: Coordinate,
        current_value: Any,
        row_label: str,
        col_label: str,
    ) -> None:
        """Start inline editing at the given coordinate.

        Args:
            coordinate: The cell coordinate to edit
            current_value: The current value in the cell
            row_label: The row label
            col_label: The column label

        """
        # If already editing the same cell, do nothing
        if self._editing and self._edit_coordinate == coordinate:
            return

        # Cancel any existing edit first (restore old cell display)
        if self._editing:
            self._restore_cell_display()

        self._editing = True
        self._edit_coordinate = coordinate
        self._edit_row_label = row_label
        self._edit_col_label = col_label

        # Update the cell to show the input value directly
        formatted = self._format_value(current_value)
        self.update_cell_at(coordinate, f"[bold cyan]{formatted}[/]")

        # Reuse existing input widget or create a new one
        if self._inline_input is not None:
            # Reuse the existing input - just update its value
            self._inline_input.value = formatted
            self._inline_input.focus()
        else:
            # Create the inline input
            self._inline_input = InlineCellInput(
                value=formatted,
                id="inline-edit",
            )
            self.app.mount(self._inline_input)
            self._inline_input.focus()

    def _restore_cell_display(self) -> None:
        """Restore the cell display to its original value without cleaning up edit state."""
        if self._edit_coordinate is None or self.table_data is None:
            return

        original_value = self.table_data.get_cell(
            self.fixed_dims,
            self._edit_row_label,
            self._edit_col_label,
        )
        self.update_cell_at(
            self._edit_coordinate,
            self._format_value(original_value),
        )

    def cancel_inline_edit(self) -> None:
        """Cancel the current inline edit and restore the original value."""
        if not self._editing or self._edit_coordinate is None:
            return

        self._restore_cell_display()
        self._cleanup_inline_edit()

    def confirm_inline_edit(self, text: str) -> None:
        """Confirm the inline edit with the given value.

        Args:
            text: The text value from the input

        """
        if not self._editing or self._edit_coordinate is None or self.table_data is None:
            self._cleanup_inline_edit()
            return

        # Parse the value
        try:
            parsed_value = self._parse_value(text, self.table_data.value_type)
        except (ValueError, TypeError):
            # Invalid value - cancel the edit
            self.cancel_inline_edit()
            return

        # Update the cell
        self.update_cell_value(
            self._edit_row_label,
            self._edit_col_label,
            parsed_value,
        )
        self._cleanup_inline_edit()

    def _cleanup_inline_edit(self) -> None:
        """Clean up the inline editing state."""
        if self._inline_input is not None:
            self._inline_input.remove()
            self._inline_input = None

        self._editing = False
        self._edit_coordinate = None
        self._edit_row_label = ""
        self._edit_col_label = ""
        self.focus()

    def _parse_value(self, text: str, value_type: type) -> Any:
        """Parse the input text into the appropriate type.

        Args:
            text: The input text to parse
            value_type: The expected type

        Returns:
            The parsed value

        Raises:
            ValueError: If the text cannot be parsed to the expected type

        """
        text = text.strip()

        if value_type is float:
            return float(text)

        if value_type is int:
            return int(text)

        if value_type is bool:
            lower = text.lower()
            if lower in ("true", "1", "yes"):
                return True
            if lower in ("false", "0", "no"):
                return False
            msg = "Boolean value must be true/false, 1/0, or yes/no"
            raise ValueError(msg)

        if value_type is str:
            return text

        # Try to construct the type directly
        return value_type(text)

    def on_inline_cell_input_edit_confirmed(
        self,
        event: InlineCellInput.EditConfirmed,
    ) -> None:
        """Handle edit confirmation from inline input."""
        self.confirm_inline_edit(event.value)

    def on_inline_cell_input_edit_cancelled(
        self,
        _event: InlineCellInput.EditCancelled,
    ) -> None:
        """Handle edit cancellation from inline input."""
        self.cancel_inline_edit()

    def update_cell_value(
        self,
        row_label: str,
        col_label: str,
        new_value: Any,
    ) -> None:
        """Update a cell value in both the display and underlying data.

        Args:
            row_label: The row label
            col_label: The column label
            new_value: The new value to set

        """
        if self.table_data is None:
            return

        # Update the underlying data
        self.table_data.update_cell(self.fixed_dims, row_label, col_label, new_value)

        # Update the display
        try:
            row_idx = self._row_labels.index(row_label)
            col_idx = self._col_labels.index(col_label) + 1  # Adjust for label column
            self.update_cell_at(
                Coordinate(row_idx, col_idx),
                self._format_value(new_value),
            )
        except (ValueError, IndexError):
            pass

        # Post message about the update
        self.post_message(self.CellValueUpdated(row_label, col_label, new_value))


class TableSelector(Static):
    """Widget for selecting which table to edit within a scope."""

    class TableSelected(Message):
        """Message sent when a table is selected."""

        def __init__(self, field_path: str) -> None:
            super().__init__()
            self.field_path = field_path

    def __init__(
        self,
        tables: dict[str, TableData],
        *,
        id: str | None = None,  # noqa: A002
    ) -> None:
        """Initialize the table selector.

        Args:
            tables: Dict mapping field_path to TableData
            id: Widget ID

        """
        super().__init__(id=id)
        self.tables = tables
        self._select: Select[str] | None = None

    def compose(self) -> ComposeResult:
        """Compose the widget."""
        table_names = list(self.tables.keys())
        if not table_names:
            yield Label("No tables found in this scope")
            return

        with Horizontal(classes="table-selector"):
            yield Label("Table: ")
            self._select = Select(
                [(name, name) for name in table_names],
                value=table_names[0],
                id="table-select",
            )
            yield self._select

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle table selection change."""
        if event.value is not None and not isinstance(event.value, NoSelection):
            self.post_message(self.TableSelected(str(event.value)))

    @property
    def current_table(self) -> str | None:
        """Get the currently selected table path."""
        if self._select is not None:
            value = self._select.value
            if isinstance(value, NoSelection):
                return None
            return value
        return None

    def set_table(self, field_path: str) -> None:
        """Set the currently selected table.

        Args:
            field_path: The field path of the table to select

        """
        if self._select is not None:
            self._select.value = field_path
