"""Tests for scan CLI command."""

import pytest
from pathlib import Path
from typer.testing import CliRunner

from chronoclean.cli.main import app


runner = CliRunner()


# Minimal JPEG header for test files
JPEG_HEADER = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00"


class TestScanCommand:
    """Tests for 'chronoclean scan' command."""
    
    def test_scan_empty_directory(self, tmp_path):
        """scan on empty directory succeeds with 0 files."""
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "Scan Complete" in result.stdout
        assert "0" in result.stdout  # 0 files found
    
    def test_scan_single_image(self, tmp_path):
        """scan finds a single image file."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "Scan Complete" in result.stdout
        assert "1" in result.stdout  # 1 file found
    
    def test_scan_multiple_images(self, tmp_path):
        """scan finds multiple image files."""
        for i in range(5):
            (tmp_path / f"photo_{i}.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "Scan Complete" in result.stdout
        assert "5" in result.stdout
    
    def test_scan_nonexistent_directory(self, tmp_path):
        """scan on nonexistent directory shows error."""
        fake_path = tmp_path / "does_not_exist"
        
        result = runner.invoke(app, ["scan", str(fake_path)])
        
        assert result.exit_code == 1
        assert "does not exist" in result.stdout or "not found" in result.stdout.lower()
    
    def test_scan_file_instead_of_directory(self, tmp_path):
        """scan on a file (not directory) shows error."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        
        result = runner.invoke(app, ["scan", str(file_path)])
        
        assert result.exit_code == 1
        assert "not a directory" in result.stdout.lower() or "is not a directory" in result.stdout.lower()
    
    def test_scan_with_limit(self, tmp_path):
        """scan --limit restricts number of files processed."""
        for i in range(10):
            (tmp_path / f"photo_{i}.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path), "--limit", "3"])
        
        assert result.exit_code == 0
        assert "Scan Complete" in result.stdout
        # Should process at most 3 files
        assert "3" in result.stdout
    
    def test_scan_recursive_default(self, tmp_path):
        """scan recurses into subdirectories by default."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.jpg").write_bytes(JPEG_HEADER)
        (subdir / "nested.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "2" in result.stdout  # Both files found
    
    def test_scan_no_recursive(self, tmp_path):
        """scan --no-recursive skips subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.jpg").write_bytes(JPEG_HEADER)
        (subdir / "nested.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path), "--no-recursive"])
        
        assert result.exit_code == 0
        assert "1" in result.stdout  # Only root file found
    
    def test_scan_with_videos_flag(self, tmp_path):
        """scan --videos includes video files."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        (tmp_path / "video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        
        result = runner.invoke(app, ["scan", str(tmp_path), "--videos"])
        
        assert result.exit_code == 0
        assert "2" in result.stdout  # Both files found
    
    def test_scan_shows_summary_table(self, tmp_path):
        """scan displays summary table with metrics."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        # Summary table should include these metrics
        assert "Total files found" in result.stdout
        assert "Files processed" in result.stdout
        assert "Scan duration" in result.stdout
    
    def test_scan_with_config_file(self, tmp_path):
        """scan with --config uses specified config file."""
        # Create a config file
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
version: "0.1"
general:
  recursive: false
""")
        
        # Create files in nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.jpg").write_bytes(JPEG_HEADER)
        (subdir / "nested.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path), "--config", str(config_file)])
        
        assert result.exit_code == 0
        # Config says non-recursive, so should only find 1 file
        assert "1" in result.stdout
    
    def test_scan_displays_source_path(self, tmp_path):
        """scan shows the source directory being scanned."""
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "Scanning" in result.stdout


class TestScanCommandEdgeCases:
    """Edge case tests for scan command."""
    
    def test_scan_hidden_files_excluded(self, tmp_path):
        """scan excludes hidden files by default."""
        (tmp_path / "visible.jpg").write_bytes(JPEG_HEADER)
        (tmp_path / ".hidden.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        # Should only find visible file
        assert "1" in result.stdout
    
    def test_scan_unsupported_extensions_skipped(self, tmp_path):
        """scan skips files with unsupported extensions."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        (tmp_path / "document.pdf").write_bytes(b"PDF")
        (tmp_path / "data.txt").write_text("text")
        
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        # Should only find jpg
        assert "1" in result.stdout
    
    def test_scan_mixed_case_extensions(self, tmp_path):
        """scan handles mixed-case extensions."""
        (tmp_path / "photo1.jpg").write_bytes(JPEG_HEADER)
        (tmp_path / "photo2.JPG").write_bytes(JPEG_HEADER)
        (tmp_path / "photo3.Jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "3" in result.stdout
    
    def test_scan_deeply_nested(self, tmp_path):
        """scan handles deeply nested directories."""
        deep = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        (deep / "deep.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "1" in result.stdout
    
    def test_scan_empty_subdirectories(self, tmp_path):
        """scan handles empty subdirectories gracefully."""
        (tmp_path / "empty1").mkdir()
        (tmp_path / "empty2").mkdir()
        (tmp_path / "has_file").mkdir()
        (tmp_path / "has_file" / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["scan", str(tmp_path)])
        
        assert result.exit_code == 0
        assert "1" in result.stdout
