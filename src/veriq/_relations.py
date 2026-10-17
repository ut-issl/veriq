from __future__ import annotations

from ._models import Requirement


def depends(requirement: Requirement) -> None:
    parent = Requirement.current()

    parent.depends_on.append(requirement)
