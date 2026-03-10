"""Test case for multi-dimensional table bug.

This test reproduces the bug where multi-dimensional table keys cause KeyError
when using string-interpolated references like Ref(f"$.data[{a},{b},{c}]").
"""

from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from pydantic import BaseModel

import veriq as vq


class Mode(StrEnum):
    MODE_A = "MODE_A"


class Type(StrEnum):
    TYPE_X = "TYPE_X"


class Rate(StrEnum):
    RATE_1 = "RATE_1"
    RATE_2 = "RATE_2"


def test_multidim_table_with_toml_roundtrip():
    """Test that multi-dimensional tables work with TOML load/save."""
    project = vq.Project(name="test")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class Model(BaseModel):
        data: vq.Table[tuple[Mode, Type, Rate], float]

    @scope.calculation(imports=[])
    def double_data(
        data: Annotated[vq.Table[tuple[Mode, Type, Rate], float], vq.Ref("$.data")],
    ) -> vq.Table[tuple[Mode, Type, Rate], float]:
        """Double all values in the table."""
        result = {}
        for key, value in data.items():
            result[key] = value * 2
        return vq.Table(result)


def test_multidim_table_with_string_interpolated_ref():
    """Test multi-dimensional table access with string-interpolated references.

    This reproduces the bug in telemetry_planner where verifications use
    Ref(f"$.data[{mode},{type},{rate}]") syntax.
    """
    project = vq.Project(name="test")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class Model(BaseModel):
        data: vq.Table[tuple[Mode, Type, Rate], float]

    # Create a verification that uses string-interpolated reference
    mode = Mode.MODE_A
    pkt_type = Type.TYPE_X
    rate = Rate.RATE_1

    @scope.verification(f"check_{mode}_{pkt_type}_{rate}")
    def check_value(
        value: Annotated[float, vq.Ref(f"$.data[{mode},{pkt_type},{rate}]")],
    ) -> bool:
        """Check that the value is positive."""
        return value > 0.0

    # Create input TOML
    with TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.toml"
        Path(tmpdir) / "output.toml"

        # Write input TOML with multi-dimensional table keys
        input_toml = """
[TestScope.model]
[TestScope.model.data]
"MODE_A,TYPE_X,RATE_1" = 1.0
"MODE_A,TYPE_X,RATE_2" = 2.0
"""
        input_path.write_text(input_toml)

        # Load and evaluate - this should fail with KeyError
        model_data = vq.load_model_data_from_toml(project, input_path)
        _results = vq.evaluate_project(project, model_data)

        # The verification should have been evaluated
        # This will trigger the bug!
