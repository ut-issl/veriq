"""Step 1: Your First Project.

This example demonstrates the basic structure of a veriq project
with a single scope and model.
"""

from pydantic import BaseModel

import veriq as vq

# Create a project (like a workbook)
project = vq.Project("MySatellite")

# Create a scope (like a sheet)
power = vq.Scope("Power")
project.add_scope(power)


# Define a model (input cells)
@power.root_model()
class PowerModel(BaseModel):
    battery_capacity: float  # in Watt-hours
    solar_panel_area: float  # in square meters
