"""Graph module providing dependency graph abstractions.

This module contains:
- DependencyGraph[T]: A generic, immutable directed acyclic graph
- topological_sort: Algorithm for ordering nodes by dependencies
"""

from ._algorithms import topological_sort
from ._dependency_graph import DependencyGraph

__all__ = ["DependencyGraph", "topological_sort"]
