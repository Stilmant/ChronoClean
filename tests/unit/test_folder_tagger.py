"""Unit tests for chronoclean.core.folder_tagger."""

from pathlib import Path

import pytest

from chronoclean.core.folder_tagger import FolderTagger, get_folder_tag


class TestFolderTaggerInit:
    """Tests for FolderTagger initialization."""

    def test_default_init(self):
        tagger = FolderTagger()

        assert tagger.min_length == 3
        assert tagger.max_length == 40
        assert tagger.distance_threshold == 0.75
        assert "tosort" in tagger.ignore_list
        assert len(tagger.force_list) == 0

    def test_custom_ignore_list(self):
        tagger = FolderTagger(ignore_list=["custom", "ignore"])

        assert "custom" in tagger.ignore_list
        assert "ignore" in tagger.ignore_list

    def test_custom_force_list(self):
        tagger = FolderTagger(force_list=["always", "use"])

        assert "always" in tagger.force_list
        assert "use" in tagger.force_list

    def test_lists_are_lowercase(self):
        tagger = FolderTagger(
            ignore_list=["UPPERCASE"],
            force_list=["MixedCase"],
        )

        assert "uppercase" in tagger.ignore_list
        assert "mixedcase" in tagger.force_list


class TestIsMeaningful:
    """Tests for is_meaningful method."""

    def test_meaningful_folder(self):
        tagger = FolderTagger()

        assert tagger.is_meaningful("Paris Trip 2024") is True
        assert tagger.is_meaningful("Wedding Photos") is True
        assert tagger.is_meaningful("Birthday Party") is True

    def test_ignored_folders(self):
        tagger = FolderTagger()

        assert tagger.is_meaningful("tosort") is False
        assert tagger.is_meaningful("TOSORT") is False
        assert tagger.is_meaningful("unsorted") is False
        assert tagger.is_meaningful("misc") is False
        assert tagger.is_meaningful("backup") is False
        assert tagger.is_meaningful("temp") is False
        assert tagger.is_meaningful("DCIM") is False

    def test_too_short(self):
        tagger = FolderTagger(min_length=3)

        assert tagger.is_meaningful("ab") is False
        assert tagger.is_meaningful("a") is False

    def test_too_long(self):
        tagger = FolderTagger(max_length=10)

        assert tagger.is_meaningful("This is a very long folder name") is False

    def test_force_list_overrides_ignore(self):
        tagger = FolderTagger(
            ignore_list=["vacation"],
            force_list=["vacation"],
        )

        assert tagger.is_meaningful("vacation") is True

    def test_empty_string(self):
        tagger = FolderTagger()

        assert tagger.is_meaningful("") is False

    def test_whitespace_only(self):
        tagger = FolderTagger()

        assert tagger.is_meaningful("   ") is False


class TestClassifyFolder:
    """Tests for classify_folder method."""

    def test_meaningful_classification(self):
        tagger = FolderTagger()
        usable, reason = tagger.classify_folder("Paris 2024")

        assert usable is True
        assert reason == "meaningful"

    def test_ignore_list_classification(self):
        tagger = FolderTagger()
        usable, reason = tagger.classify_folder("tosort")

        assert usable is False
        assert reason == "in_ignore_list"

    def test_force_list_classification(self):
        tagger = FolderTagger(force_list=["special"])
        usable, reason = tagger.classify_folder("special")

        assert usable is True
        assert reason == "in_force_list"

    def test_too_short_classification(self):
        tagger = FolderTagger(min_length=3)
        usable, reason = tagger.classify_folder("ab")

        assert usable is False
        assert reason == "too_short"

    def test_too_long_classification(self):
        tagger = FolderTagger(max_length=5)
        usable, reason = tagger.classify_folder("Very Long Name")

        assert usable is False
        assert reason == "too_long"

    def test_empty_classification(self):
        tagger = FolderTagger()
        usable, reason = tagger.classify_folder("")

        assert usable is False
        assert reason == "empty"


class TestCameraFolderPatterns:
    """Tests for camera-generated folder detection."""

    @pytest.mark.parametrize("folder_name", [
        "100APPLE",
        "101ANDRO",
        "102NIKON",
        "DCIM",
        "dcim",
    ])
    def test_camera_folders_rejected(self, folder_name: str):
        tagger = FolderTagger()
        usable, reason = tagger.classify_folder(folder_name)

        assert usable is False

    @pytest.mark.parametrize("folder_name", [
        "12345678",  # Just 8 digits
        "20240315",  # Date-like
    ])
    def test_numbers_only_rejected(self, folder_name: str):
        tagger = FolderTagger()
        usable, reason = tagger.classify_folder(folder_name)

        assert usable is False


class TestFormatTag:
    """Tests for format_tag method."""

    def test_basic_format(self):
        tagger = FolderTagger()

        assert tagger.format_tag("Paris Trip") == "Paris_Trip"

    def test_removes_special_chars(self):
        tagger = FolderTagger()

        # Implementation removes special chars without replacing with underscore
        assert tagger.format_tag("Paris/Trip!") == "ParisTrip"
        assert tagger.format_tag("My@Photo#Collection") == "MyPhotoCollection"

    def test_multiple_spaces(self):
        tagger = FolderTagger()

        assert tagger.format_tag("Paris   Trip") == "Paris_Trip"

    def test_strips_whitespace(self):
        tagger = FolderTagger()

        assert tagger.format_tag("  Paris Trip  ") == "Paris_Trip"

    def test_truncates_long_tags(self):
        tagger = FolderTagger(max_length=10)
        long_name = "A" * 50

        result = tagger.format_tag(long_name)
        assert len(result) <= tagger.max_length

    def test_preserves_hyphens(self):
        tagger = FolderTagger()

        assert tagger.format_tag("2024-03-15") == "2024-03-15"

    def test_removes_leading_trailing_underscores(self):
        tagger = FolderTagger()

        assert tagger.format_tag("_Paris_") == "Paris"


class TestExtractTag:
    """Tests for extract_tag method."""

    def test_extract_from_meaningful_folder(self, temp_dir: Path):
        folder = temp_dir / "Paris 2024"
        folder.mkdir()
        file_path = folder / "photo.jpg"
        file_path.write_bytes(b"test")

        tagger = FolderTagger()
        tag = tagger.extract_tag(file_path)

        assert tag == "Paris_2024"

    def test_extract_skips_ignored_folder(self, temp_dir: Path):
        # Create 3 levels of non-meaningful folders to exhaust the 3-level walk
        folder = temp_dir / "DCIM" / "100APPLE" / "tosort"
        folder.mkdir(parents=True)
        file_path = folder / "photo.jpg"
        file_path.write_bytes(b"test")

        tagger = FolderTagger()
        tag = tagger.extract_tag(file_path)

        # All 3 levels (tosort, 100APPLE, DCIM) are non-meaningful
        assert tag is None

    def test_extract_walks_up_tree(self, temp_dir: Path):
        meaningful = temp_dir / "Paris 2024"
        ignored = meaningful / "tosort"
        ignored.mkdir(parents=True)
        file_path = ignored / "photo.jpg"
        file_path.write_bytes(b"test")

        tagger = FolderTagger()
        tag = tagger.extract_tag(file_path)

        assert tag == "Paris_2024"

    def test_extract_from_directory(self, temp_dir: Path):
        folder = temp_dir / "Wedding"
        folder.mkdir()

        tagger = FolderTagger()
        tag = tagger.extract_tag(folder)

        assert tag == "Wedding"

    def test_extract_none_when_no_meaningful(self, temp_dir: Path):
        # Create 3+ levels of non-meaningful folders to exhaust walk limit
        folder = temp_dir / "DCIM" / "100APPLE" / "tosort"
        folder.mkdir(parents=True)
        file_path = folder / "photo.jpg"
        file_path.write_bytes(b"test")

        tagger = FolderTagger()
        tag = tagger.extract_tag(file_path)

        # All 3 levels are non-meaningful, so should return None
        assert tag is None


class TestIsTagInFilename:
    """Tests for is_tag_in_filename method."""

    def test_exact_match(self):
        tagger = FolderTagger()

        assert tagger.is_tag_in_filename("Paris_photo.jpg", "Paris") is True

    def test_case_insensitive(self):
        tagger = FolderTagger()

        assert tagger.is_tag_in_filename("paris_photo.jpg", "PARIS") is True
        assert tagger.is_tag_in_filename("PARIS_photo.jpg", "paris") is True

    def test_partial_match(self):
        tagger = FolderTagger()

        assert tagger.is_tag_in_filename("20240315_Paris_001.jpg", "Paris") is True

    def test_no_match(self):
        tagger = FolderTagger()

        assert tagger.is_tag_in_filename("IMG_001.jpg", "Paris") is False

    def test_fuzzy_match(self):
        tagger = FolderTagger(distance_threshold=0.75)

        # Very similar
        assert tagger.is_tag_in_filename("ParisTrip_001.jpg", "Paris_Trip") is True

    def test_empty_inputs(self):
        tagger = FolderTagger()

        assert tagger.is_tag_in_filename("", "Paris") is False
        assert tagger.is_tag_in_filename("photo.jpg", "") is False


class TestShouldAddTag:
    """Tests for should_add_tag method."""

    def test_should_add_new_tag(self, temp_dir: Path):
        folder = temp_dir / "Paris 2024"
        folder.mkdir()

        tagger = FolderTagger()
        should_add, tag = tagger.should_add_tag("IMG_001.jpg", folder)

        assert should_add is True
        assert tag == "Paris_2024"

    def test_should_not_add_existing_tag(self, temp_dir: Path):
        folder = temp_dir / "Paris"
        folder.mkdir()

        tagger = FolderTagger()
        should_add, tag = tagger.should_add_tag("Paris_001.jpg", folder)

        assert should_add is False
        assert tag == "Paris"

    def test_no_tag_for_ignored_folder(self, temp_dir: Path):
        # Create ignored folder under another ignored folder to exhaust walk
        folder = temp_dir / "DCIM" / "100APPLE" / "tosort"
        folder.mkdir(parents=True)

        tagger = FolderTagger()
        should_add, tag = tagger.should_add_tag("IMG_001.jpg", folder)

        # All levels are non-meaningful, so no tag
        assert should_add is False
        assert tag is None


class TestGetFolderTagFunction:
    """Tests for convenience function."""

    def test_get_folder_tag(self, temp_dir: Path):
        folder = temp_dir / "Vacation 2024"
        folder.mkdir()

        tag = get_folder_tag(folder)

        assert tag == "Vacation_2024"

    def test_get_folder_tag_none(self, temp_dir: Path):
        # Create multiple ignored folder levels
        folder = temp_dir / "DCIM" / "100APPLE" / "tosort"
        folder.mkdir(parents=True)

        tag = get_folder_tag(folder)

        # All 3 levels are ignored, so returns None
        assert tag is None
