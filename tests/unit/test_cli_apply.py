"""Tests for apply CLI command."""

import pytest
from pathlib import Path
from typer.testing import CliRunner

from chronoclean.cli.main import app


runner = CliRunner()


# Minimal JPEG header for test files
JPEG_HEADER = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00"


class TestApplyCommandDryRun:
    """Tests for 'chronoclean apply' in dry-run mode."""
    
    def test_apply_dry_run_default(self, tmp_path, monkeypatch):
        """apply runs in dry-run mode by default."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest)])
        
        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
    
    def test_apply_dry_run_explicit(self, tmp_path, monkeypatch):
        """apply --dry-run shows planned changes without executing."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--dry-run"])
        
        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        # Source file should still exist
        assert (source / "photo.jpg").exists()
    
    def test_apply_empty_source(self, tmp_path, monkeypatch):
        """apply on empty source directory shows warning."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        
        result = runner.invoke(app, ["apply", str(source), str(dest)])
        
        assert result.exit_code == 0
        assert "No files found" in result.stdout
    
    def test_apply_shows_file_count(self, tmp_path, monkeypatch):
        """apply shows number of files found."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        for i in range(3):
            (source / f"photo_{i}.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest)])
        
        assert result.exit_code == 0
        assert "3" in result.stdout or "Found 3" in result.stdout
    
    def test_apply_shows_structure(self, tmp_path, monkeypatch):
        """apply displays folder structure being used."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest)])
        
        assert result.exit_code == 0
        assert "Structure:" in result.stdout


class TestApplyCommandLiveMode:
    """Tests for 'chronoclean apply' in live mode."""
    
    def test_apply_no_dry_run_requires_confirmation(self, tmp_path, monkeypatch):
        """apply --no-dry-run requires confirmation by default."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        # Answer 'n' to confirmation prompt
        result = runner.invoke(app, ["apply", str(source), str(dest), "--no-dry-run"], input="n\n")
        
        assert result.exit_code == 0
        assert "Aborted" in result.stdout
        # File should still be in source
        assert (source / "photo.jpg").exists()
    
    def test_apply_force_skips_confirmation(self, tmp_path, monkeypatch):
        """apply --no-dry-run --force skips confirmation."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--no-dry-run", "--force"])
        
        assert result.exit_code == 0
        # Should have processed without asking
        assert "Aborted" not in result.stdout
    
    def test_apply_copy_mode_default(self, tmp_path, monkeypatch):
        """apply uses copy mode by default (not move)."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--no-dry-run", "--force"])
        
        assert result.exit_code == 0
        # Original should still exist (copy, not move)
        assert (source / "photo.jpg").exists()
    
    def test_apply_move_mode(self, tmp_path, monkeypatch):
        """apply --move moves files instead of copying."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--no-dry-run", "--force", "--move"])
        
        assert result.exit_code == 0
        assert "MOVE" in result.stdout


class TestApplyCommandOptions:
    """Tests for apply command options."""
    
    def test_apply_with_limit(self, tmp_path, monkeypatch):
        """apply --limit restricts files processed."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        for i in range(10):
            (source / f"photo_{i}.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--limit", "3"])
        
        assert result.exit_code == 0
        # Should show only 3 files found
        assert "3" in result.stdout
    
    def test_apply_no_recursive(self, tmp_path, monkeypatch):
        """apply --no-recursive skips subdirectories."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        subdir = source / "subdir"
        subdir.mkdir()
        (source / "root.jpg").write_bytes(JPEG_HEADER)
        (subdir / "nested.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--no-recursive"])
        
        assert result.exit_code == 0
        # Should only find root file
        assert "Found 1" in result.stdout or "1 files" in result.stdout.lower()
    
    def test_apply_custom_structure(self, tmp_path, monkeypatch):
        """apply --structure uses custom folder structure."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--structure", "YYYY"])
        
        assert result.exit_code == 0
        assert "YYYY" in result.stdout
    
    def test_apply_with_rename(self, tmp_path, monkeypatch):
        """apply --rename enables file renaming."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--rename"])
        
        assert result.exit_code == 0
        assert "Renaming: enabled" in result.stdout
    
    def test_apply_with_tag_names(self, tmp_path, monkeypatch):
        """apply --tag-names enables folder tag in filenames."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--tag-names"])
        
        assert result.exit_code == 0
        assert "Folder tags: enabled" in result.stdout
    
    def test_apply_with_config(self, tmp_path, monkeypatch):
        """apply with --config uses specified config file."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
version: "0.1"
sorting:
  folder_structure: "YYYY"
""")
        
        result = runner.invoke(app, ["apply", str(source), str(dest), "--config", str(config_file)])
        
        assert result.exit_code == 0
        assert "YYYY" in result.stdout


class TestApplyCommandErrors:
    """Error handling tests for apply command."""
    
    def test_apply_nonexistent_source(self, tmp_path, monkeypatch):
        """apply with nonexistent source shows error."""
        monkeypatch.chdir(tmp_path)
        dest = tmp_path / "dest"
        dest.mkdir()
        fake_source = tmp_path / "does_not_exist"
        
        result = runner.invoke(app, ["apply", str(fake_source), str(dest)])
        
        assert result.exit_code == 1
    
    def test_apply_source_is_file(self, tmp_path, monkeypatch):
        """apply with file as source shows error."""
        monkeypatch.chdir(tmp_path)
        source_file = tmp_path / "file.txt"
        source_file.write_text("test")
        dest = tmp_path / "dest"
        dest.mkdir()
        
        result = runner.invoke(app, ["apply", str(source_file), str(dest)])
        
        assert result.exit_code == 1


class TestApplyCommandDisplay:
    """Tests for apply command output display."""
    
    def test_apply_shows_operation_type(self, tmp_path, monkeypatch):
        """apply displays operation type (COPY/MOVE)."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest)])
        
        assert result.exit_code == 0
        assert "Operation:" in result.stdout
        assert "COPY" in result.stdout
    
    def test_apply_shows_source_and_dest(self, tmp_path, monkeypatch):
        """apply displays source and destination paths."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["apply", str(source), str(dest)])
        
        assert result.exit_code == 0
        assert "Source:" in result.stdout
        assert "Destination:" in result.stdout
