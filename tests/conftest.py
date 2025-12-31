"""Pytest configuration and shared fixtures for ChronoClean tests."""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

from chronoclean.config.schema import (
    ChronoCleanConfig,
    FolderTagsConfig,
    GeneralConfig,
    RenamingConfig,
    SortingConfig,
)
from chronoclean.core.models import DateSource, FileRecord, FileType, ScanResult


# =============================================================================
# Test Isolation
# =============================================================================


@pytest.fixture(autouse=True)
def isolate_working_directory(tmp_path, monkeypatch):
    """Automatically isolate all tests in a temporary directory.
    
    This prevents tests from creating artifacts (like .chronoclean/) 
    in the project directory. All tests run with tmp_path as cwd.
    """
    monkeypatch.chdir(tmp_path)


# =============================================================================
# Path Fixtures
# =============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    path = Path(tempfile.mkdtemp(prefix="chronoclean_test_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def source_dir(temp_dir: Path) -> Path:
    """Create a source directory within temp_dir."""
    source = temp_dir / "source"
    source.mkdir()
    return source


@pytest.fixture
def destination_dir(temp_dir: Path) -> Path:
    """Create a destination directory within temp_dir."""
    dest = temp_dir / "destination"
    dest.mkdir()
    return dest


# =============================================================================
# File Fixtures
# =============================================================================


@pytest.fixture
def sample_jpg(source_dir: Path) -> Path:
    """Create a sample JPG file (empty, no EXIF)."""
    file_path = source_dir / "sample.jpg"
    file_path.write_bytes(b"\xFF\xD8\xFF\xE0")  # Minimal JPEG header
    return file_path


@pytest.fixture
def sample_png(source_dir: Path) -> Path:
    """Create a sample PNG file."""
    file_path = source_dir / "sample.png"
    # Minimal PNG header
    file_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    return file_path


@pytest.fixture
def sample_video(source_dir: Path) -> Path:
    """Create a sample video file."""
    file_path = source_dir / "sample.mp4"
    file_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return file_path


@pytest.fixture
def hidden_file(source_dir: Path) -> Path:
    """Create a hidden file."""
    file_path = source_dir / ".hidden.jpg"
    file_path.write_bytes(b"\xFF\xD8\xFF\xE0")
    return file_path


# =============================================================================
# Directory Structure Fixtures
# =============================================================================


@pytest.fixture
def mock_photo_library(source_dir: Path) -> Path:
    """
    Create a mock photo library structure.
    
    Structure:
        source/
            Paris 2024/
                IMG_001.jpg
                IMG_002.jpg
            tosort/
                photo.jpg
            DCIM/
                100APPLE/
                    IMG_0001.jpg
            2023-12-25 Christmas/
                family.jpg
    """
    # Paris 2024 folder
    paris = source_dir / "Paris 2024"
    paris.mkdir()
    (paris / "IMG_001.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")
    (paris / "IMG_002.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")
    
    # tosort folder (should be ignored for tagging)
    tosort = source_dir / "tosort"
    tosort.mkdir()
    (tosort / "photo.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")
    
    # DCIM folder structure
    dcim = source_dir / "DCIM" / "100APPLE"
    dcim.mkdir(parents=True)
    (dcim / "IMG_0001.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")
    
    # Date-named folder
    christmas = source_dir / "2023-12-25 Christmas"
    christmas.mkdir()
    (christmas / "family.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")
    
    return source_dir


@pytest.fixture
def nested_folders(source_dir: Path) -> Path:
    """Create nested folder structure for recursive testing."""
    level1 = source_dir / "level1"
    level2 = level1 / "level2"
    level3 = level2 / "level3"
    level3.mkdir(parents=True)
    
    (source_dir / "root.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")
    (level1 / "l1.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")
    (level2 / "l2.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")
    (level3 / "l3.jpg").write_bytes(b"\xFF\xD8\xFF\xE0")
    
    return source_dir


# =============================================================================
# Model Fixtures
# =============================================================================


@pytest.fixture
def sample_file_record(sample_jpg: Path) -> FileRecord:
    """Create a sample FileRecord."""
    return FileRecord(
        source_path=sample_jpg,
        file_type=FileType.IMAGE,
        size_bytes=100,
        detected_date=datetime(2024, 3, 15, 14, 30, 0),
        date_source=DateSource.EXIF,
        has_exif=True,
    )


@pytest.fixture
def file_record_no_date(sample_jpg: Path) -> FileRecord:
    """Create a FileRecord without a date."""
    return FileRecord(
        source_path=sample_jpg,
        file_type=FileType.IMAGE,
        size_bytes=100,
        detected_date=None,
        date_source=DateSource.UNKNOWN,
        has_exif=False,
    )


@pytest.fixture
def sample_scan_result(source_dir: Path, sample_file_record: FileRecord) -> ScanResult:
    """Create a sample ScanResult."""
    result = ScanResult(source_root=source_dir)
    result.add_file(sample_file_record)
    return result


# =============================================================================
# Config Fixtures
# =============================================================================


@pytest.fixture
def default_config() -> ChronoCleanConfig:
    """Return default configuration."""
    return ChronoCleanConfig()


@pytest.fixture
def config_with_renaming() -> ChronoCleanConfig:
    """Return configuration with renaming enabled."""
    config = ChronoCleanConfig()
    config.renaming = RenamingConfig(
        enabled=True,
        pattern="{date}_{time}",
        date_format="%Y%m%d",
        time_format="%H%M%S",
    )
    return config


@pytest.fixture
def config_with_tags() -> ChronoCleanConfig:
    """Return configuration with folder tags enabled."""
    config = ChronoCleanConfig()
    config.folder_tags = FolderTagsConfig(
        enabled=True,
        min_length=3,
        max_length=40,
    )
    return config


@pytest.fixture
def config_day_folders() -> ChronoCleanConfig:
    """Return configuration with day-level folders."""
    config = ChronoCleanConfig()
    config.sorting = SortingConfig(
        folder_structure="YYYY/MM/DD",
        include_day=True,
    )
    return config


# =============================================================================
# Date Fixtures
# =============================================================================


@pytest.fixture
def sample_date() -> datetime:
    """Return a sample datetime for testing."""
    return datetime(2024, 3, 15, 14, 30, 45)


@pytest.fixture
def sample_dates() -> list[datetime]:
    """Return a list of sample dates for testing."""
    return [
        datetime(2024, 1, 1, 0, 0, 0),
        datetime(2024, 6, 15, 12, 30, 0),
        datetime(2024, 12, 31, 23, 59, 59),
        datetime(2023, 7, 4, 9, 15, 30),
    ]


# =============================================================================
# Helper Functions (available to all tests)
# =============================================================================


def create_test_file(directory: Path, name: str, content: bytes = b"test") -> Path:
    """Helper to create a test file."""
    file_path = directory / name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)
    return file_path


def create_test_image(directory: Path, name: str = "test.jpg") -> Path:
    """Helper to create a minimal test image."""
    return create_test_file(directory, name, b"\xFF\xD8\xFF\xE0")


# Make helpers available
pytest.create_test_file = create_test_file
pytest.create_test_image = create_test_image
