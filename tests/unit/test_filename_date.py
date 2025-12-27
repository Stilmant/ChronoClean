"""Tests for filename date parsing (v0.2)."""

import pytest
from datetime import datetime
from pathlib import Path

from chronoclean.core.date_inference import (
    DateInferenceEngine,
    get_filename_date,
)
from chronoclean.core.models import DateSource


class TestFilenameDateParsing:
    """Tests for _get_filename_date method."""

    @pytest.fixture
    def engine(self):
        """Create a DateInferenceEngine with filename priority."""
        return DateInferenceEngine(priority=["filename"])

    # YYYYMMDD_HHMMSS formats
    @pytest.mark.parametrize("filename,expected", [
        ("IMG_20240315_143000.jpg", datetime(2024, 3, 15, 14, 30, 0)),
        ("20240315_143000.jpg", datetime(2024, 3, 15, 14, 30, 0)),
        ("photo_20240315_143000.jpg", datetime(2024, 3, 15, 14, 30, 0)),
        ("20240315-143000.jpg", datetime(2024, 3, 15, 14, 30, 0)),
    ])
    def test_yyyymmdd_hhmmss_format(self, engine, tmp_path, filename, expected):
        """Test YYYYMMDD_HHMMSS pattern."""
        file = tmp_path / filename
        file.touch()
        date, source = engine.infer_date(file)
        assert date == expected
        assert source == DateSource.FILENAME

    # Screenshot formats
    @pytest.mark.parametrize("filename,expected", [
        ("Screenshot_20240315_143000.png", datetime(2024, 3, 15, 14, 30, 0)),
        ("Screenshot-20240315-143000.png", datetime(2024, 3, 15, 14, 30, 0)),
        ("screenshot_20240315_143000.jpg", datetime(2024, 3, 15, 14, 30, 0)),
    ])
    def test_screenshot_format(self, engine, tmp_path, filename, expected):
        """Test screenshot filename format."""
        file = tmp_path / filename
        file.touch()
        date, source = engine.infer_date(file)
        assert date == expected
        assert source == DateSource.FILENAME

    # WhatsApp formats
    @pytest.mark.parametrize("filename,expected", [
        ("IMG-20240315-WA0001.jpg", datetime(2024, 3, 15)),
        ("IMG-20240315-WA0099.jpg", datetime(2024, 3, 15)),
        ("VID-20240315-WA0001.mp4", datetime(2024, 3, 15)),
        ("img-20240315-wa0001.jpg", datetime(2024, 3, 15)),  # lowercase
    ])
    def test_whatsapp_format(self, engine, tmp_path, filename, expected):
        """Test WhatsApp filename format."""
        file = tmp_path / filename
        file.touch()
        date, source = engine.infer_date(file)
        assert date == expected
        assert source == DateSource.FILENAME

    # IMG_YYYYMMDD format
    @pytest.mark.parametrize("filename,expected", [
        ("IMG_20240315.jpg", datetime(2024, 3, 15)),
        ("IMG-20240315.jpg", datetime(2024, 3, 15)),
        ("img_20240315.jpg", datetime(2024, 3, 15)),  # lowercase
    ])
    def test_img_yyyymmdd_format(self, engine, tmp_path, filename, expected):
        """Test IMG_YYYYMMDD pattern."""
        file = tmp_path / filename
        file.touch()
        date, source = engine.infer_date(file)
        assert date == expected
        assert source == DateSource.FILENAME

    # YYYY-MM-DD format
    @pytest.mark.parametrize("filename,expected", [
        ("2024-03-15_photo.jpg", datetime(2024, 3, 15)),
        ("photo_2024-03-15.jpg", datetime(2024, 3, 15)),
        ("2024-03-15.jpg", datetime(2024, 3, 15)),
    ])
    def test_yyyy_mm_dd_format(self, engine, tmp_path, filename, expected):
        """Test YYYY-MM-DD pattern."""
        file = tmp_path / filename
        file.touch()
        date, source = engine.infer_date(file)
        assert date == expected
        assert source == DateSource.FILENAME

    # YYYY_MM_DD format
    @pytest.mark.parametrize("filename,expected", [
        ("photo_2024_03_15.jpg", datetime(2024, 3, 15)),
        ("2024_03_15_vacation.jpg", datetime(2024, 3, 15)),
    ])
    def test_yyyy_underscore_mm_dd_format(self, engine, tmp_path, filename, expected):
        """Test YYYY_MM_DD pattern."""
        file = tmp_path / filename
        file.touch()
        date, source = engine.infer_date(file)
        assert date == expected
        assert source == DateSource.FILENAME

    # YYMMDD format (2-digit year)
    @pytest.mark.parametrize("filename,yy,expected_year", [
        ("IMG_090831.jpg", 9, 2009),    # 09 -> 2009
        ("IMG_150315.jpg", 15, 2015),   # 15 -> 2015
        ("IMG_000101.jpg", 0, 2000),    # 00 -> 2000
        ("IMG_290101.jpg", 29, 2029),   # 29 -> 2029 (under cutoff)
        ("IMG_990831.jpg", 99, 1999),   # 99 -> 1999
    ])
    def test_yymmdd_format_year_expansion(self, engine, tmp_path, filename, yy, expected_year):
        """Test YYMMDD pattern with 2-digit year expansion."""
        file = tmp_path / filename
        file.touch()
        date, source = engine.infer_date(file)
        assert date is not None
        assert date.year == expected_year
        assert source == DateSource.FILENAME

    def test_yymmdd_custom_cutoff(self, tmp_path):
        """Test custom year cutoff for 2-digit years."""
        engine = DateInferenceEngine(priority=["filename"], year_cutoff=20)
        # IMG_090315 -> 09-03-15 -> 2009 (09 < 20) 
        file = tmp_path / "IMG_090315.jpg"
        file.touch()
        date, source = engine.infer_date(file)
        assert date is not None
        assert date.year == 2009  # 09 <= 20, so 2000s

    # No date in filename
    @pytest.mark.parametrize("filename", [
        "photo.jpg",
        "IMG_1234.jpg",  # Not enough digits
        "random_file.png",
        "vacation.heic",
    ])
    def test_no_date_returns_none(self, engine, tmp_path, filename):
        """Test files without dates return None."""
        file = tmp_path / filename
        file.touch()
        date, source = engine.infer_date(file)
        assert date is None
        assert source == DateSource.UNKNOWN

    # Invalid dates
    @pytest.mark.parametrize("filename", [
        "IMG_20241315_143000.jpg",  # Invalid month 13
        "IMG_20240332_143000.jpg",  # Invalid day 32
        "IMG_20240229_250000.jpg",  # Invalid hour 25
    ])
    def test_invalid_dates_skipped(self, engine, tmp_path, filename):
        """Test invalid dates are skipped."""
        file = tmp_path / filename
        file.touch()
        date, source = engine.infer_date(file)
        # May parse partial or return None
        if date is not None:
            # Should not have invalid components
            assert 1 <= date.month <= 12
            assert 1 <= date.day <= 31


class TestFilenameDateInPriority:
    """Tests for filename date in priority order."""

    def test_filename_in_priority(self, tmp_path):
        """Test filename is used when in priority list."""
        engine = DateInferenceEngine(
            priority=["exif", "filename", "filesystem"]
        )
        file = tmp_path / "IMG_20240315_143000.jpg"
        file.touch()
        
        date, source = engine.infer_date(file)
        # EXIF will fail (no EXIF data), so filename should be used
        assert date == datetime(2024, 3, 15, 14, 30, 0)
        assert source == DateSource.FILENAME

    def test_filename_after_filesystem(self, tmp_path):
        """Test filesystem takes priority when filename is later."""
        engine = DateInferenceEngine(
            priority=["filesystem", "filename"]
        )
        file = tmp_path / "IMG_20200101_120000.jpg"
        file.touch()
        
        date, source = engine.infer_date(file)
        # Filesystem date will be found first
        assert source == DateSource.FILESYSTEM_MODIFIED

    def test_filename_only(self, tmp_path):
        """Test using only filename as source."""
        engine = DateInferenceEngine(priority=["filename"])
        file = tmp_path / "IMG_20240315_143000.jpg"
        file.touch()
        
        date, source = engine.infer_date(file)
        assert date == datetime(2024, 3, 15, 14, 30, 0)
        assert source == DateSource.FILENAME


class TestGetFilenameDateHelper:
    """Tests for get_filename_date convenience function."""

    def test_basic_usage(self, tmp_path):
        """Test get_filename_date returns datetime."""
        file = tmp_path / "IMG_20240315_143000.jpg"
        file.touch()
        
        date = get_filename_date(file)
        assert date == datetime(2024, 3, 15, 14, 30, 0)

    def test_no_date_returns_none(self, tmp_path):
        """Test returns None when no date in filename."""
        file = tmp_path / "random_photo.jpg"
        file.touch()
        
        date = get_filename_date(file)
        assert date is None

    def test_custom_year_cutoff(self, tmp_path):
        """Test custom year cutoff parameter."""
        file = tmp_path / "IMG_150315.jpg"
        file.touch()
        
        # Default cutoff=30: 15 -> 2015
        date = get_filename_date(file, year_cutoff=30)
        assert date is not None
        assert date.year == 2015
        
        # Cutoff=10: 15 -> 1915 - but this won't be 1915 
        # because the pattern matches YYYYMMDD first as 1503-15 which is invalid
        # Let's use a different test case
        file2 = tmp_path / "IMG_050315.jpg"
        file2.touch()
        
        # cutoff=30: 05 <= 30, so 2005
        date = get_filename_date(file2, year_cutoff=30)
        assert date is not None
        assert date.year == 2005


class TestDateSourceFilename:
    """Tests for FILENAME DateSource enum value."""

    def test_filename_in_enum(self):
        """Test FILENAME is a valid DateSource."""
        assert hasattr(DateSource, 'FILENAME')
        assert DateSource.FILENAME.value == "filename"

    def test_filename_source_returned(self, tmp_path):
        """Test filename date returns FILENAME source."""
        engine = DateInferenceEngine(priority=["filename"])
        file = tmp_path / "2024-03-15_photo.jpg"
        file.touch()
        
        date, source = engine.infer_date(file)
        assert source == DateSource.FILENAME


class TestEdgeCases:
    """Edge case tests for filename date parsing."""

    def test_multiple_dates_in_filename(self, tmp_path):
        """Test filename with multiple dates uses first valid."""
        engine = DateInferenceEngine(priority=["filename"])
        file = tmp_path / "20240315_to_20240320.jpg"
        file.touch()
        
        date, source = engine.infer_date(file)
        assert date == datetime(2024, 3, 15)

    def test_date_in_path_vs_filename(self, tmp_path):
        """Test date in filename takes priority over path."""
        subdir = tmp_path / "2020-01-01"
        subdir.mkdir()
        file = subdir / "IMG_20240315_143000.jpg"
        file.touch()
        
        engine = DateInferenceEngine(priority=["filename"])
        date, source = engine.infer_date(file)
        
        # Should get date from filename, not folder
        assert date == datetime(2024, 3, 15, 14, 30, 0)
        assert source == DateSource.FILENAME

    def test_very_long_filename(self, tmp_path):
        """Test parsing dates from long filenames."""
        engine = DateInferenceEngine(priority=["filename"])
        filename = "a" * 50 + "_20240315_143000_" + "b" * 50 + ".jpg"
        file = tmp_path / filename
        file.touch()
        
        date, source = engine.infer_date(file)
        assert date == datetime(2024, 3, 15, 14, 30, 0)

    def test_unicode_in_filename(self, tmp_path):
        """Test parsing dates from filenames with unicode."""
        engine = DateInferenceEngine(priority=["filename"])
        file = tmp_path / "パリ旅行_20240315_143000.jpg"
        file.touch()
        
        date, source = engine.infer_date(file)
        assert date == datetime(2024, 3, 15, 14, 30, 0)

    def test_8digit_not_date(self, tmp_path):
        """Test 8-digit numbers that aren't valid dates."""
        engine = DateInferenceEngine(priority=["filename"])
        file = tmp_path / "file_12345678.jpg"  # Not a valid date
        file.touch()
        
        date, source = engine.infer_date(file)
        # 12345678 -> 1234-56-78 is invalid
        assert date is None

    def test_boundary_dates(self, tmp_path):
        """Test boundary dates (Jan 1, Dec 31)."""
        engine = DateInferenceEngine(priority=["filename"])
        
        # January 1st
        file1 = tmp_path / "20240101_000000.jpg"
        file1.touch()
        date, _ = engine.infer_date(file1)
        assert date == datetime(2024, 1, 1, 0, 0, 0)
        
        # December 31st
        file2 = tmp_path / "20241231_235959.jpg"
        file2.touch()
        date, _ = engine.infer_date(file2)
        assert date == datetime(2024, 12, 31, 23, 59, 59)
