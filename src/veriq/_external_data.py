"""ExternalData abstract base class and built-in implementations.

This module provides the foundation for referencing external data sources
(files, URLs, S3, databases, etc.) with checksum-based reproducibility tracking.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 - Pydantic requires Path at runtime for field validation
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator

from ._context import get_input_base_dir

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Self


class ExternalData(BaseModel, ABC):
    """Abstract base for external data references.

    Subclasses must implement:
    - _compute_checksum(): Compute checksum (fetch data as needed)

    Subclasses may optionally override:
    - _on_validated(): Called after checksum validation succeeds (for caching)

    The framework handles:
    - Checksum storage/comparison in TOML
    - User warnings on data changes

    Users receive the ExternalData subclass object in calculations and
    access data via subclass-specific methods (e.g., FileRef.path, S3Ref.get_data()).

    Using BaseModel (not dataclass) ensures native Pydantic serialization
    and JSON schema generation work correctly.
    """

    model_config = ConfigDict(frozen=True)

    # Framework-managed field (not user-provided initially)
    checksum: str | None = None

    @abstractmethod
    def _compute_checksum(self) -> str:
        """Internal: Compute checksum for the external data.

        Called by veriq framework for validation.
        Implementor decides how to fetch and hash data.
        Can stream for large files, or fetch + cache for remote resources.

        Must return deterministic hash: "algorithm:hexdigest" (e.g., "sha256:abc123...")
        """
        ...

    def _on_validated(self) -> None:
        """Called after checksum validation succeeds.

        Subclasses can override to cache data fetched during _compute_checksum().
        Default: do nothing.
        """

    def _validate(self) -> tuple[bool, str]:
        """Internal: Compute checksum and compare with stored.

        Returns: (is_valid, computed_checksum)
        """
        computed = self._compute_checksum()
        is_valid = self.checksum is None or self.checksum == computed
        if is_valid:
            self._on_validated()
        return (is_valid, computed)


class FileRef(ExternalData):
    """Reference to a local file.

    Streams file for checksum - doesn't load entire file into memory.
    User accesses data via `path` attribute.

    Relative paths are resolved against the base directory set via
    `input_base_dir()` context manager (typically the TOML file's directory).

    Example:
        # In model definition
        class MyModel(BaseModel):
            config_file: FileRef

        # In calculation
        @scope.calculation()
        def process(config_file: Annotated[FileRef, vq.Ref("$.config_file")]) -> Result:
            data = config_file.path.read_bytes()
            return process_data(data)

        # In TOML
        [Scope.model.config_file]
        path = "data/config.json"
        checksum = "sha256:abc123..."  # Added by veriq after first run

    """

    model_config = ConfigDict(frozen=True, validate_default=True)

    path: Path

    @model_validator(mode="after")
    def _resolve_relative_path(self) -> Self:
        """Resolve relative paths against the base directory from context."""
        if not self.path.is_absolute():
            base_dir = get_input_base_dir()
            if base_dir is not None:
                # Use object.__setattr__ since the model is frozen
                object.__setattr__(self, "path", base_dir / self.path)
        return self

    def _compute_checksum(self) -> str:
        """Compute SHA256 checksum by streaming the file."""
        h = hashlib.sha256()
        with self.path.open("rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return f"sha256:{h.hexdigest()}"


# =============================================================================
# Checksum Validation
# =============================================================================


@dataclass(frozen=True, slots=True)
class ChecksumValidationEntry:
    """Result of validating a single ExternalData instance."""

    path: str  # Path within model (e.g., "$.config_file")
    scope: str  # Scope name
    external_data: ExternalData  # The validated ExternalData instance
    stored_checksum: str | None  # Checksum from TOML (None if first run)
    computed_checksum: str  # Newly computed checksum
    is_new: bool  # True if no stored checksum (first run)
    is_valid: bool  # True if checksums match or is_new


@dataclass(frozen=True, slots=True)
class ChecksumValidationResult:
    """Result of validating all ExternalData in model data."""

    entries: tuple[ChecksumValidationEntry, ...]

    @property
    def has_new_checksums(self) -> bool:
        """True if any ExternalData has no stored checksum."""
        return any(e.is_new for e in self.entries)

    @property
    def has_mismatches(self) -> bool:
        """True if any ExternalData has a checksum mismatch."""
        return any(not e.is_valid and not e.is_new for e in self.entries)

    @property
    def new_entries(self) -> tuple[ChecksumValidationEntry, ...]:
        """ExternalData entries with no stored checksum (first run)."""
        return tuple(e for e in self.entries if e.is_new)

    @property
    def mismatched_entries(self) -> tuple[ChecksumValidationEntry, ...]:
        """ExternalData entries with checksum mismatch."""
        return tuple(e for e in self.entries if not e.is_valid and not e.is_new)

    @property
    def valid_entries(self) -> tuple[ChecksumValidationEntry, ...]:
        """ExternalData entries with valid (matching) checksum."""
        return tuple(e for e in self.entries if e.is_valid and not e.is_new)


def _find_external_data_in_value(
    value: Any,
    path_prefix: str,
) -> list[tuple[str, ExternalData]]:
    """Recursively find all ExternalData instances in a value.

    Returns list of (path, external_data) tuples.
    """
    results: list[tuple[str, ExternalData]] = []

    if isinstance(value, ExternalData):
        results.append((path_prefix, value))
    elif isinstance(value, BaseModel):
        for field_name in type(value).model_fields:
            field_value = getattr(value, field_name)
            field_path = f"{path_prefix}.{field_name}"
            results.extend(_find_external_data_in_value(field_value, field_path))
    elif isinstance(value, dict):
        for k, v in value.items():
            key_path = f"{path_prefix}[{k}]"
            results.extend(_find_external_data_in_value(v, key_path))
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            item_path = f"{path_prefix}[{i}]"
            results.extend(_find_external_data_in_value(item, item_path))

    return results


def validate_external_data(
    model_data: Mapping[str, BaseModel],
) -> ChecksumValidationResult:
    """Validate all ExternalData instances in model data.

    Walks through model data, finds all ExternalData instances,
    computes checksums, and compares with stored values.

    Args:
        model_data: Mapping from scope name to root model instance

    Returns:
        ChecksumValidationResult with validation entries for each ExternalData

    """
    entries: list[ChecksumValidationEntry] = []

    for scope_name, root_model in model_data.items():
        # Find all ExternalData in this scope
        found = _find_external_data_in_value(root_model, "$")

        for path, external_data in found:
            # Validate and compute checksum
            is_valid, computed = external_data._validate()  # noqa: SLF001
            is_new = external_data.checksum is None

            entry = ChecksumValidationEntry(
                path=path,
                scope=scope_name,
                external_data=external_data,
                stored_checksum=external_data.checksum,
                computed_checksum=computed,
                is_new=is_new,
                is_valid=is_valid,
            )
            entries.append(entry)

    return ChecksumValidationResult(entries=tuple(entries))
