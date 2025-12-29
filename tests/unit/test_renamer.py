"""Unit tests for chronoclean.core.renamer."""

from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.core.renamer import ConflictResolver, Renamer


class TestRenamerInit:
    """Tests for Renamer initialization."""

    def test_default_init(self):
        renamer = Renamer()

        assert renamer.pattern == "{date}_{time}"
        assert renamer.date_format == "%Y%m%d"
        assert renamer.time_format == "%H%M%S"
        assert renamer.lowercase_ext is True

    def test_custom_init(self):
        renamer = Renamer(
            pattern="{date}_{original}",
            date_format="%Y-%m-%d",
            time_format="%H%M",
            lowercase_ext=False,
        )

        assert renamer.pattern == "{date}_{original}"
        assert renamer.date_format == "%Y-%m-%d"
        assert renamer.time_format == "%H%M"
        assert renamer.lowercase_ext is False


class TestGenerateFilename:
    """Tests for generate_filename method."""

    def test_basic_rename(self):
        renamer = Renamer()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.JPG")

        result = renamer.generate_filename(original, date)

        assert result == "20240315_143045.jpg"

    def test_preserve_extension_case(self):
        renamer = Renamer(lowercase_ext=False)
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.JPG")

        result = renamer.generate_filename(original, date)

        assert result.endswith(".JPG")

    def test_with_tag(self):
        renamer = Renamer()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = renamer.generate_filename(original, date, tag="Paris")

        assert result == "20240315_143045_Paris.jpg"

    def test_tag_in_pattern(self):
        renamer = Renamer(pattern="{date}_{tag}_{time}")
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = renamer.generate_filename(original, date, tag="Paris")

        assert result == "20240315_Paris_143045.jpg"

    def test_original_in_pattern(self):
        renamer = Renamer(pattern="{date}_{original}")
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("MyPhoto.jpg")

        result = renamer.generate_filename(original, date)

        assert result == "20240315_MyPhoto.jpg"

    def test_with_counter(self):
        renamer = Renamer()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = renamer.generate_filename(original, date, counter=5)

        assert result == "20240315_143045_005.jpg"

    def test_counter_in_pattern(self):
        renamer = Renamer(pattern="{date}_{time}_{counter}")
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = renamer.generate_filename(original, date, counter=42)

        assert result == "20240315_143045_042.jpg"

    def test_custom_date_format(self):
        renamer = Renamer(date_format="%Y-%m-%d")
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = renamer.generate_filename(original, date)

        assert "2024-03-15" in result

    def test_custom_time_format(self):
        renamer = Renamer(time_format="%H-%M")
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = renamer.generate_filename(original, date)

        assert "14-30" in result

    def test_no_double_underscores(self):
        renamer = Renamer(pattern="{date}__{time}")
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = renamer.generate_filename(original, date)

        assert "__" not in result

    def test_tag_without_pattern_placeholder(self):
        renamer = Renamer(pattern="{date}_{time}", tag_format="_{tag}")
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = renamer.generate_filename(original, date, tag="Paris")

        assert result == "20240315_143045_Paris.jpg"


class TestFormatTag:
    """Tests for _format_tag method."""

    def test_basic_format(self):
        renamer = Renamer()

        assert renamer._format_tag("Paris Trip") == "Paris_Trip"

    def test_removes_special_chars(self):
        renamer = Renamer()

        assert renamer._format_tag("Trip!@#$%") == "Trip"

    def test_max_length(self):
        renamer = Renamer()
        long_tag = "A" * 50

        result = renamer._format_tag(long_tag)

        assert len(result) <= 30

    def test_strips_underscores(self):
        renamer = Renamer()

        assert renamer._format_tag("_Paris_") == "Paris"


class TestNeedsRename:
    """Tests for needs_rename method."""

    def test_needs_rename_true(self):
        renamer = Renamer()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        assert renamer.needs_rename(original, date) is True

    def test_needs_rename_false(self):
        renamer = Renamer()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("20240315_143045.jpg")

        assert renamer.needs_rename(original, date) is False

    def test_case_insensitive(self):
        renamer = Renamer()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("20240315_143045.JPG")

        assert renamer.needs_rename(original, date) is False


class TestConflictResolver:
    """Tests for ConflictResolver class."""

    def test_init_default(self):
        resolver = ConflictResolver()

        assert resolver.renamer is not None

    def test_init_custom_renamer(self):
        custom = Renamer(pattern="{original}")
        resolver = ConflictResolver(renamer=custom)

        assert resolver.renamer is custom

    def test_resolve_no_conflict(self):
        resolver = ConflictResolver()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = resolver.resolve(original, date)

        assert result == "20240315_143045.jpg"

    def test_resolve_with_existing_files(self):
        resolver = ConflictResolver()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        existing = {"20240315_143045.jpg"}
        result = resolver.resolve(original, date, existing_files=existing)

        assert result == "20240315_143045_001.jpg"

    def test_resolve_multiple_conflicts(self):
        resolver = ConflictResolver()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        existing = {
            "20240315_143045.jpg",
            "20240315_143045_001.jpg",
            "20240315_143045_002.jpg",
        }
        result = resolver.resolve(original, date, existing_files=existing)

        assert result == "20240315_143045_003.jpg"

    def test_resolve_tracks_used_names(self):
        resolver = ConflictResolver()
        date = datetime(2024, 3, 15, 14, 30, 45)

        # First file
        result1 = resolver.resolve(Path("IMG_001.jpg"), date)
        # Second file same date
        result2 = resolver.resolve(Path("IMG_002.jpg"), date)

        assert result1 == "20240315_143045.jpg"
        assert result2 == "20240315_143045_001.jpg"

    def test_resolve_with_tag(self):
        resolver = ConflictResolver()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        result = resolver.resolve(original, date, tag="Paris")

        assert "Paris" in result

    def test_reset(self):
        resolver = ConflictResolver()
        date = datetime(2024, 3, 15, 14, 30, 45)

        resolver.resolve(Path("IMG_001.jpg"), date)
        resolver.reset()
        result = resolver.resolve(Path("IMG_002.jpg"), date)

        # After reset, should get same name as first file would have
        assert result == "20240315_143045.jpg"

    def test_case_insensitive_tracking(self):
        resolver = ConflictResolver()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("IMG_001.jpg")

        existing = {"20240315_143045.JPG"}  # uppercase
        result = resolver.resolve(original, date, existing_files=existing)

        assert result == "20240315_143045_001.jpg"


class TestEdgeCases:
    """Edge case tests."""

    def test_midnight(self):
        renamer = Renamer()
        date = datetime(2024, 1, 1, 0, 0, 0)
        original = Path("photo.jpg")

        result = renamer.generate_filename(original, date)

        assert result == "20240101_000000.jpg"

    def test_end_of_day(self):
        renamer = Renamer()
        date = datetime(2024, 12, 31, 23, 59, 59)
        original = Path("photo.jpg")

        result = renamer.generate_filename(original, date)

        assert result == "20241231_235959.jpg"

    def test_empty_tag(self):
        renamer = Renamer()
        date = datetime(2024, 3, 15, 14, 30, 45)
        original = Path("photo.jpg")

        result = renamer.generate_filename(original, date, tag="")

        assert result == "20240315_143045.jpg"

    def test_various_extensions(self):
        renamer = Renamer()
        date = datetime(2024, 3, 15, 14, 30, 45)

        for ext in [".jpg", ".png", ".heic", ".mp4", ".cr2"]:
            original = Path(f"photo{ext.upper()}")
            result = renamer.generate_filename(original, date)
            assert result.endswith(ext)

class TestGenerateFilenameTagOnly:
    """Tests for generate_filename_tag_only method (v0.3)."""

    def test_basic_tag_only(self):
        """Basic tag-only rename preserves original name."""
        renamer = Renamer()
        original = Path("IMG_1234.JPG")

        result = renamer.generate_filename_tag_only(original, "Paris")

        assert result == "IMG_1234_Paris.jpg"

    def test_tag_only_preserves_stem(self):
        """Original filename stem is preserved."""
        renamer = Renamer()
        original = Path("vacation_photo_2024.jpg")

        result = renamer.generate_filename_tag_only(original, "Beach")

        assert result == "vacation_photo_2024_Beach.jpg"

    def test_tag_only_with_counter(self):
        """Counter is appended for duplicates."""
        renamer = Renamer()
        original = Path("IMG_1234.jpg")

        result = renamer.generate_filename_tag_only(original, "Paris", counter=1)

        assert result == "IMG_1234_Paris_001.jpg"

    def test_tag_only_lowercase_extension(self):
        """Extension is lowercased by default."""
        renamer = Renamer(lowercase_ext=True)
        original = Path("IMG_1234.JPG")

        result = renamer.generate_filename_tag_only(original, "Paris")

        assert result.endswith(".jpg")

    def test_tag_only_preserve_extension_case(self):
        """Extension case can be preserved."""
        renamer = Renamer(lowercase_ext=False)
        original = Path("IMG_1234.JPG")

        result = renamer.generate_filename_tag_only(original, "Paris")

        assert result.endswith(".JPG")

    def test_tag_only_cleans_tag(self):
        """Tag is cleaned and formatted."""
        renamer = Renamer()
        original = Path("IMG_1234.jpg")

        # Special characters should be removed
        result = renamer.generate_filename_tag_only(original, "Paris Trip!")

        assert "!" not in result
        assert "Paris" in result

    def test_tag_only_handles_spaces_in_tag(self):
        """Spaces in tag are converted to underscores."""
        renamer = Renamer()
        original = Path("IMG_1234.jpg")

        result = renamer.generate_filename_tag_only(original, "Beach Vacation")

        assert " " not in result
        assert "_" in result

    def test_tag_only_removes_double_underscores(self):
        """Double underscores are collapsed."""
        renamer = Renamer()
        original = Path("IMG__1234.jpg")  # Stem has double underscore

        result = renamer.generate_filename_tag_only(original, "Paris")

        assert "__" not in result

    def test_tag_only_various_extensions(self):
        """Works with various file types."""
        renamer = Renamer()
        
        for ext in [".jpg", ".png", ".heic", ".mp4", ".cr2", ".mov"]:
            original = Path(f"photo{ext.upper()}")
            result = renamer.generate_filename_tag_only(original, "Tag")
            assert result.endswith(ext)
            assert "Tag" in result