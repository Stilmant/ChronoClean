"""Tests for CLI configuration integration."""

import tempfile
from pathlib import Path

import pytest
import yaml

from chronoclean.config.loader import ConfigLoader
from chronoclean.config.schema import ChronoCleanConfig


class TestCLIConfigIntegration:
    """Tests for CLI using config file values."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_config(self, temp_dir):
        """Create a sample config file."""
        config_data = {
            "version": "1.0",
            "general": {
                "recursive": False,
                "include_videos": False,
                "ignore_hidden_files": True,
                "dry_run_default": False,
            },
            "scan": {
                "image_extensions": [".jpg", ".png"],
                "video_extensions": [".mp4"],
                "raw_extensions": [".cr2"],
                "limit": 50,
            },
            "sorting": {
                "folder_structure": "YYYY/MM/DD",
                "fallback_date_priority": ["exif", "folder_name", "filesystem"],
            },
            "folder_tags": {
                "enabled": True,
                "min_length": 4,
                "max_length": 30,
                "ignore_list": ["temp", "misc"],
                "force_list": ["vacation"],
                "distance_threshold": 0.8,
            },
            "renaming": {
                "enabled": True,
                "pattern": "{date}_{time}_{tag}",
                "date_format": "%Y-%m-%d",
                "time_format": "%H%M",
            },
        }
        config_path = temp_dir / "chronoclean.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
        return config_path

    def test_load_config_from_file(self, sample_config):
        """Config file is loaded correctly."""
        cfg = ConfigLoader.load(sample_config)

        assert cfg.general.recursive is False
        assert cfg.general.include_videos is False
        assert cfg.general.dry_run_default is False
        assert cfg.scan.limit == 50
        assert cfg.sorting.folder_structure == "YYYY/MM/DD"
        assert cfg.folder_tags.enabled is True
        assert cfg.renaming.enabled is True

    def test_config_folder_tags_settings(self, sample_config):
        """Folder tag settings are loaded."""
        cfg = ConfigLoader.load(sample_config)

        assert cfg.folder_tags.min_length == 4
        assert cfg.folder_tags.max_length == 30
        assert "temp" in cfg.folder_tags.ignore_list
        assert "vacation" in cfg.folder_tags.force_list
        assert cfg.folder_tags.distance_threshold == 0.8

    def test_config_renaming_settings(self, sample_config):
        """Renaming settings are loaded."""
        cfg = ConfigLoader.load(sample_config)

        assert cfg.renaming.pattern == "{date}_{time}_{tag}"
        assert cfg.renaming.date_format == "%Y-%m-%d"
        assert cfg.renaming.time_format == "%H%M"

    def test_config_fallback_priority(self, sample_config):
        """Fallback priority order is loaded."""
        cfg = ConfigLoader.load(sample_config)

        assert cfg.sorting.fallback_date_priority == ["exif", "folder_name", "filesystem"]

    def test_config_extensions(self, sample_config):
        """Custom extensions are loaded."""
        cfg = ConfigLoader.load(sample_config)

        assert cfg.scan.image_extensions == [".jpg", ".png"]
        assert cfg.scan.video_extensions == [".mp4"]
        assert cfg.scan.raw_extensions == [".cr2"]

    def test_default_config_when_no_file(self, temp_dir):
        """Default config is used when no file exists."""
        # Change to temp dir without config file
        cfg = ConfigLoader.load(None)

        # Should have defaults
        assert cfg.general.recursive is True
        assert cfg.general.include_videos is True
        assert cfg.general.dry_run_default is True

    def test_partial_config_merges_with_defaults(self, temp_dir):
        """Partial config file merges with defaults."""
        config_data = {
            "general": {
                "recursive": False,
            }
        }
        config_path = temp_dir / "partial.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        cfg = ConfigLoader.load(config_path)

        # Explicitly set value
        assert cfg.general.recursive is False
        # Default values
        assert cfg.general.include_videos is True
        assert cfg.sorting.folder_structure == "YYYY/MM"


class TestConfigHelperFunctions:
    """Tests for CLI helper functions."""

    def test_resolve_bool_cli_overrides_config_true(self):
        """CLI True overrides config False."""
        from chronoclean.cli.main import _resolve_bool

        result = _resolve_bool(True, False)
        assert result is True

    def test_resolve_bool_cli_overrides_config_false(self):
        """CLI False overrides config True."""
        from chronoclean.cli.main import _resolve_bool

        result = _resolve_bool(False, True)
        assert result is False

    def test_resolve_bool_none_uses_config(self):
        """CLI None uses config value."""
        from chronoclean.cli.main import _resolve_bool

        result = _resolve_bool(None, True)
        assert result is True

        result = _resolve_bool(None, False)
        assert result is False


class TestScannerWithConfig:
    """Tests for Scanner using config values."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_scanner_uses_config_extensions(self, temp_dir):
        """Scanner uses extensions from config."""
        from chronoclean.core.scanner import Scanner

        # Create files with different extensions
        (temp_dir / "photo.jpg").touch()
        (temp_dir / "photo.png").touch()
        (temp_dir / "photo.tiff").touch()
        (temp_dir / "video.mp4").touch()

        # Scanner with custom extensions (only jpg)
        scanner = Scanner(
            image_extensions={".jpg"},
            video_extensions=set(),
            raw_extensions=set(),
            include_videos=False,
        )

        result = scanner.scan(temp_dir)

        # Should only find .jpg
        assert result.total_files == 1
        assert result.files[0].source_path.suffix == ".jpg"

    def test_scanner_uses_config_ignore_hidden(self, temp_dir):
        """Scanner respects ignore_hidden from config."""
        from chronoclean.core.scanner import Scanner

        # Create regular and hidden files
        (temp_dir / "photo.jpg").touch()
        hidden_dir = temp_dir / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "hidden_photo.jpg").touch()

        # Scanner ignoring hidden (default)
        scanner = Scanner(ignore_hidden=True)
        result = scanner.scan(temp_dir)
        assert result.total_files == 1

        # Scanner including hidden
        scanner = Scanner(ignore_hidden=False)
        result = scanner.scan(temp_dir)
        assert result.total_files == 2


class TestFolderTaggerWithConfig:
    """Tests for FolderTagger using config values."""

    def test_tagger_uses_config_ignore_list(self):
        """FolderTagger uses ignore list from config."""
        from chronoclean.core.folder_tagger import FolderTagger

        tagger = FolderTagger(ignore_list=["custom_ignore", "another"])

        assert tagger.is_meaningful("custom_ignore") is False
        assert tagger.is_meaningful("another") is False
        assert tagger.is_meaningful("vacation") is True  # Not in custom list

    def test_tagger_uses_config_force_list(self):
        """FolderTagger uses force list from config."""
        from chronoclean.core.folder_tagger import FolderTagger

        # "temp" would normally be ignored, but force list overrides
        tagger = FolderTagger(
            ignore_list=["temp"],
            force_list=["temp"],
        )

        assert tagger.is_meaningful("temp") is True

    def test_tagger_uses_config_length_limits(self):
        """FolderTagger uses length limits from config."""
        from chronoclean.core.folder_tagger import FolderTagger

        tagger = FolderTagger(min_length=5, max_length=10)

        assert tagger.is_meaningful("abc") is False  # Too short (3 < 5)
        assert tagger.is_meaningful("abcde") is True  # Exactly 5
        assert tagger.is_meaningful("abcdefghij") is True  # Exactly 10
        assert tagger.is_meaningful("abcdefghijk") is False  # Too long (11 > 10)


class TestDateInferenceWithConfig:
    """Tests for DateInferenceEngine using config values."""

    def test_engine_uses_config_priority(self):
        """DateInferenceEngine uses priority from config."""
        from chronoclean.core.date_inference import DateInferenceEngine

        # Custom priority: folder_name first
        engine = DateInferenceEngine(priority=["folder_name", "filesystem", "exif"])

        assert engine.priority == ["folder_name", "filesystem", "exif"]

    def test_engine_default_priority(self):
        """DateInferenceEngine has correct default priority."""
        from chronoclean.core.date_inference import DateInferenceEngine

        engine = DateInferenceEngine()

        # v0.3: Default priority includes video_metadata and filename
        assert engine.priority == ["exif", "video_metadata", "filename", "filesystem", "folder_name"]


class TestRenamerWithConfig:
    """Tests for Renamer using config values."""

    def test_renamer_uses_config_pattern(self):
        """Renamer uses pattern from config."""
        from datetime import datetime
        from pathlib import Path

        from chronoclean.core.renamer import Renamer

        renamer = Renamer(
            pattern="{date}-{time}",
            date_format="%Y_%m_%d",
            time_format="%H%M",
        )

        result = renamer.generate_filename(
            Path("photo.jpg"),
            datetime(2024, 3, 15, 14, 30, 0),
        )

        assert result == "2024_03_15-1430.jpg"

    def test_renamer_uses_config_tag_format(self):
        """Renamer uses tag format from config."""
        from datetime import datetime
        from pathlib import Path

        from chronoclean.core.renamer import Renamer

        renamer = Renamer(
            pattern="{date}_{time}",
            tag_format="-{tag}",  # Dash instead of underscore
        )

        result = renamer.generate_filename(
            Path("photo.jpg"),
            datetime(2024, 3, 15, 14, 30, 0),
            tag="Paris",
        )

        assert "-Paris" in result

    def test_renamer_uses_config_lowercase(self):
        """Renamer uses lowercase_ext from config."""
        from datetime import datetime
        from pathlib import Path

        from chronoclean.core.renamer import Renamer

        # Lowercase enabled (default)
        renamer = Renamer(lowercase_ext=True)
        result = renamer.generate_filename(
            Path("photo.JPG"),
            datetime(2024, 3, 15, 14, 30, 0),
        )
        assert result.endswith(".jpg")

        # Lowercase disabled
        renamer = Renamer(lowercase_ext=False)
        result = renamer.generate_filename(
            Path("photo.JPG"),
            datetime(2024, 3, 15, 14, 30, 0),
        )
        assert result.endswith(".JPG")
