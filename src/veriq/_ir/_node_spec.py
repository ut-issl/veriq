"""Node specification for computation graphs."""

from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from veriq._path import ProjectPath


class NodeKind(StrEnum):
    """The kind of node in the computation graph."""

    MODEL = auto()  # Input data from model (leaf values)
    CALCULATION = auto()  # Computed value
    VERIFICATION = auto()  # Verification check (returns bool or Table[K, bool])


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """Specification of a computation node.

    This is a pure, immutable data structure describing what a node does,
    without any behavior or side effects. It serves as the intermediate
    representation between user-facing API and the evaluation engine.

    Attributes:
        id: Unique identifier (ProjectPath) for this node.
        kind: Whether this is a MODEL, CALCULATION, or VERIFICATION node.
        dependencies: Set of node IDs this node depends on (leaf-level paths).
        output_type: The Python type of this node's output.
        compute_fn: Function to compute the value. None for MODEL nodes.
        param_mapping: Maps function parameter names to dependency ProjectPaths.
            This is the high-level mapping before leaf expansion.
        metadata: Optional metadata (e.g., xfail flag, assumed verifications).

    Example:
        A calculation node that computes power from voltage and current:

        >>> NodeSpec(
        ...     id=ProjectPath("Power", CalcPath("@compute_power", ())),
        ...     kind=NodeKind.CALCULATION,
        ...     dependencies=frozenset({
        ...         ProjectPath("Power", ModelPath("$", (AttributePart("voltage"),))),
        ...         ProjectPath("Power", ModelPath("$", (AttributePart("current"),))),
        ...     }),
        ...     output_type=float,
        ...     compute_fn=lambda voltage, current: voltage * current,
        ...     param_mapping={
        ...         "voltage": ProjectPath("Power", ModelPath("$", (AttributePart("voltage"),))),
        ...         "current": ProjectPath("Power", ModelPath("$", (AttributePart("current"),))),
        ...     },
        ... )

    """

    id: ProjectPath
    kind: NodeKind
    dependencies: frozenset[ProjectPath]
    output_type: type
    compute_fn: Callable[..., Any] | None = None
    param_mapping: dict[str, ProjectPath] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_input(self) -> bool:
        """Check if this is an input node (MODEL kind with no dependencies)."""
        return self.kind == NodeKind.MODEL and len(self.dependencies) == 0

    def __hash__(self) -> int:
        """Hash based on the node ID."""
        return hash(self.id)
