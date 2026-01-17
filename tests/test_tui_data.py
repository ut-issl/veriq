"""Tests for TUI data module."""

from enum import StrEnum, unique

import pytest
from pydantic import BaseModel

import veriq as vq
from veriq._cli.tui.data import (
    TableData,
    extract_table_fields_from_model,
    load_tables_from_toml,
    save_tables_to_toml,
)


@unique
class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"


@unique
class Phase(StrEnum):
    INITIAL = "initial"
    CRUISE = "cruise"


@unique
class Component(StrEnum):
    CPU = "cpu"
    RADIO = "radio"
    SENSOR = "sensor"


class TestTableData:
    """Tests for TableData class."""

    def test_dimensions_1d(self):
        """Test dimensions property for 1D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode,),
            value_type=float,
            flat_data={"nominal": 10.0, "safe": 5.0},
        )
        assert table_data.dimensions == 1

    def test_dimensions_2d(self):
        """Test dimensions property for 2D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode, Phase),
            value_type=float,
            flat_data={
                "nominal,initial": 10.0,
                "nominal,cruise": 15.0,
                "safe,initial": 5.0,
                "safe,cruise": 7.0,
            },
        )
        assert table_data.dimensions == 2

    def test_dimensions_3d(self):
        """Test dimensions property for 3D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Component, Mode, Phase),
            value_type=float,
            flat_data={},  # Empty for dimension test
        )
        assert table_data.dimensions == 3

    def test_row_labels_1d(self):
        """Test row labels for 1D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode,),
            value_type=float,
            flat_data={"nominal": 10.0, "safe": 5.0},
        )
        assert table_data.row_labels({}) == ["nominal", "safe"]

    def test_column_labels_1d(self):
        """Test column labels for 1D table (should be single Value column)."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode,),
            value_type=float,
            flat_data={"nominal": 10.0, "safe": 5.0},
        )
        assert table_data.column_labels({}) == ["Value"]

    def test_row_labels_2d(self):
        """Test row labels for 2D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode, Phase),
            value_type=float,
            flat_data={},
        )
        assert table_data.row_labels({}) == ["nominal", "safe"]

    def test_column_labels_2d(self):
        """Test column labels for 2D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode, Phase),
            value_type=float,
            flat_data={},
        )
        assert table_data.column_labels({}) == ["initial", "cruise"]

    def test_row_labels_3d_with_fixed_dim(self):
        """Test row labels for 3D table with first dimension fixed."""
        table_data = TableData(
            field_name="power",
            key_types=(Component, Mode, Phase),
            value_type=float,
            flat_data={},
        )
        fixed_dims = {0: Component.CPU}
        assert table_data.row_labels(fixed_dims) == ["nominal", "safe"]

    def test_column_labels_3d_with_fixed_dim(self):
        """Test column labels for 3D table with first dimension fixed."""
        table_data = TableData(
            field_name="power",
            key_types=(Component, Mode, Phase),
            value_type=float,
            flat_data={},
        )
        fixed_dims = {0: Component.CPU}
        assert table_data.column_labels(fixed_dims) == ["initial", "cruise"]

    def test_get_cell_2d(self):
        """Test getting cell value for 2D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode, Phase),
            value_type=float,
            flat_data={
                "nominal,initial": 10.0,
                "nominal,cruise": 15.0,
                "safe,initial": 5.0,
                "safe,cruise": 7.0,
            },
        )
        assert table_data.get_cell({}, "nominal", "initial") == 10.0
        assert table_data.get_cell({}, "safe", "cruise") == 7.0

    def test_get_cell_3d(self):
        """Test getting cell value for 3D table with fixed dimension."""
        table_data = TableData(
            field_name="power",
            key_types=(Component, Mode, Phase),
            value_type=float,
            flat_data={
                "cpu,nominal,initial": 10.0,
                "cpu,nominal,cruise": 15.0,
                "cpu,safe,initial": 5.0,
                "cpu,safe,cruise": 7.0,
                "radio,nominal,initial": 20.0,
                "radio,nominal,cruise": 25.0,
                "radio,safe,initial": 10.0,
                "radio,safe,cruise": 12.0,
            },
        )
        fixed_dims = {0: Component.CPU}
        assert table_data.get_cell(fixed_dims, "nominal", "initial") == 10.0
        assert table_data.get_cell(fixed_dims, "safe", "cruise") == 7.0

        fixed_dims = {0: Component.RADIO}
        assert table_data.get_cell(fixed_dims, "nominal", "initial") == 20.0

    def test_update_cell_2d(self):
        """Test updating cell value for 2D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode, Phase),
            value_type=float,
            flat_data={
                "nominal,initial": 10.0,
                "nominal,cruise": 15.0,
                "safe,initial": 5.0,
                "safe,cruise": 7.0,
            },
        )
        assert not table_data.modified
        table_data.update_cell({}, "nominal", "initial", 99.0)
        assert table_data.flat_data["nominal,initial"] == 99.0
        assert table_data.modified

    def test_update_cell_3d(self):
        """Test updating cell value for 3D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Component, Mode, Phase),
            value_type=float,
            flat_data={
                "cpu,nominal,initial": 10.0,
                "cpu,nominal,cruise": 15.0,
            },
        )
        fixed_dims = {0: Component.CPU}
        table_data.update_cell(fixed_dims, "nominal", "initial", 99.0)
        assert table_data.flat_data["cpu,nominal,initial"] == 99.0
        assert table_data.modified

    def test_get_fixed_dimension_options_2d(self):
        """Test that 2D tables have no fixed dimension options."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode, Phase),
            value_type=float,
            flat_data={},
        )
        assert table_data.get_fixed_dimension_options() == []

    def test_get_fixed_dimension_options_3d(self):
        """Test fixed dimension options for 3D table."""
        table_data = TableData(
            field_name="power",
            key_types=(Component, Mode, Phase),
            value_type=float,
            flat_data={},
        )
        options = table_data.get_fixed_dimension_options()
        assert len(options) == 1
        dim_idx, enum_name, values = options[0]
        assert dim_idx == 0
        assert enum_name == "Component"
        assert values == ["cpu", "radio", "sensor"]

    def test_to_serializable(self):
        """Test conversion to serializable dict."""
        table_data = TableData(
            field_name="power",
            key_types=(Mode,),
            value_type=float,
            flat_data={"nominal": 10.0, "safe": 5.0},
        )
        result = table_data.to_serializable()
        assert result == {"nominal": 10.0, "safe": 5.0}


class TestExtractTableFields:
    """Tests for extract_table_fields_from_model function."""

    def test_simple_table_field(self):
        """Test extraction of simple table field."""

        class TestModel(BaseModel):
            power: vq.Table[Mode, float]

        fields = extract_table_fields_from_model(TestModel)
        assert len(fields) == 1
        field_path, key_types, value_type = fields[0]
        assert field_path == "power"
        assert key_types == (Mode,)
        assert value_type is float

    def test_nested_table_field(self):
        """Test extraction of table field in nested model."""

        class Inner(BaseModel):
            power: vq.Table[Mode, float]

        class Outer(BaseModel):
            inner: Inner

        fields = extract_table_fields_from_model(Outer)
        assert len(fields) == 1
        field_path, key_types, value_type = fields[0]
        assert field_path == "inner.power"
        assert key_types == (Mode,)
        assert value_type is float

    def test_2d_table_field(self):
        """Test extraction of 2D table field."""

        class TestModel(BaseModel):
            power: vq.Table[tuple[Mode, Phase], float]

        fields = extract_table_fields_from_model(TestModel)
        assert len(fields) == 1
        field_path, key_types, value_type = fields[0]
        assert field_path == "power"
        assert key_types == (Mode, Phase)
        assert value_type is float

    def test_multiple_table_fields(self):
        """Test extraction of multiple table fields."""

        class TestModel(BaseModel):
            power: vq.Table[Mode, float]
            voltage: vq.Table[Phase, int]

        fields = extract_table_fields_from_model(TestModel)
        assert len(fields) == 2
        paths = {f[0] for f in fields}
        assert paths == {"power", "voltage"}

    def test_non_table_fields_ignored(self):
        """Test that non-table fields are ignored."""

        class TestModel(BaseModel):
            name: str
            value: float
            power: vq.Table[Mode, float]

        fields = extract_table_fields_from_model(TestModel)
        assert len(fields) == 1
        assert fields[0][0] == "power"


class TestLoadAndSaveTables:
    """Tests for load_tables_from_toml and save_tables_to_toml functions."""

    @pytest.fixture
    def project_with_tables(self):
        """Create a project with table fields."""
        project = vq.Project("TestProject")
        scope = vq.Scope("TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestRootModel(BaseModel):
            power: vq.Table[Mode, float]

        return project

    def test_load_tables_from_toml(self, project_with_tables: vq.Project):
        """Test loading tables from TOML data."""
        toml_data = {
            "TestScope": {
                "model": {
                    "power": {
                        "nominal": 10.0,
                        "safe": 5.0,
                    },
                },
            },
        }

        tables = load_tables_from_toml(project_with_tables, toml_data)
        assert "TestScope" in tables
        assert "power" in tables["TestScope"]

        table_data = tables["TestScope"]["power"]
        assert table_data.field_name == "power"
        assert table_data.key_types == (Mode,)
        assert table_data.value_type is float
        assert table_data.flat_data == {"nominal": 10.0, "safe": 5.0}

    def test_save_tables_to_toml(self, project_with_tables: vq.Project):
        """Test saving modified tables back to TOML."""
        original_toml = {
            "TestScope": {
                "model": {
                    "power": {
                        "nominal": 10.0,
                        "safe": 5.0,
                    },
                },
            },
        }

        tables = load_tables_from_toml(project_with_tables, original_toml)

        # Modify the table
        tables["TestScope"]["power"].update_cell({}, "nominal", "Value", 99.0)

        # Save back
        updated_toml = save_tables_to_toml(tables, original_toml)

        assert updated_toml["TestScope"]["model"]["power"]["nominal"] == 99.0
        assert updated_toml["TestScope"]["model"]["power"]["safe"] == 5.0

    def test_load_empty_scope(self, project_with_tables: vq.Project):
        """Test loading when scope has no model data."""
        toml_data = {}

        tables = load_tables_from_toml(project_with_tables, toml_data)
        # Should return empty dict for scope with no model data in TOML
        assert tables == {} or "TestScope" not in tables or not tables.get("TestScope")

    def test_load_scope_without_tables(self):
        """Test loading scope that has no table fields."""
        project = vq.Project("TestProject")
        scope = vq.Scope("TestScope")
        project.add_scope(scope)

        @scope.root_model()
        class TestRootModel(BaseModel):
            name: str
            value: float

        toml_data = {
            "TestScope": {
                "model": {
                    "name": "test",
                    "value": 1.0,
                },
            },
        }

        tables = load_tables_from_toml(project, toml_data)
        # No tables should be extracted
        assert tables == {} or "TestScope" not in tables or not tables.get("TestScope")
