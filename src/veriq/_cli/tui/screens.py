"""Modal screens for TUI table editing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


class EditCellScreen(ModalScreen[Any | None]):
    """Modal dialog for editing a single cell value."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS = """
    EditCellScreen {
        align: center middle;
    }

    #dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }

    #dialog Label {
        margin-bottom: 1;
    }

    #cell-input {
        margin-bottom: 1;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    #buttons Button {
        margin: 0 1;
    }

    #error-label {
        color: $error;
        margin-top: 1;
        height: auto;
    }
    """

    def __init__(
        self,
        current_value: Any,
        value_type: type,
        row_label: str,
        col_label: str,
    ) -> None:
        """Initialize the edit cell screen.

        Args:
            current_value: The current value in the cell
            value_type: The expected type of the value
            row_label: The row label for context
            col_label: The column label for context

        """
        super().__init__()
        self.current_value = current_value
        self.value_type = value_type
        self.row_label = row_label
        self.col_label = col_label

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Vertical(id="dialog"):
            yield Label(f"Edit cell [{self.row_label}, {self.col_label}]")
            yield Label(f"Type: {self._get_type_name()}", classes="type-label")
            yield Input(
                value=self._format_value(self.current_value),
                id="cell-input",
                placeholder=f"Enter {self._get_type_name()} value",
            )
            yield Static("", id="error-label")
            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def _get_type_name(self) -> str:
        """Get a human-readable type name."""
        if self.value_type is float:
            return "float"
        if self.value_type is int:
            return "int"
        if self.value_type is bool:
            return "bool"
        if self.value_type is str:
            return "str"
        return self.value_type.__name__

    def _format_value(self, value: Any) -> str:
        """Format a value for display in the input."""
        if value is None:
            return ""
        if isinstance(value, float):
            if value == int(value):
                return str(int(value))
            return str(value)
        return str(value)

    def _parse_value(self, text: str) -> Any:
        """Parse the input text into the appropriate type.

        Args:
            text: The input text to parse

        Returns:
            The parsed value

        Raises:
            ValueError: If the text cannot be parsed to the expected type

        """
        text = text.strip()

        if self.value_type is float:
            return float(text)

        if self.value_type is int:
            return int(text)

        if self.value_type is bool:
            lower = text.lower()
            if lower in ("true", "1", "yes"):
                return True
            if lower in ("false", "0", "no"):
                return False
            msg = "Boolean value must be true/false, 1/0, or yes/no"
            raise ValueError(msg)

        if self.value_type is str:
            return text

        # Try to construct the type directly
        return self.value_type(text)

    def on_mount(self) -> None:
        """Focus the input when mounted."""
        self.query_one("#cell-input", Input).focus()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Handle Enter key in input."""
        self._try_submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "ok":
            self._try_submit()
        elif event.button.id == "cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)

    def _try_submit(self) -> None:
        """Try to parse and submit the value."""
        input_widget = self.query_one("#cell-input", Input)
        error_label = self.query_one("#error-label", Static)

        try:
            parsed_value = self._parse_value(input_widget.value)
            error_label.update("")
            self.dismiss(parsed_value)
        except (ValueError, TypeError) as e:
            error_label.update(f"Error: {e}")


class ConfirmQuitScreen(ModalScreen[bool]):
    """Modal dialog to confirm quitting with unsaved changes."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS = """
    ConfirmQuitScreen {
        align: center middle;
    }

    #dialog {
        width: 50;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $warning;
    }

    #dialog Label {
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    #buttons Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Vertical(id="dialog"):
            yield Label("You have unsaved changes.")
            yield Label("Do you want to save before quitting?")
            with Horizontal(id="buttons"):
                yield Button("Save & Quit", variant="primary", id="save")
                yield Button("Quit without saving", variant="warning", id="quit")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        save_and_quit = True
        quit_without_saving = False
        if event.button.id == "save":
            self.dismiss(save_and_quit)
        elif event.button.id == "quit":
            self.dismiss(quit_without_saving)
        elif event.button.id == "cancel":
            self.dismiss(None)  # Cancel, don't quit

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)
