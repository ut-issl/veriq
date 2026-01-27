"""Tests for ExternalData ABC and FileRef implementation.

Phase 2: ExternalData Foundation
- ExternalData abstract base class
- FileRef built-in implementation
- Checksum validation flow
"""

import hashlib
from pathlib import Path  # noqa: TC003 - Used at runtime for pytest tmp_path fixture
from typing import Annotated

from pydantic import BaseModel, PrivateAttr

import veriq as vq
from veriq._eval import evaluate_project
from veriq._external_data import (
    ChecksumValidationResult,
    ExternalData,
    FileRef,
    validate_external_data,
)
from veriq._io import load_model_data_from_toml
from veriq._path import AttributePart, CalcPath, ModelPath, ProjectPath

# =============================================================================
# Tests for ExternalData ABC
# =============================================================================


def test_external_data_is_abstract() -> None:
    """Test that ExternalData cannot be instantiated directly."""
    import pytest

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        ExternalData()


def test_external_data_subclass_must_implement_compute_checksum() -> None:
    """Test that subclasses must implement _compute_checksum."""
    import pytest

    class IncompleteRef(ExternalData):
        path: str

    with pytest.raises(TypeError, match="_compute_checksum"):
        IncompleteRef(path="test.txt")


def test_external_data_subclass_with_compute_checksum() -> None:
    """Test that a complete subclass can be instantiated."""

    class CompleteRef(ExternalData):
        path: str

        def _compute_checksum(self) -> str:
            return "sha256:abc123"

    ref = CompleteRef(path="test.txt")
    assert ref.path == "test.txt"
    assert ref.checksum is None


def test_external_data_validate_with_no_stored_checksum() -> None:
    """Test _validate when no checksum is stored (first run)."""

    class TestRef(ExternalData):
        data: str

        def _compute_checksum(self) -> str:
            return f"sha256:{hashlib.sha256(self.data.encode()).hexdigest()}"

    ref = TestRef(data="hello")
    is_valid, computed = ref._validate()

    assert is_valid is True  # No stored checksum, so always valid
    expected_checksum = f"sha256:{hashlib.sha256(b'hello').hexdigest()}"
    assert computed == expected_checksum


def test_external_data_validate_with_matching_checksum() -> None:
    """Test _validate when checksum matches."""

    class TestRef(ExternalData):
        data: str

        def _compute_checksum(self) -> str:
            return f"sha256:{hashlib.sha256(self.data.encode()).hexdigest()}"

    expected = f"sha256:{hashlib.sha256(b'hello').hexdigest()}"
    ref = TestRef(data="hello", checksum=expected)
    is_valid, computed = ref._validate()

    assert is_valid is True
    assert computed == expected


def test_external_data_validate_with_mismatched_checksum() -> None:
    """Test _validate when checksum doesn't match."""

    class TestRef(ExternalData):
        data: str

        def _compute_checksum(self) -> str:
            return f"sha256:{hashlib.sha256(self.data.encode()).hexdigest()}"

    wrong_checksum = "sha256:wrong"
    ref = TestRef(data="hello", checksum=wrong_checksum)
    is_valid, computed = ref._validate()

    assert is_valid is False
    expected = f"sha256:{hashlib.sha256(b'hello').hexdigest()}"
    assert computed == expected


def test_external_data_on_validated_called_when_valid() -> None:
    """Test that _on_validated is called when validation succeeds."""
    callback_called = []

    class TestRef(ExternalData):
        data: str

        def _compute_checksum(self) -> str:
            return "sha256:abc"

        def _on_validated(self) -> None:
            callback_called.append(True)

    ref = TestRef(data="hello")
    ref._validate()

    assert len(callback_called) == 1


def test_external_data_on_validated_not_called_when_invalid() -> None:
    """Test that _on_validated is NOT called when validation fails."""
    callback_called = []

    class TestRef(ExternalData):
        data: str

        def _compute_checksum(self) -> str:
            return "sha256:abc"

        def _on_validated(self) -> None:
            callback_called.append(True)

    ref = TestRef(data="hello", checksum="sha256:wrong")
    ref._validate()

    assert len(callback_called) == 0


# =============================================================================
# Tests for FileRef
# =============================================================================


def test_fileref_compute_checksum(tmp_path: Path) -> None:
    """Test that FileRef computes correct SHA256 checksum."""
    test_file = tmp_path / "test.txt"
    test_content = b"Hello, World!"
    test_file.write_bytes(test_content)

    ref = FileRef(path=test_file)
    checksum = ref._compute_checksum()

    expected = f"sha256:{hashlib.sha256(test_content).hexdigest()}"
    assert checksum == expected


def test_fileref_compute_checksum_streams_large_file(tmp_path: Path) -> None:
    """Test that FileRef streams large files (doesn't load all into memory)."""
    test_file = tmp_path / "large.bin"
    # Create a file larger than typical chunk size
    test_content = b"x" * 100_000
    test_file.write_bytes(test_content)

    ref = FileRef(path=test_file)
    checksum = ref._compute_checksum()

    expected = f"sha256:{hashlib.sha256(test_content).hexdigest()}"
    assert checksum == expected


def test_fileref_validate_first_run(tmp_path: Path) -> None:
    """Test FileRef validation on first run (no stored checksum)."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"content")

    ref = FileRef(path=test_file)
    is_valid, computed = ref._validate()

    assert is_valid is True
    assert computed.startswith("sha256:")


def test_fileref_validate_matching_checksum(tmp_path: Path) -> None:
    """Test FileRef validation with matching checksum."""
    test_file = tmp_path / "test.txt"
    content = b"content"
    test_file.write_bytes(content)

    expected = f"sha256:{hashlib.sha256(content).hexdigest()}"
    ref = FileRef(path=test_file, checksum=expected)
    is_valid, computed = ref._validate()

    assert is_valid is True
    assert computed == expected


def test_fileref_validate_mismatched_checksum(tmp_path: Path) -> None:
    """Test FileRef validation with mismatched checksum."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"content")

    ref = FileRef(path=test_file, checksum="sha256:wrong")
    is_valid, _computed = ref._validate()

    assert is_valid is False


def test_fileref_path_accessible(tmp_path: Path) -> None:
    """Test that users can access FileRef.path to read the file."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"Hello")

    ref = FileRef(path=test_file)

    # User should be able to access path and read file
    assert ref.path == test_file
    assert ref.path.read_bytes() == b"Hello"


# =============================================================================
# Tests for FileRef in Model
# =============================================================================


def test_fileref_as_model_field(tmp_path: Path) -> None:
    """Test that FileRef can be used as a Pydantic model field."""
    test_file = tmp_path / "config.txt"
    test_file.write_bytes(b"config data")

    class TestModel(BaseModel):
        config: FileRef
        value: float

    model = TestModel(config=FileRef(path=test_file), value=1.0)

    assert model.config.path == test_file
    assert model.value == 1.0


def test_fileref_in_veriq_model(tmp_path: Path) -> None:
    """Test that FileRef works in a veriq scope model."""
    test_file = tmp_path / "data.bin"
    test_file.write_bytes(b"binary data")

    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        data_file: FileRef
        scale: float

    model_data = {
        "TestScope": TestModel(
            data_file=FileRef(path=test_file),
            scale=2.0,
        ),
    }

    result = evaluate_project(project, model_data)

    # Check that FileRef is stored as a leaf value
    file_path = ProjectPath(
        scope="TestScope",
        path=ModelPath(root="$", parts=(AttributePart("data_file"),)),
    )
    assert result.has_value(file_path)
    assert isinstance(result.get_value(file_path), FileRef)
    assert result.get_value(file_path).path == test_file


def test_fileref_in_calculation(tmp_path: Path) -> None:
    """Test that FileRef can be used in calculations."""
    test_file = tmp_path / "numbers.txt"
    test_file.write_text("10\n20\n30")

    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        numbers_file: FileRef

    @scope.calculation()
    def sum_numbers(
        numbers_file: Annotated[FileRef, vq.Ref("$.numbers_file")],
    ) -> float:
        # User reads file via path
        content = numbers_file.path.read_text()
        numbers = [int(line) for line in content.strip().split("\n")]
        return float(sum(numbers))

    model_data = {
        "TestScope": TestModel(numbers_file=FileRef(path=test_file)),
    }

    result = evaluate_project(project, model_data)

    calc_path = ProjectPath(
        scope="TestScope",
        path=CalcPath(root="@sum_numbers", parts=()),
    )
    assert result.get_value(calc_path) == 60.0


def test_fileref_toml_roundtrip(tmp_path: Path) -> None:
    """Test that FileRef can be loaded from TOML."""
    # Create a data file
    data_file = tmp_path / "data.txt"
    data_file.write_bytes(b"test data")

    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        config_file: FileRef
        value: float

    # Create TOML with FileRef
    toml_content = f"""
[TestScope.model]
value = 42.0

[TestScope.model.config_file]
path = "{data_file}"
"""
    toml_file = tmp_path / "input.toml"
    toml_file.write_text(toml_content)

    model_data = load_model_data_from_toml(project, toml_file)

    assert "TestScope" in model_data
    assert isinstance(model_data["TestScope"].config_file, FileRef)  # ty: ignore[unresolved-attribute]
    assert model_data["TestScope"].config_file.path == data_file  # ty: ignore[unresolved-attribute]
    assert model_data["TestScope"].value == 42.0  # ty: ignore[unresolved-attribute]


def test_fileref_toml_with_checksum(tmp_path: Path) -> None:
    """Test that FileRef loads checksum from TOML."""
    data_file = tmp_path / "data.txt"
    content = b"test data"
    data_file.write_bytes(content)
    checksum = f"sha256:{hashlib.sha256(content).hexdigest()}"

    project = vq.Project(name="TestProject")
    scope = vq.Scope(name="TestScope")
    project.add_scope(scope)

    @scope.root_model()
    class TestModel(BaseModel):
        config_file: FileRef
        value: float

    toml_content = f"""
[TestScope.model]
value = 42.0

[TestScope.model.config_file]
path = "{data_file}"
checksum = "{checksum}"
"""
    toml_file = tmp_path / "input.toml"
    toml_file.write_text(toml_content)

    model_data = load_model_data_from_toml(project, toml_file)

    assert model_data["TestScope"].config_file.checksum == checksum  # ty: ignore[unresolved-attribute]


# =============================================================================
# Tests for User-Defined ExternalData (Plugin Pattern)
# =============================================================================


def test_user_defined_external_data_with_caching() -> None:
    """Test that users can define their own ExternalData with caching."""

    class MockS3Ref(ExternalData):
        """Mock S3 reference that caches data after validation."""

        bucket: str
        key: str
        _cached_data: bytes | None = PrivateAttr(default=None)
        _fetch_count: int = PrivateAttr(default=0)

        def _compute_checksum(self) -> str:
            # Simulate fetching data
            self._fetch_count += 1
            data = f"data from {self.bucket}/{self.key}".encode()
            self._cached_data = data
            return f"sha256:{hashlib.sha256(data).hexdigest()}"

        def get_data(self) -> bytes:
            if self._cached_data is None:
                msg = "Data not available. Run validation first."
                raise RuntimeError(msg)
            return self._cached_data

    ref = MockS3Ref(bucket="my-bucket", key="data.txt")

    # First validation fetches data
    is_valid, _checksum = ref._validate()
    assert is_valid is True
    assert ref._fetch_count == 1

    # Data is now cached
    data = ref.get_data()
    assert data == b"data from my-bucket/data.txt"

    # No additional fetch needed
    assert ref._fetch_count == 1


# =============================================================================
# Tests for validate_external_data Function
# =============================================================================


def test_validate_external_data_empty_model_data() -> None:
    """Test validation with no model data."""
    result = validate_external_data({})

    assert isinstance(result, ChecksumValidationResult)
    assert len(result.entries) == 0
    assert not result.has_new_checksums
    assert not result.has_mismatches


def test_validate_external_data_no_external_data_fields() -> None:
    """Test validation with model that has no ExternalData fields."""

    class SimpleModel(BaseModel):
        value: float
        name: str

    model_data = {"Scope1": SimpleModel(value=1.0, name="test")}
    result = validate_external_data(model_data)

    assert len(result.entries) == 0
    assert not result.has_new_checksums
    assert not result.has_mismatches


def test_validate_external_data_first_run_no_checksum(tmp_path: Path) -> None:
    """Test validation on first run (no stored checksum)."""
    test_file = tmp_path / "data.txt"
    test_file.write_bytes(b"test content")

    class TestModel(BaseModel):
        data_file: FileRef

    # First run: no checksum stored
    model_data = {"TestScope": TestModel(data_file=FileRef(path=test_file))}
    result = validate_external_data(model_data)

    assert len(result.entries) == 1
    assert result.has_new_checksums
    assert not result.has_mismatches

    entry = result.entries[0]
    assert entry.path == "$.data_file"
    assert entry.scope == "TestScope"
    assert entry.is_new is True
    assert entry.is_valid is True
    assert entry.stored_checksum is None
    assert entry.computed_checksum.startswith("sha256:")


def test_validate_external_data_matching_checksum(tmp_path: Path) -> None:
    """Test validation with matching checksum."""
    test_file = tmp_path / "data.txt"
    content = b"test content"
    test_file.write_bytes(content)
    checksum = f"sha256:{hashlib.sha256(content).hexdigest()}"

    class TestModel(BaseModel):
        data_file: FileRef

    model_data = {"TestScope": TestModel(data_file=FileRef(path=test_file, checksum=checksum))}
    result = validate_external_data(model_data)

    assert len(result.entries) == 1
    assert not result.has_new_checksums
    assert not result.has_mismatches

    entry = result.entries[0]
    assert entry.is_new is False
    assert entry.is_valid is True
    assert entry.stored_checksum == checksum
    assert entry.computed_checksum == checksum


def test_validate_external_data_mismatched_checksum(tmp_path: Path) -> None:
    """Test validation with mismatched checksum."""
    test_file = tmp_path / "data.txt"
    test_file.write_bytes(b"new content")

    class TestModel(BaseModel):
        data_file: FileRef

    # Stored checksum doesn't match current file content
    model_data = {"TestScope": TestModel(data_file=FileRef(path=test_file, checksum="sha256:old_checksum"))}
    result = validate_external_data(model_data)

    assert len(result.entries) == 1
    assert not result.has_new_checksums
    assert result.has_mismatches

    entry = result.entries[0]
    assert entry.is_new is False
    assert entry.is_valid is False
    assert entry.stored_checksum == "sha256:old_checksum"
    assert entry.computed_checksum != "sha256:old_checksum"


def test_validate_external_data_multiple_files(tmp_path: Path) -> None:
    """Test validation with multiple ExternalData fields."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"
    content1 = b"content 1"
    content2 = b"content 2"
    file1.write_bytes(content1)
    file2.write_bytes(content2)
    checksum1 = f"sha256:{hashlib.sha256(content1).hexdigest()}"

    class TestModel(BaseModel):
        config: FileRef
        data: FileRef

    model_data = {
        "TestScope": TestModel(
            config=FileRef(path=file1, checksum=checksum1),  # Valid
            data=FileRef(path=file2),  # New (no checksum)
        ),
    }
    result = validate_external_data(model_data)

    assert len(result.entries) == 2
    assert result.has_new_checksums
    assert not result.has_mismatches

    # Check properties
    assert len(result.new_entries) == 1
    assert len(result.valid_entries) == 1
    assert len(result.mismatched_entries) == 0


def test_validate_external_data_nested_model(tmp_path: Path) -> None:
    """Test validation with ExternalData in nested Pydantic model."""
    test_file = tmp_path / "config.json"
    test_file.write_bytes(b'{"key": "value"}')

    class ConfigSection(BaseModel):
        config_file: FileRef
        enabled: bool

    class RootModel(BaseModel):
        section: ConfigSection
        name: str

    model_data = {
        "TestScope": RootModel(
            section=ConfigSection(config_file=FileRef(path=test_file), enabled=True),
            name="test",
        ),
    }
    result = validate_external_data(model_data)

    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.path == "$.section.config_file"
    assert entry.is_new is True


def test_validate_external_data_multiple_scopes(tmp_path: Path) -> None:
    """Test validation across multiple scopes."""
    file1 = tmp_path / "scope1.txt"
    file2 = tmp_path / "scope2.txt"
    file1.write_bytes(b"scope 1 data")
    file2.write_bytes(b"scope 2 data")

    class Scope1Model(BaseModel):
        file: FileRef

    class Scope2Model(BaseModel):
        file: FileRef

    model_data = {
        "Scope1": Scope1Model(file=FileRef(path=file1)),
        "Scope2": Scope2Model(file=FileRef(path=file2)),
    }
    result = validate_external_data(model_data)

    assert len(result.entries) == 2
    scopes = {e.scope for e in result.entries}
    assert scopes == {"Scope1", "Scope2"}


def test_validate_external_data_mixed_results(tmp_path: Path) -> None:
    """Test validation with mix of new, valid, and mismatched checksums."""
    file_new = tmp_path / "new.txt"
    file_valid = tmp_path / "valid.txt"
    file_mismatch = tmp_path / "mismatch.txt"

    content_valid = b"valid content"
    file_new.write_bytes(b"new file")
    file_valid.write_bytes(content_valid)
    file_mismatch.write_bytes(b"changed content")

    checksum_valid = f"sha256:{hashlib.sha256(content_valid).hexdigest()}"

    class TestModel(BaseModel):
        file_new: FileRef
        file_valid: FileRef
        file_mismatch: FileRef

    model_data = {
        "TestScope": TestModel(
            file_new=FileRef(path=file_new),  # New
            file_valid=FileRef(path=file_valid, checksum=checksum_valid),  # Valid
            file_mismatch=FileRef(path=file_mismatch, checksum="sha256:old"),  # Mismatch
        ),
    }
    result = validate_external_data(model_data)

    assert len(result.entries) == 3
    assert result.has_new_checksums
    assert result.has_mismatches
    assert len(result.new_entries) == 1
    assert len(result.valid_entries) == 1
    assert len(result.mismatched_entries) == 1


def test_validate_external_data_on_validated_called() -> None:
    """Test that _on_validated is called during validation."""
    validated_paths: list[str] = []

    class TrackingRef(ExternalData):
        name: str

        def _compute_checksum(self) -> str:
            return f"sha256:{hashlib.sha256(self.name.encode()).hexdigest()}"

        def _on_validated(self) -> None:
            validated_paths.append(self.name)

    class TestModel(BaseModel):
        ref1: TrackingRef
        ref2: TrackingRef

    model_data = {
        "TestScope": TestModel(
            ref1=TrackingRef(name="first"),
            ref2=TrackingRef(name="second"),
        ),
    }

    result = validate_external_data(model_data)

    # Both should be validated (new checksums)
    assert len(result.entries) == 2
    assert set(validated_paths) == {"first", "second"}
