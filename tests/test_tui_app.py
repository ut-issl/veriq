"""Integration tests for TUI application."""

from __future__ import annotations

import tempfile
from enum import StrEnum, unique
from pathlib import Path
from typing import TYPE_CHECKING, cast

import tomli_w
from pydantic import BaseModel

if TYPE_CHECKING:
    from textual.widgets._data_table import CellType

import veriq as vq
from veriq._cli.tui.app import VeriqEditApp
from veriq._cli.tui.screens import ConfirmQuitScreen, EditCellScreen
from veriq._cli.tui.widgets import TableEditor, TableSelector


@unique
class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"


@unique
class Phase(StrEnum):
    INITIAL = "initial"
    CRUISE = "cruise"


def create_test_project() -> vq.Project:
    """Create a test project with table fields."""
    project = vq.Project("TestProject")
    scope = vq.Scope("TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestRootModel(BaseModel):
        power: vq.Table[Mode, float]
        matrix: vq.Table[tuple[Mode, Phase], float]

    return project


def create_toml_file(data: dict) -> Path:
    """Create a temporary TOML file with the given data."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
        tomli_w.dump(data, f)
        return Path(f.name)


class TestVeriqEditAppInitialization:
    """Tests for app initialization."""

    async def test_app_starts_with_valid_data(self):
        """Test that the app starts correctly with valid TOML data."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                # App should have loaded the tables
                assert "TestScope" in app.tables
                assert "power" in app.tables["TestScope"]
                assert "matrix" in app.tables["TestScope"]

                # Check that table data is loaded correctly
                power_table = app.tables["TestScope"]["power"]
                assert power_table.flat_data["nominal"] == 10.0
                assert power_table.flat_data["safe"] == 5.0
        finally:
            toml_path.unlink()

    async def test_app_displays_scope_tabs(self):
        """Test that scope tabs are displayed."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                # The table selector should be present
                table_selector = app.query_one("#table-selector-TestScope", TableSelector)
                assert table_selector is not None
        finally:
            toml_path.unlink()

    async def test_app_with_empty_toml(self):
        """Test app behavior with empty TOML (no tables)."""
        project = create_test_project()
        toml_data: dict = {}
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                # App should start but have no tables
                assert app.tables == {}
        finally:
            toml_path.unlink()


class TestTableNavigation:
    """Tests for table navigation."""

    async def test_switch_tables_with_action(self):
        """Test switching between tables using next_table action."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                # Initial table should be the first one
                initial_table = app._current_table_path

                # Call the action directly to switch tables
                app.action_next_table()
                await pilot.pause()

                # Table should have changed
                new_table = app._current_table_path
                assert new_table != initial_table
                assert new_table == "matrix"

                # Calling again should cycle back to first table
                app.action_next_table()
                await pilot.pause()
                assert app._current_table_path == "power"
        finally:
            toml_path.unlink()


class TestCellEditing:
    """Tests for cell editing functionality."""

    async def test_click_cell_then_another_cell(self):
        """Test clicking one cell and then another quickly doesn't cause duplicate ID error."""
        from textual.coordinate import Coordinate
        from textual.widgets._data_table import CellKey, ColumnKey, RowKey

        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                editor = app.query_one("#editor-TestScope", TableEditor)

                # Simulate selecting the first cell (nominal row, Value column)
                editor.cursor_coordinate = Coordinate(0, 1)
                editor.post_message(
                    TableEditor.CellSelected(
                        editor,
                        value=cast("CellType", "10"),  # ty: ignore[invalid-argument-type]
                        coordinate=Coordinate(0, 1),
                        cell_key=CellKey(
                            row_key=RowKey("nominal"),
                            column_key=ColumnKey("Value"),
                        ),
                    ),
                )
                await pilot.pause()

                # First cell edit should be active
                assert editor._editing is True
                assert editor._edit_row_label == "nominal"

                # Simulate selecting the second cell (safe row, Value column)
                editor.cursor_coordinate = Coordinate(1, 1)
                editor.post_message(
                    TableEditor.CellSelected(
                        editor,
                        value=cast("CellType", "5"),  # ty: ignore[invalid-argument-type]
                        coordinate=Coordinate(1, 1),
                        cell_key=CellKey(
                            row_key=RowKey("safe"),
                            column_key=ColumnKey("Value"),
                        ),
                    ),
                )
                await pilot.pause()

                # Should not have raised DuplicateIds error
                # The inline input should exist and be focused on the second cell
                assert editor._editing is True
                assert editor._edit_row_label == "safe"
        finally:
            toml_path.unlink()

    async def test_inline_edit_saves_on_enter(self):
        """Test that pressing Enter in inline edit saves the value to the table."""
        from textual.coordinate import Coordinate
        from textual.widgets import Input
        from textual.widgets._data_table import CellKey, ColumnKey, RowKey

        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                editor = app.query_one("#editor-TestScope", TableEditor)
                power_table = app.tables["TestScope"]["power"]

                # Verify initial value
                assert power_table.flat_data["nominal"] == 10.0

                # Simulate selecting the cell (nominal row, Value column)
                editor.cursor_coordinate = Coordinate(0, 1)
                editor.post_message(
                    TableEditor.CellSelected(
                        editor,
                        value=cast("CellType", "10"),  # ty: ignore[invalid-argument-type]
                        coordinate=Coordinate(0, 1),
                        cell_key=CellKey(
                            row_key=RowKey("nominal"),
                            column_key=ColumnKey("Value"),
                        ),
                    ),
                )
                await pilot.pause()

                # Edit should be active
                assert editor._editing is True
                assert editor._inline_input is not None

                # Change the value in the input
                editor._inline_input.value = "99.5"

                # Press Enter to submit
                editor._inline_input.post_message(Input.Submitted(editor._inline_input, "99.5"))
                await pilot.pause()

                # Value should be updated in the table data
                assert power_table.flat_data["nominal"] == 99.5
                assert power_table.modified is True

                # Editing should be finished
                assert editor._editing is False
        finally:
            toml_path.unlink()

    async def test_cell_edit_updates_data(self):
        """Test that editing a cell updates the underlying data."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                # Get the table editor
                editor = app.query_one("#editor-TestScope", TableEditor)

                # Directly update the cell value (simulating the edit workflow)
                editor.update_cell_value("nominal", "Value", 99.0)
                await pilot.pause()

                # Verify the data was updated
                power_table = app.tables["TestScope"]["power"]
                assert power_table.flat_data["nominal"] == 99.0
                assert power_table.modified is True
        finally:
            toml_path.unlink()

    async def test_edit_cell_screen_parses_float(self):
        """Test that EditCellScreen correctly parses float values."""
        screen = EditCellScreen(
            current_value=10.0,
            value_type=float,
            row_label="nominal",
            col_label="Value",
        )

        # Test the _parse_value method
        assert screen._parse_value("99.5") == 99.5
        assert screen._parse_value("100") == 100.0
        assert screen._parse_value("-5.5") == -5.5

    async def test_edit_cell_screen_parses_int(self):
        """Test that EditCellScreen correctly parses int values."""
        screen = EditCellScreen(
            current_value=10,
            value_type=int,
            row_label="nominal",
            col_label="Value",
        )

        # Test the _parse_value method
        assert screen._parse_value("99") == 99
        assert screen._parse_value("-5") == -5

    async def test_edit_cell_screen_parses_bool(self):
        """Test that EditCellScreen correctly parses bool values."""
        screen = EditCellScreen(
            current_value=True,
            value_type=bool,
            row_label="nominal",
            col_label="Value",
        )

        # Test the _parse_value method
        assert screen._parse_value("true") is True
        assert screen._parse_value("True") is True
        assert screen._parse_value("1") is True
        assert screen._parse_value("yes") is True
        assert screen._parse_value("false") is False
        assert screen._parse_value("False") is False
        assert screen._parse_value("0") is False
        assert screen._parse_value("no") is False


class TestSaveAndQuit:
    """Tests for save and quit functionality."""

    async def test_has_unsaved_changes_detection(self):
        """Test that unsaved changes are detected."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                # Initially no unsaved changes
                assert app._has_unsaved_changes() is False

                # Modify a cell
                editor = app.query_one("#editor-TestScope", TableEditor)
                editor.update_cell_value("nominal", "Value", 99.0)
                await pilot.pause()

                # Now there should be unsaved changes
                assert app._has_unsaved_changes() is True
        finally:
            toml_path.unlink()

    async def test_save_clears_modified_flag(self):
        """Test that saving clears the modified flag."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                # Modify a cell
                editor = app.query_one("#editor-TestScope", TableEditor)
                editor.update_cell_value("nominal", "Value", 99.0)
                await pilot.pause()

                assert app._has_unsaved_changes() is True

                # Save changes
                app._save_changes()
                await pilot.pause()

                # Modified flag should be cleared
                assert app._has_unsaved_changes() is False

                # Verify the file was updated
                import tomllib

                with toml_path.open("rb") as f:
                    saved_data = tomllib.load(f)
                assert saved_data["TestScope"]["model"]["power"]["nominal"] == 99.0
        finally:
            toml_path.unlink()

    async def test_save_action(self):
        """Test the save action (pressing 's')."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                # Modify a cell
                editor = app.query_one("#editor-TestScope", TableEditor)
                editor.update_cell_value("nominal", "Value", 99.0)
                await pilot.pause()

                # Press 's' to save
                await pilot.press("s")
                await pilot.pause()

                # Verify changes were saved
                assert app._has_unsaved_changes() is False
        finally:
            toml_path.unlink()


class TestTableEditor:
    """Tests for TableEditor widget."""

    async def test_table_editor_displays_data(self):
        """Test that TableEditor displays table data correctly."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                editor = app.query_one("#editor-TestScope", TableEditor)

                # Check that the editor has data loaded
                assert editor.table_data is not None
                assert editor._row_labels is not None
                assert editor._col_labels is not None
        finally:
            toml_path.unlink()

    async def test_table_editor_format_value(self):
        """Test value formatting in TableEditor."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                editor = app.query_one("#editor-TestScope", TableEditor)

                # Test formatting
                assert editor._format_value(10.0) == "10"  # Integer-like float
                assert editor._format_value(10.5) == "10.5"
                assert editor._format_value(None) == ""
                assert editor._format_value("test") == "test"
        finally:
            toml_path.unlink()


class TestConfirmQuitScreen:
    """Tests for ConfirmQuitScreen."""

    async def test_confirm_quit_screen_composition(self):
        """Test that ConfirmQuitScreen composes correctly."""
        screen = ConfirmQuitScreen()

        # Create a minimal app to test the screen
        from textual.app import App

        class TestApp(App):
            pass

        app = TestApp()
        async with app.run_test(size=(80, 24)) as pilot:
            # Push the screen
            app.push_screen(screen)
            await pilot.pause()

            # The screen should be active
            assert app.screen is screen


class TestMultiDimensionalTable:
    """Tests for multi-dimensional table handling."""

    async def test_2d_table_display(self):
        """Test that 2D tables are displayed correctly."""
        project = create_test_project()
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {"nominal": 10.0, "safe": 5.0},
                    "matrix": {
                        "nominal,initial": 1.0,
                        "nominal,cruise": 2.0,
                        "safe,initial": 3.0,
                        "safe,cruise": 4.0,
                    },
                },
            },
        }
        toml_path = create_toml_file(toml_data)

        try:
            app = VeriqEditApp(toml_path, project)
            async with app.run_test(size=(120, 40)) as pilot:
                # Switch to the matrix table
                app._load_table_in_editor("TestScope", "matrix")
                await pilot.pause()

                # Check the table data
                matrix_table = app.tables["TestScope"]["matrix"]
                assert matrix_table.dimensions == 2
                assert matrix_table.row_labels({}) == ["nominal", "safe"]
                assert matrix_table.column_labels({}) == ["initial", "cruise"]
        finally:
            toml_path.unlink()
