"""Unit tests for chronoclean.core.exif_reader."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from chronoclean.core.exif_reader import ExifData, ExifReader, ExifReadError


class TestExifData:
    """Tests for ExifData dataclass."""

    def test_default_values(self):
        data = ExifData()

        assert data.date_taken is None
        assert data.date_original is None
        assert data.date_digitized is None
        assert data.camera_make is None
        assert data.camera_model is None
        assert data.raw_tags == {}

    def test_best_date_original_priority(self):
        """date_original takes priority."""
        data = ExifData(
            date_original=datetime(2024, 1, 1),
            date_taken=datetime(2024, 2, 2),
            date_digitized=datetime(2024, 3, 3),
        )

        assert data.best_date == datetime(2024, 1, 1)

    def test_best_date_fallback_to_taken(self):
        """Falls back to date_taken if no original."""
        data = ExifData(
            date_taken=datetime(2024, 2, 2),
            date_digitized=datetime(2024, 3, 3),
        )

        assert data.best_date == datetime(2024, 2, 2)

    def test_best_date_fallback_to_digitized(self):
        """Falls back to date_digitized if no others."""
        data = ExifData(
            date_digitized=datetime(2024, 3, 3),
        )

        assert data.best_date == datetime(2024, 3, 3)

    def test_best_date_none(self):
        """Returns None if no dates."""
        data = ExifData()

        assert data.best_date is None


class TestExifReader:
    """Tests for ExifReader class."""

    def test_init_defaults(self):
        reader = ExifReader()

        assert reader.skip_errors is True

    def test_init_custom(self):
        reader = ExifReader(skip_errors=False)

        assert reader.skip_errors is False

    def test_supported_extensions(self):
        assert ".jpg" in ExifReader.SUPPORTED_EXTENSIONS
        assert ".jpeg" in ExifReader.SUPPORTED_EXTENSIONS
        assert ".heic" in ExifReader.SUPPORTED_EXTENSIONS
        assert ".tiff" in ExifReader.SUPPORTED_EXTENSIONS

    def test_read_nonexistent_file_skip_errors(self, temp_dir: Path):
        """Non-existent file returns empty ExifData when skip_errors=True."""
        reader = ExifReader(skip_errors=True)
        fake_path = temp_dir / "nonexistent.jpg"

        result = reader.read(fake_path)

        assert isinstance(result, ExifData)
        assert result.best_date is None

    def test_read_nonexistent_file_raise_error(self, temp_dir: Path):
        """Non-existent file raises when skip_errors=False."""
        reader = ExifReader(skip_errors=False)
        fake_path = temp_dir / "nonexistent.jpg"

        with pytest.raises(ExifReadError, match="not found"):
            reader.read(fake_path)

    def test_read_unsupported_extension(self, temp_dir: Path):
        """Unsupported extension returns empty ExifData."""
        reader = ExifReader()
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("not an image")

        result = reader.read(txt_file)

        assert isinstance(result, ExifData)
        assert result.best_date is None

    @patch("chronoclean.core.exif_reader.exifread.process_file")
    def test_read_with_exif_data(self, mock_process, temp_dir: Path):
        """Successfully reads EXIF data."""
        # Create test file
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        # Mock EXIF tags
        mock_process.return_value = {
            "EXIF DateTimeOriginal": MagicMock(__str__=lambda s: "2024:03:15 14:30:00"),
            "Image Make": MagicMock(__str__=lambda s: "Canon"),
            "Image Model": MagicMock(__str__=lambda s: "EOS 5D"),
        }

        reader = ExifReader()
        result = reader.read(jpg_file)

        assert result.date_original == datetime(2024, 3, 15, 14, 30, 0)
        assert result.camera_make == "Canon"
        assert result.camera_model == "EOS 5D"

    @patch("chronoclean.core.exif_reader.exifread.process_file")
    def test_read_empty_exif(self, mock_process, temp_dir: Path):
        """File with no EXIF returns empty ExifData."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        mock_process.return_value = {}

        reader = ExifReader()
        result = reader.read(jpg_file)

        assert result.best_date is None

    @patch("chronoclean.core.exif_reader.exifread.process_file")
    def test_get_date_convenience(self, mock_process, temp_dir: Path):
        """get_date() returns just the date."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        mock_process.return_value = {
            "EXIF DateTimeOriginal": MagicMock(__str__=lambda s: "2024:03:15 14:30:00"),
        }

        reader = ExifReader()
        date = reader.get_date(jpg_file)

        assert date == datetime(2024, 3, 15, 14, 30, 0)

    @patch("chronoclean.core.exif_reader.exifread.process_file")
    def test_has_exif_true(self, mock_process, temp_dir: Path):
        """has_exif() returns True when date exists."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        mock_process.return_value = {
            "EXIF DateTimeOriginal": MagicMock(__str__=lambda s: "2024:03:15 14:30:00"),
        }

        reader = ExifReader()
        assert reader.has_exif(jpg_file) is True

    @patch("chronoclean.core.exif_reader.exifread.process_file")
    def test_has_exif_false(self, mock_process, temp_dir: Path):
        """has_exif() returns False when no date."""
        jpg_file = temp_dir / "test.jpg"
        jpg_file.write_bytes(b"\xFF\xD8\xFF\xE0")

        mock_process.return_value = {}

        reader = ExifReader()
        assert reader.has_exif(jpg_file) is False


class TestExifReaderDateParsing:
    """Tests for EXIF date parsing."""

    def test_parse_standard_format(self):
        reader = ExifReader()
        result = reader._parse_date("2024:03:15 14:30:00")

        assert result == datetime(2024, 3, 15, 14, 30, 0)

    def test_parse_dash_format(self):
        reader = ExifReader()
        result = reader._parse_date("2024-03-15 14:30:00")

        assert result == datetime(2024, 3, 15, 14, 30, 0)

    def test_parse_slash_format(self):
        reader = ExifReader()
        result = reader._parse_date("2024/03/15 14:30:00")

        assert result == datetime(2024, 3, 15, 14, 30, 0)

    def test_parse_without_seconds(self):
        reader = ExifReader()
        result = reader._parse_date("2024:03:15 14:30")

        assert result == datetime(2024, 3, 15, 14, 30, 0)

    def test_parse_empty_string(self):
        reader = ExifReader()
        result = reader._parse_date("")

        assert result is None

    def test_parse_zero_date(self):
        reader = ExifReader()
        result = reader._parse_date("0000:00:00 00:00:00")

        assert result is None

    def test_parse_invalid_format(self):
        reader = ExifReader()
        result = reader._parse_date("not a date")

        assert result is None

    def test_parse_whitespace(self):
        reader = ExifReader()
        result = reader._parse_date("  2024:03:15 14:30:00  ")

        assert result == datetime(2024, 3, 15, 14, 30, 0)
