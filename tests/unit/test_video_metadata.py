"""Unit tests for chronoclean.core.video_metadata module (v0.3)."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chronoclean.core.video_metadata import (
    VideoMetadataReader,
    parse_video_date,
    VIDEO_DATE_FORMATS,
)


class TestVideoMetadataReaderInit:
    """Tests for VideoMetadataReader initialization."""

    def test_default_init(self):
        """Default initialization uses ffprobe provider."""
        reader = VideoMetadataReader()

        assert reader.provider == "ffprobe"
        assert reader.ffprobe_path == "ffprobe"
        assert reader.fallback_to_hachoir is True
        assert reader.skip_errors is True

    def test_custom_init(self):
        """Custom initialization respects all parameters."""
        reader = VideoMetadataReader(
            provider="hachoir",
            ffprobe_path="/usr/local/bin/ffprobe",
            fallback_to_hachoir=False,
            skip_errors=False,
        )

        assert reader.provider == "hachoir"
        assert reader.ffprobe_path == "/usr/local/bin/ffprobe"
        assert reader.fallback_to_hachoir is False
        assert reader.skip_errors is False


class TestParseDateString:
    """Tests for parse_video_date function."""

    def test_iso_format_with_z(self):
        """Parse ISO format with Z suffix."""
        result = parse_video_date("2024-03-15T14:30:00Z")

        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30

    def test_iso_format_with_microseconds(self):
        """Parse ISO format with microseconds."""
        result = parse_video_date("2024-03-15T14:30:00.123456Z")

        assert result is not None
        assert result.year == 2024

    def test_common_format(self):
        """Parse common datetime format."""
        result = parse_video_date("2024-03-15 14:30:00")

        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_exif_like_format(self):
        """Parse EXIF-like format with colons."""
        result = parse_video_date("2024:03:15 14:30:00")

        assert result is not None
        assert result.year == 2024

    def test_date_only_format(self):
        """Parse date-only format."""
        result = parse_video_date("2024-03-15")

        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_invalid_date_returns_none(self):
        """Invalid date string returns None."""
        result = parse_video_date("not a date")

        assert result is None

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        result = parse_video_date("")

        assert result is None

    def test_none_returns_none(self):
        """None input returns None."""
        result = parse_video_date(None)

        assert result is None


class TestVideoMetadataReaderGetCreationDate:
    """Tests for get_creation_date method."""

    def test_nonexistent_file_returns_none(self, tmp_path: Path):
        """Non-existent file returns None."""
        reader = VideoMetadataReader()
        fake_path = tmp_path / "nonexistent.mp4"

        result = reader.get_creation_date(fake_path)

        assert result is None

    @patch.object(VideoMetadataReader, "_check_ffprobe")
    @patch.object(VideoMetadataReader, "_ffprobe_date")
    def test_ffprobe_provider_success(
        self, mock_ffprobe_date, mock_check_ffprobe, tmp_path: Path
    ):
        """ffprobe provider returns date on success."""
        mock_check_ffprobe.return_value = True
        mock_ffprobe_date.return_value = datetime(2024, 3, 15, 14, 30, 0)

        # Create a real file
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        reader = VideoMetadataReader(provider="ffprobe")
        result = reader.get_creation_date(video_file)

        assert result == datetime(2024, 3, 15, 14, 30, 0)
        mock_ffprobe_date.assert_called_once()

    @patch.object(VideoMetadataReader, "_check_ffprobe")
    @patch.object(VideoMetadataReader, "_check_hachoir")
    @patch.object(VideoMetadataReader, "_ffprobe_date")
    @patch.object(VideoMetadataReader, "_hachoir_date")
    def test_fallback_to_hachoir(
        self,
        mock_hachoir_date,
        mock_ffprobe_date,
        mock_check_hachoir,
        mock_check_ffprobe,
        tmp_path: Path,
    ):
        """Falls back to hachoir when ffprobe fails."""
        mock_check_ffprobe.return_value = True
        mock_check_hachoir.return_value = True
        mock_ffprobe_date.return_value = None  # ffprobe fails
        mock_hachoir_date.return_value = datetime(2024, 3, 15, 14, 30, 0)

        video_file = tmp_path / "test.mp4"
        video_file.touch()

        reader = VideoMetadataReader(provider="ffprobe", fallback_to_hachoir=True)
        result = reader.get_creation_date(video_file)

        assert result == datetime(2024, 3, 15, 14, 30, 0)
        mock_hachoir_date.assert_called_once()

    @patch.object(VideoMetadataReader, "_check_ffprobe")
    @patch.object(VideoMetadataReader, "_ffprobe_date")
    def test_no_fallback_returns_none(
        self, mock_ffprobe_date, mock_check_ffprobe, tmp_path: Path
    ):
        """Returns None when ffprobe fails and fallback disabled."""
        mock_check_ffprobe.return_value = True
        mock_ffprobe_date.return_value = None

        video_file = tmp_path / "test.mp4"
        video_file.touch()

        reader = VideoMetadataReader(provider="ffprobe", fallback_to_hachoir=False)
        result = reader.get_creation_date(video_file)

        assert result is None

    @patch.object(VideoMetadataReader, "_check_hachoir")
    @patch.object(VideoMetadataReader, "_hachoir_date")
    def test_hachoir_provider(
        self, mock_hachoir_date, mock_check_hachoir, tmp_path: Path
    ):
        """hachoir provider works when selected."""
        mock_check_hachoir.return_value = True
        mock_hachoir_date.return_value = datetime(2024, 3, 15, 14, 30, 0)

        video_file = tmp_path / "test.mp4"
        video_file.touch()

        reader = VideoMetadataReader(provider="hachoir")
        result = reader.get_creation_date(video_file)

        assert result == datetime(2024, 3, 15, 14, 30, 0)


class TestVideoMetadataReaderProviderChecks:
    """Tests for provider availability checks."""

    @patch("shutil.which")
    def test_check_ffprobe_available(self, mock_which):
        """ffprobe check returns True when available."""
        mock_which.return_value = "/usr/bin/ffprobe"

        reader = VideoMetadataReader()
        result = reader._check_ffprobe()

        assert result is True
        mock_which.assert_called_with("ffprobe")

    @patch("shutil.which")
    def test_check_ffprobe_unavailable(self, mock_which):
        """ffprobe check returns False when unavailable."""
        mock_which.return_value = None

        reader = VideoMetadataReader()
        result = reader._check_ffprobe()

        assert result is False

    @patch("shutil.which")
    def test_ffprobe_check_cached(self, mock_which):
        """ffprobe availability is cached."""
        mock_which.return_value = "/usr/bin/ffprobe"

        reader = VideoMetadataReader()
        reader._check_ffprobe()
        reader._check_ffprobe()

        # Should only be called once due to caching
        assert mock_which.call_count == 1


class TestVideoDateFormats:
    """Tests for VIDEO_DATE_FORMATS constant."""

    def test_formats_list_not_empty(self):
        """Date formats list is populated."""
        assert len(VIDEO_DATE_FORMATS) > 0

    def test_formats_include_common_patterns(self):
        """Common date patterns are included."""
        # These are common patterns that should be supported
        test_cases = [
            "2024-03-15T14:30:00Z",
            "2024-03-15 14:30:00",
            "2024:03:15 14:30:00",
            "2024-03-15",
        ]

        for date_str in test_cases:
            result = parse_video_date(date_str)
            assert result is not None, f"Failed to parse: {date_str}"
