"""Generate / refresh per-scope input TOML files from model defaults.

SSOT: the scope's root model is the single source of schema. ``scaffold_input``
materialises each scope's own ``input`` file from that schema's defaults. For an
existing file it preserves current values and comments (add-missing), so the
data file stays the single source of input values.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import tomli_w

from ._default import default
from ._toml_edit import dumps_toml, merge_into_document, parse_toml_preserving
from ._update import update_input_data

if TYPE_CHECKING:
    from pathlib import Path

    from ._models import Project


@dataclass(frozen=True, slots=True)
class ScopeScaffold:
    """Outcome of scaffolding one scope's input file."""

    scope: str
    path: Path
    created: bool
    updated: bool
    warnings: tuple[str, ...] = ()


def scaffold_input(
    project: Project,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
) -> list[ScopeScaffold]:
    """Generate or refresh each scope's ``input`` TOML from model defaults.

    Only scopes that declare an ``input`` path are scaffolded.

    - New file: written from the root model's defaults.
    - Existing file (add-missing, default): existing values and comments are
      preserved; missing fields are added from defaults.
    - ``overwrite=True``: existing file is reset to defaults.
    - ``dry_run=True``: nothing is written; results still describe the changes.

    Args:
        project: The project whose scopes' input files to scaffold.
        overwrite: Reset existing files to defaults instead of merging.
        dry_run: Compute results without writing any file.

    Returns:
        One ScopeScaffold per scope that declares an input path.

    """
    results: list[ScopeScaffold] = []
    for scope_name, scope in project.scopes.items():
        target = scope.input_path
        if target is None:
            continue

        defaults = default(scope.get_root_model()).model_dump()

        if target.exists() and not overwrite:
            existing = tomllib.loads(target.read_text())
            update = update_input_data(defaults, existing)
            document = parse_toml_preserving(target.read_text())
            merge_into_document(document, defaults, existing)
            content = dumps_toml(document)
            warnings = tuple(w.message for w in update.warnings)
            created = False
        else:
            content = tomli_w.dumps(defaults)
            warnings = ()
            created = not target.exists()

        updated = not target.exists() or content != target.read_text()
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

        results.append(
            ScopeScaffold(
                scope=scope_name,
                path=target,
                created=created,
                updated=updated,
                warnings=warnings,
            ),
        )

    return results
