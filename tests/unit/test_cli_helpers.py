"""Unit tests for CLI helper functions."""

import pytest

from chronoclean.cli.main import _build_date_priority
from chronoclean.config.loader import ChronoCleanConfig


class TestBuildDatePriority:
    """Tests for _build_date_priority function."""

    def test_default_priority_with_filename_enabled_by_default(self):
        """Default config has filename_date.enabled=True, so filename is included."""
        cfg = ChronoCleanConfig()
        # Default: filename_date.enabled = True
        
        result = _build_date_priority(cfg)
        
        # v0.3: Default priority is ["exif", "video_metadata", "filename", "filesystem", "folder_name"]
        assert "filename" in result
        assert "video_metadata" in result
        # filename should be after video_metadata
        assert result.index("filename") > result.index("video_metadata")

    def test_filename_enabled_adds_to_priority(self):
        """When filename_date.enabled, filename is in the priority list."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = True
        cfg.filename_date.priority = "after_exif"
        
        result = _build_date_priority(cfg)
        
        assert "filename" in result

    def test_filename_disabled_strips_from_priority(self):
        """When filename_date.enabled=False, filename is stripped even if in fallback_date_priority."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = False
        # Use a priority list with filename
        cfg.sorting.fallback_date_priority = ["exif", "filename", "filesystem", "folder_name"]
        
        result = _build_date_priority(cfg)
        
        # filename should be stripped since feature is disabled
        assert "filename" not in result
        assert result == ["exif", "filesystem", "folder_name"]

    def test_filename_disabled_handles_filename_only_priority(self):
        """Edge case: priority list with only filename when disabled."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = False
        cfg.sorting.fallback_date_priority = ["filename"]
        
        result = _build_date_priority(cfg)
        
        assert result == []

    def test_filename_enabled_before_exif(self):
        """priority='before_exif' puts filename at the start."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = True
        cfg.filename_date.priority = "before_exif"
        # Use priority list without filename to test insertion
        cfg.sorting.fallback_date_priority = ["exif", "filesystem", "folder_name"]
        
        result = _build_date_priority(cfg)
        
        assert result[0] == "filename"
        assert "exif" in result

    def test_filename_enabled_after_exif(self):
        """priority='after_exif' puts filename after exif."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = True
        cfg.filename_date.priority = "after_exif"
        # Use priority list without filename to test insertion
        cfg.sorting.fallback_date_priority = ["exif", "filesystem", "folder_name"]
        
        result = _build_date_priority(cfg)
        
        exif_idx = result.index("exif")
        filename_idx = result.index("filename")
        assert filename_idx == exif_idx + 1

    def test_filename_enabled_after_filesystem(self):
        """priority='after_filesystem' puts filename after filesystem."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = True
        cfg.filename_date.priority = "after_filesystem"
        # Use priority list without filename to test insertion
        cfg.sorting.fallback_date_priority = ["exif", "filesystem", "folder_name"]
        
        result = _build_date_priority(cfg)
        
        fs_idx = result.index("filesystem")
        filename_idx = result.index("filename")
        assert filename_idx == fs_idx + 1

    def test_filename_already_in_priority_not_duplicated(self):
        """If filename already in fallback_date_priority, don't add again."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = True
        cfg.filename_date.priority = "after_exif"
        cfg.sorting.fallback_date_priority = ["exif", "filename", "filesystem"]
        
        result = _build_date_priority(cfg)
        
        # Should keep existing position, not add again
        assert result.count("filename") == 1
        assert result == ["exif", "filename", "filesystem"]

    def test_filename_after_exif_when_exif_missing(self):
        """priority='after_exif' with no exif in list puts filename at start."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = True
        cfg.filename_date.priority = "after_exif"
        cfg.sorting.fallback_date_priority = ["filesystem", "folder_name"]
        
        result = _build_date_priority(cfg)
        
        # No exif in list, so filename goes at beginning
        assert result[0] == "filename"

    def test_filename_after_filesystem_when_filesystem_missing_falls_back_to_exif(self):
        """priority='after_filesystem' with no filesystem falls back to after_exif."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = True
        cfg.filename_date.priority = "after_filesystem"
        cfg.sorting.fallback_date_priority = ["exif", "folder_name"]
        
        result = _build_date_priority(cfg)
        
        # No filesystem in list, but exif is present, so filename goes after exif
        exif_idx = result.index("exif")
        filename_idx = result.index("filename")
        assert filename_idx == exif_idx + 1

    def test_filename_after_filesystem_when_both_missing_appends(self):
        """priority='after_filesystem' with no filesystem/exif appends to end."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = True
        cfg.filename_date.priority = "after_filesystem"
        cfg.sorting.fallback_date_priority = ["folder_name"]
        
        result = _build_date_priority(cfg)
        
        # No filesystem or exif, so filename goes at end
        assert result[-1] == "filename"

    def test_default_priority_value(self):
        """Default priority setting is 'after_exif'."""
        cfg = ChronoCleanConfig()
        cfg.filename_date.enabled = True
        # Use priority list without filename to test insertion
        cfg.sorting.fallback_date_priority = ["exif", "filesystem", "folder_name"]
        
        result = _build_date_priority(cfg)
        
        # Default is after_exif
        assert "filename" in result
        exif_idx = result.index("exif")
        filename_idx = result.index("filename")
        assert filename_idx == exif_idx + 1
