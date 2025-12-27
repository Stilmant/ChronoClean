"""Unit tests for chronoclean.config module."""

from pathlib import Path

import pytest

from chronoclean.config.loader import ConfigError, ConfigLoader
from chronoclean.config.schema import (
    ChronoCleanConfig,
    FolderTagsConfig,
    GeneralConfig,
    LoggingConfig,
    PathsConfig,
    RenamingConfig,
    ScanConfig,
    SortingConfig,
)


class TestChronoCleanConfig:
    """Tests for ChronoCleanConfig dataclass."""

    def test_default_config(self):
        config = ChronoCleanConfig()

        assert config.version == "1.0"
        assert config.general is not None
        assert config.paths is not None
        assert config.sorting is not None

    def test_all_supported_extensions(self):
        config = ChronoCleanConfig()
        extensions = config.all_supported_extensions

        assert ".jpg" in extensions
        assert ".mp4" in extensions
        assert ".cr2" in extensions


class TestGeneralConfig:
    """Tests for GeneralConfig dataclass."""

    def test_defaults(self):
        config = GeneralConfig()

        assert config.timezone == "local"
        assert config.recursive is True
        assert config.include_videos is True
        assert config.ignore_hidden_files is True
        assert config.dry_run_default is True
        assert config.output_folder == ".chronoclean"

    def test_custom_values(self):
        config = GeneralConfig(
            recursive=False,
            include_videos=False,
            dry_run_default=False,
        )

        assert config.recursive is False
        assert config.include_videos is False
        assert config.dry_run_default is False


class TestPathsConfig:
    """Tests for PathsConfig dataclass."""

    def test_defaults_are_none(self):
        config = PathsConfig()

        assert config.source is None
        assert config.destination is None
        assert config.temp_folder is None

    def test_with_paths(self):
        config = PathsConfig(
            source=Path("/photos/inbox"),
            destination=Path("/photos/sorted"),
        )

        assert config.source == Path("/photos/inbox")
        assert config.destination == Path("/photos/sorted")


class TestScanConfig:
    """Tests for ScanConfig dataclass."""

    def test_defaults(self):
        config = ScanConfig()

        assert ".jpg" in config.image_extensions
        assert ".mp4" in config.video_extensions
        assert ".cr2" in config.raw_extensions
        assert config.skip_exif_errors is True
        assert config.limit is None

    def test_custom_extensions(self):
        config = ScanConfig(
            image_extensions=[".jpg", ".png"],
            video_extensions=[".mp4"],
        )

        assert len(config.image_extensions) == 2
        assert len(config.video_extensions) == 1


class TestSortingConfig:
    """Tests for SortingConfig dataclass."""

    def test_defaults(self):
        config = SortingConfig()

        assert config.folder_structure == "YYYY/MM"
        assert "exif" in config.fallback_date_priority
        assert config.include_day is False

    def test_with_day(self):
        config = SortingConfig(
            folder_structure="YYYY/MM/DD",
            include_day=True,
        )

        assert config.folder_structure == "YYYY/MM/DD"
        assert config.include_day is True


class TestFolderTagsConfig:
    """Tests for FolderTagsConfig dataclass."""

    def test_defaults(self):
        config = FolderTagsConfig()

        assert config.enabled is False
        assert config.min_length == 3
        assert config.max_length == 40
        assert "tosort" in config.ignore_list
        assert config.distance_threshold == 0.75

    def test_custom_ignore_list(self):
        config = FolderTagsConfig(
            ignore_list=["custom", "ignore"],
            force_list=["always_use"],
        )

        assert "custom" in config.ignore_list
        assert "always_use" in config.force_list


class TestRenamingConfig:
    """Tests for RenamingConfig dataclass."""

    def test_defaults(self):
        config = RenamingConfig()

        assert config.enabled is False
        assert config.pattern == "{date}_{time}"
        assert config.date_format == "%Y%m%d"
        assert config.time_format == "%H%M%S"
        assert config.lowercase_extensions is True

    def test_custom_pattern(self):
        config = RenamingConfig(
            enabled=True,
            pattern="{date}_{time}_{tag}",
        )

        assert config.enabled is True
        assert "{tag}" in config.pattern


class TestLoggingConfig:
    """Tests for LoggingConfig dataclass."""

    def test_defaults(self):
        config = LoggingConfig()

        assert config.level == "info"
        assert config.color_output is True
        assert config.log_to_file is True


class TestConfigLoader:
    """Tests for ConfigLoader."""

    def test_load_defaults(self):
        """Load with no config file returns defaults."""
        config = ConfigLoader.load()

        assert isinstance(config, ChronoCleanConfig)
        assert config.general.recursive is True

    def test_load_from_yaml(self, temp_dir: Path):
        """Load from a YAML file."""
        config_path = temp_dir / "test_config.yaml"
        config_path.write_text("""
version: "2.0"
general:
  recursive: false
  include_videos: false
sorting:
  folder_structure: "YYYY/MM/DD"
""")

        config = ConfigLoader.load(config_path)

        assert config.version == "2.0"
        assert config.general.recursive is False
        assert config.general.include_videos is False
        assert config.sorting.folder_structure == "YYYY/MM/DD"

    def test_load_partial_config(self, temp_dir: Path):
        """Partial config merges with defaults."""
        config_path = temp_dir / "partial.yaml"
        config_path.write_text("""
general:
  recursive: false
""")

        config = ConfigLoader.load(config_path)

        assert config.general.recursive is False
        # Other defaults preserved
        assert config.general.include_videos is True
        assert config.sorting.folder_structure == "YYYY/MM"

    def test_load_missing_file(self, temp_dir: Path):
        """Loading non-existent file raises error."""
        config_path = temp_dir / "nonexistent.yaml"

        with pytest.raises(ConfigError, match="not found"):
            ConfigLoader.load(config_path)

    def test_load_invalid_yaml(self, temp_dir: Path):
        """Loading invalid YAML raises error."""
        config_path = temp_dir / "invalid.yaml"
        config_path.write_text("invalid: yaml: content: [")

        with pytest.raises(ConfigError, match="Invalid YAML"):
            ConfigLoader.load(config_path)

    def test_load_empty_yaml(self, temp_dir: Path):
        """Loading empty YAML returns defaults."""
        config_path = temp_dir / "empty.yaml"
        config_path.write_text("")

        config = ConfigLoader.load(config_path)

        assert isinstance(config, ChronoCleanConfig)
        assert config.general.recursive is True

    def test_load_paths_config(self, temp_dir: Path):
        """Load paths from YAML."""
        config_path = temp_dir / "paths.yaml"
        config_path.write_text("""
paths:
  source: "/photos/inbox"
  destination: "/photos/sorted"
""")

        config = ConfigLoader.load(config_path)

        assert config.paths.source == Path("/photos/inbox")
        assert config.paths.destination == Path("/photos/sorted")

    def test_load_folder_tags(self, temp_dir: Path):
        """Load folder tags config."""
        config_path = temp_dir / "tags.yaml"
        config_path.write_text("""
folder_tags:
  enabled: true
  min_length: 5
  ignore_list:
    - custom_ignore
    - another
  force_list:
    - always
""")

        config = ConfigLoader.load(config_path)

        assert config.folder_tags.enabled is True
        assert config.folder_tags.min_length == 5
        assert "custom_ignore" in config.folder_tags.ignore_list
        assert "always" in config.folder_tags.force_list


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_validate_valid_config(self):
        """Valid config returns no errors."""
        config = ChronoCleanConfig()
        errors = ConfigLoader.validate(config)

        assert errors == []

    def test_validate_invalid_folder_structure(self):
        """Invalid folder structure returns error."""
        config = ChronoCleanConfig()
        config.sorting.folder_structure = "INVALID"

        errors = ConfigLoader.validate(config)

        assert len(errors) > 0
        assert any("folder_structure" in e for e in errors)

    def test_validate_invalid_fallback_source(self):
        """Invalid fallback source returns error."""
        config = ChronoCleanConfig()
        config.sorting.fallback_date_priority = ["invalid_source"]

        errors = ConfigLoader.validate(config)

        assert len(errors) > 0
        assert any("fallback" in e.lower() for e in errors)

    def test_validate_invalid_log_level(self):
        """Invalid log level returns error."""
        config = ChronoCleanConfig()
        config.logging.level = "invalid"

        errors = ConfigLoader.validate(config)

        assert len(errors) > 0
        assert any("level" in e.lower() for e in errors)

    def test_validate_invalid_distance_threshold(self):
        """Distance threshold out of range returns error."""
        config = ChronoCleanConfig()
        config.folder_tags.distance_threshold = 1.5

        errors = ConfigLoader.validate(config)

        assert len(errors) > 0
        assert any("threshold" in e.lower() for e in errors)

    def test_validate_invalid_min_length(self):
        """Min length < 1 returns error."""
        config = ChronoCleanConfig()
        config.folder_tags.min_length = 0

        errors = ConfigLoader.validate(config)

        assert len(errors) > 0

    def test_validate_max_less_than_min(self):
        """Max length < min length returns error."""
        config = ChronoCleanConfig()
        config.folder_tags.min_length = 10
        config.folder_tags.max_length = 5

        errors = ConfigLoader.validate(config)

        assert len(errors) > 0
        assert any("max_length" in e.lower() for e in errors)
