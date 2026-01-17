"""Intermediate Representation (IR) module for veriq.

This module provides pure data structures for representing computation graphs
independent of the user-facing API. The IR serves as a bridge between:
- User-facing layer (Project, Scope, decorators)
- Core evaluation engine

Key types:
- NodeKind: Enum for node types (MODEL, CALCULATION, VERIFICATION)
- NodeSpec: Specification of a single computation node
- GraphSpec: Collection of NodeSpecs with metadata
- build_graph_spec: Function to build IR from user-facing Project
"""

from ._builder import build_graph_spec
from ._graph_spec import GraphSpec
from ._node_spec import NodeKind, NodeSpec

__all__ = ["GraphSpec", "NodeKind", "NodeSpec", "build_graph_spec"]
