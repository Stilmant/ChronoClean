"""Unit tests for chronoclean.core.date_inference."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chronoclean.core.date_inference import DateInferenceEngine, get_best_date
from chronoclean.core.exif_reader import ExifReader
from chronoclean.core.models import DateSource


class TestDateInferenceEngine:
    """Tests for DateInferenceEngine class."""

    def test_init_defaults(self):
        engine = DateInferenceEngine()

        # v0.3: Default priority includes video_metadata and filename
        assert engine.priority == ["exif", "video_metadata", "filename", "filesystem", "folder_name"]
        assert engine.exif_reader is not None
        assert engine.video_reader is not None

    def test_init_custom_priority(self):
        engine = DateInferenceEngine(priority=["filesystem", "exif"])

        assert engine.priority == ["filesystem", "exif"]

    def test_init_custom_exif_reader(self):
        custom_reader = ExifReader(skip_errors=False)
        engine = DateInferenceEngine(exif_reader=custom_reader)

        assert engine.exif_reader is custom_reader


class TestInferDateFromExif:
    """Tests for EXIF date inference."""

    def test_exif_date_found(self, temp_dir: Path):
        """Returns EXIF date when available."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        mock_reader = MagicMock()
        mock_reader.get_date.return_value = datetime(2024, 3, 15, 14, 30)

        engine = DateInferenceEngine(exif_reader=mock_reader)
        date, source = engine.infer_date(jpg_file)

        assert date == datetime(2024, 3, 15, 14, 30)
        assert source == DateSource.EXIF

    def test_exif_date_not_found_fallback(self, temp_dir: Path):
        """Falls back to filesystem when EXIF not available."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        mock_reader = MagicMock()
        mock_reader.get_date.return_value = None

        engine = DateInferenceEngine(exif_reader=mock_reader)
        date, source = engine.infer_date(jpg_file)

        # Should fall back to filesystem
        assert date is not None
        assert source in (DateSource.FILESYSTEM_CREATED, DateSource.FILESYSTEM_MODIFIED)


class TestInferDateFromFilesystem:
    """Tests for filesystem date inference."""

    def test_filesystem_date(self, temp_dir: Path):
        """Gets date from filesystem."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["filesystem"])
        date, source = engine.infer_date(jpg_file)

        assert date is not None
        assert source in (DateSource.FILESYSTEM_CREATED, DateSource.FILESYSTEM_MODIFIED)

    def test_filesystem_date_recent(self, temp_dir: Path):
        """Filesystem date is recent (file just created)."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["filesystem"])
        date, source = engine.infer_date(jpg_file)

        # Date should be very recent (within last minute)
        now = datetime.now()
        assert (now - date).total_seconds() < 60


class TestInferDateFromFolderName:
    """Tests for folder name date inference."""

    @pytest.mark.parametrize("folder_name,expected_date", [
        ("2024-03-15", datetime(2024, 3, 15)),
        ("2024_03_15", datetime(2024, 3, 15)),
        ("2024.03.15", datetime(2024, 3, 15)),
        ("20240315", datetime(2024, 3, 15)),
    ])
    def test_full_date_patterns(self, temp_dir: Path, folder_name: str, expected_date: datetime):
        """Recognizes full date patterns in folder names."""
        folder = temp_dir / folder_name
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["folder_name"])
        date, source = engine.infer_date(jpg_file)

        assert date is not None
        assert date.year == expected_date.year
        assert date.month == expected_date.month
        assert date.day == expected_date.day
        assert source == DateSource.FOLDER_NAME

    @pytest.mark.parametrize("folder_name,expected_year,expected_month", [
        ("2024-03", 2024, 3),
        ("2024_03", 2024, 3),
        ("2024.03", 2024, 3),
    ])
    def test_year_month_patterns(self, temp_dir: Path, folder_name: str, 
                                  expected_year: int, expected_month: int):
        """Recognizes year-month patterns."""
        folder = temp_dir / folder_name
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["folder_name"])
        date, source = engine.infer_date(jpg_file)

        assert date is not None
        assert date.year == expected_year
        assert date.month == expected_month
        assert source == DateSource.FOLDER_NAME

    def test_date_with_text(self, temp_dir: Path):
        """Recognizes dates with surrounding text."""
        folder = temp_dir / "2024-03-15 Paris Trip"
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["folder_name"])
        date, source = engine.infer_date(jpg_file)

        assert date is not None
        assert date.year == 2024
        assert date.month == 3
        assert date.day == 15

    def test_year_only(self, temp_dir: Path):
        """Recognizes year-only folders."""
        folder = temp_dir / "Photos 2024"
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["folder_name"])
        date, source = engine.infer_date(jpg_file)

        assert date is not None
        assert date.year == 2024

    def test_no_date_in_folder(self, temp_dir: Path):
        """Returns None for folders without date patterns."""
        folder = temp_dir / "Random Folder"
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["folder_name"])
        date, source = engine.infer_date(jpg_file)

        assert date is None
        assert source == DateSource.UNKNOWN

    def test_walks_up_directory_tree(self, temp_dir: Path):
        """Walks up directory tree to find date."""
        dated_folder = temp_dir / "2024-03-15 Trip"
        subfolder = dated_folder / "Day1"
        subfolder.mkdir(parents=True)
        jpg_file = subfolder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["folder_name"])
        date, source = engine.infer_date(jpg_file)

        assert date is not None
        assert date.year == 2024
        assert date.month == 3
        assert date.day == 15


class TestDateValidation:
    """Tests for date validation logic."""

    def test_invalid_month_rejected(self, temp_dir: Path):
        """Invalid month (13) is rejected."""
        folder = temp_dir / "2024-13-01"
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["folder_name"])
        date, source = engine.infer_date(jpg_file)

        # Should not parse invalid date
        assert date is None or date.month != 13

    def test_invalid_day_rejected(self, temp_dir: Path):
        """Invalid day (32) is rejected."""
        folder = temp_dir / "2024-01-32"
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["folder_name"])
        date, source = engine.infer_date(jpg_file)

        assert date is None or date.day != 32

    def test_year_out_of_range(self, temp_dir: Path):
        """Year before 1990 or after 2100 may be rejected."""
        folder = temp_dir / "1800-01-01"
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        engine = DateInferenceEngine(priority=["folder_name"])
        date, source = engine.infer_date(jpg_file)

        # Should either be None or have the parsed year
        if date is not None:
            assert date.year == 1800 or source == DateSource.UNKNOWN


class TestPriorityOrder:
    """Tests for date source priority ordering."""

    def test_exif_takes_priority(self, temp_dir: Path):
        """EXIF date is preferred over filesystem."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        mock_reader = MagicMock()
        mock_reader.get_date.return_value = datetime(2020, 1, 1)

        engine = DateInferenceEngine(
            priority=["exif", "filesystem"],
            exif_reader=mock_reader,
        )
        date, source = engine.infer_date(jpg_file)

        assert date == datetime(2020, 1, 1)
        assert source == DateSource.EXIF

    def test_custom_priority(self, temp_dir: Path):
        """Custom priority order is respected."""
        folder = temp_dir / "2024-06-15"
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        mock_reader = MagicMock()
        mock_reader.get_date.return_value = datetime(2020, 1, 1)

        # Folder name first
        engine = DateInferenceEngine(
            priority=["folder_name", "exif"],
            exif_reader=mock_reader,
        )
        date, source = engine.infer_date(jpg_file)

        assert date.year == 2024
        assert date.month == 6
        assert source == DateSource.FOLDER_NAME


class TestGetBestDateFunction:
    """Tests for the convenience function."""

    def test_get_best_date(self, temp_dir: Path):
        """Convenience function works."""
        folder = temp_dir / "2024-03-15"
        folder.mkdir()
        jpg_file = folder / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        date, source = get_best_date(jpg_file, priority=["folder_name"])

        assert date is not None
        assert date.year == 2024

    def test_get_best_date_default_priority(self, temp_dir: Path):
        """Uses default priority when not specified."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        date, source = get_best_date(jpg_file)

        # Should return something (at least filesystem date)
        assert date is not None or source == DateSource.UNKNOWN
