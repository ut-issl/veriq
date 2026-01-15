"""Tests for the schema command to ensure it generates correct JSON schemas."""

import json
import subprocess
import tomllib
from enum import StrEnum
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

import veriq as vq
from veriq._table import Table


def test_schema_command_restricts_table_keys(tmp_path: Path) -> None:
    """Test that the schema command generates JSON schema that restricts Table keys."""
    # Create a minimal project with a Table field
    project_file = tmp_path / "test_project.py"
    project_code = """
from enum import StrEnum
from pydantic import BaseModel
import veriq as vq
from veriq._table import Table

class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"

class Design(BaseModel):
    power_consumption: Table[Mode, float]

project = vq.Project(name="TestProject")
scope = vq.Scope(name="Power")
project.add_scope(scope)
scope.root_model()(Design)
"""
    project_file.write_text(project_code)

    # Generate JSON schema
    schema_file = tmp_path / "schema.json"
    result = subprocess.run(
        ["uv", "run", "veriq", "schema", str(project_file), "-o", str(schema_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Schema generation failed: {result.stderr}"
    assert schema_file.exists(), "Schema file was not created"

    # Load the generated schema
    with schema_file.open() as f:
        schema = json.load(f)

    # Create a valid TOML file with only allowed keys
    valid_toml = tmp_path / "valid.toml"
    valid_toml.write_text("""
[Power.model.power_consumption]
nominal = 10.0
safe = 5.0
""")

    # Create an invalid TOML file with extra key
    invalid_toml = tmp_path / "invalid.toml"
    invalid_toml.write_text("""
[Power.model.power_consumption]
nominal = 10.0
safe = 5.0
mission = 15.0
""")

    # Load valid TOML and validate against schema
    with valid_toml.open("rb") as f:
        valid_data = tomllib.load(f)

    # Import jsonschema for validation
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed")

    # Valid data should pass
    try:
        jsonschema.validate(valid_data, schema)
    except jsonschema.ValidationError as e:
        pytest.fail(f"Valid data failed validation: {e}")

    # Invalid data should fail
    with invalid_toml.open("rb") as f:
        invalid_data = tomllib.load(f)

    with pytest.raises(jsonschema.ValidationError, match=r"mission|additional"):
        jsonschema.validate(invalid_data, schema)


def test_schema_table_has_explicit_enum_key_properties() -> None:
    """Test that JSON schema for Table fields explicitly lists allowed enum keys.

    The JSON schema should have explicit 'properties' for each enum value
    and 'additionalProperties': false to properly restrict keys.
    """

    class Mode(StrEnum):
        NOMINAL = "nominal"
        SAFE = "safe"

    class Design(BaseModel):
        power_consumption: Table[Mode, float]

    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="Power")
    project.add_scope(scope)
    scope.root_model()(Design)

    # Get the input model and its schema
    input_model = project.input_model()
    schema = input_model.model_json_schema()

    # The schema uses $defs for nested models
    # Find the Design model in $defs
    assert "$defs" in schema, "Schema should have $defs"

    # Look for the Design model definition
    design_def = None
    for def_value in schema["$defs"].values():
        if "power_consumption" in def_value.get("properties", {}):
            design_def = def_value
            break

    assert design_def is not None, "Could not find Design model in $defs"

    power_consumption_schema = design_def["properties"]["power_consumption"]

    # Verify the schema has explicit properties for each enum value
    assert "properties" in power_consumption_schema, "Table should have 'properties' in schema"
    assert set(power_consumption_schema["properties"].keys()) == {"nominal", "safe"}

    # Verify each property has the correct type
    assert power_consumption_schema["properties"]["nominal"]["type"] == "number"
    assert power_consumption_schema["properties"]["safe"]["type"] == "number"

    # Verify that additionalProperties is set to False to reject extra keys
    assert power_consumption_schema["additionalProperties"] is False

    # Verify that all keys are required
    assert set(power_consumption_schema["required"]) == {"nominal", "safe"}


def test_schema_restricts_table_keys_with_pydantic() -> None:
    """Test that Table schema restricts keys using Pydantic validation."""

    class Mode(StrEnum):
        NOMINAL = "nominal"
        SAFE = "safe"

    class Design(BaseModel):
        power_consumption: Table[Mode, float]

    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="Power")
    project.add_scope(scope)
    scope.root_model()(Design)

    # Get the input model
    input_model = project.input_model()

    # Valid data with only allowed keys
    valid_data = {
        "Power": {
            "model": {
                "power_consumption": {
                    "nominal": 10.0,
                    "safe": 5.0,
                },
            },
        },
    }

    # This should validate successfully
    instance = input_model.model_validate(valid_data)
    assert instance is not None

    # Invalid data with extra key
    invalid_data = {
        "Power": {
            "model": {
                "power_consumption": {
                    "nominal": 10.0,
                    "safe": 5.0,
                    "mission": 15.0,  # This key is not in the Mode enum
                },
            },
        },
    }

    # This should fail validation
    with pytest.raises(ValidationError):
        input_model.model_validate(invalid_data)


def test_schema_restricts_tuple_table_keys(tmp_path: Path) -> None:
    """Test that schema restricts keys for Table with tuple keys."""
    # Create a project with a tuple-keyed Table
    project_file = tmp_path / "test_tuple_table.py"
    project_code = """
from enum import StrEnum
from pydantic import BaseModel
import veriq as vq
from veriq._table import Table

class Phase(StrEnum):
    INITIAL = "initial"
    CRUISE = "cruise"

class Mode(StrEnum):
    NOMINAL = "nominal"
    SAFE = "safe"

class Design(BaseModel):
    power_matrix: Table[tuple[Phase, Mode], float]

project = vq.Project(name="TestProject")
scope = vq.Scope(name="Power")
project.add_scope(scope)
scope.root_model()(Design)
"""
    project_file.write_text(project_code)

    # Generate JSON schema
    schema_file = tmp_path / "tuple_schema.json"
    result = subprocess.run(
        ["uv", "run", "veriq", "schema", str(project_file), "-o", str(schema_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"Schema generation failed: {result.stderr}"

    # Load the schema
    with schema_file.open() as f:
        schema = json.load(f)

    # Valid TOML with correct tuple keys
    valid_toml = tmp_path / "valid_tuple.toml"
    valid_toml.write_text("""
[Power.model.power_matrix]
"initial,nominal" = 10.0
"initial,safe" = 5.0
"cruise,nominal" = 12.0
"cruise,safe" = 6.0
""")

    # Invalid TOML with extra tuple key
    invalid_toml = tmp_path / "invalid_tuple.toml"
    invalid_toml.write_text("""
[Power.model.power_matrix]
"initial,nominal" = 10.0
"initial,safe" = 5.0
"cruise,nominal" = 12.0
"cruise,safe" = 6.0
"cruise,mission" = 15.0
""")

    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed")

    # Validate valid data
    with valid_toml.open("rb") as f:
        valid_data = tomllib.load(f)

    try:
        jsonschema.validate(valid_data, schema)
    except jsonschema.ValidationError as e:
        pytest.fail(f"Valid tuple data failed validation: {e}")

    # Validate invalid data
    with invalid_toml.open("rb") as f:
        invalid_data = tomllib.load(f)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_data, schema)
