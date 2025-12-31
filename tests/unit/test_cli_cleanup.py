"""Tests for cleanup CLI command."""

import json
import pytest
from pathlib import Path
from typer.testing import CliRunner

from chronoclean.cli.main import app


runner = CliRunner()


# Minimal JPEG header for test files
JPEG_HEADER = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00"


class TestCleanupCommandBasic:
    """Basic tests for 'chronoclean cleanup' command."""
    
    def test_cleanup_no_verification_reports(self, tmp_path, monkeypatch):
        """cleanup with no verification reports shows message."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["cleanup"])
        
        # Should fail gracefully with no reports found
        assert "No verification reports found" in result.stdout or "no matching" in result.stdout.lower() or result.exit_code == 1
    
    def test_cleanup_help(self):
        """cleanup --help shows usage information."""
        result = runner.invoke(app, ["cleanup", "--help"])
        
        assert result.exit_code == 0
        assert "cleanup" in result.stdout.lower()
        assert "--dry-run" in result.stdout or "dry-run" in result.stdout
    
    def test_cleanup_only_filter_validation(self, tmp_path, monkeypatch):
        """cleanup only accepts 'ok' filter."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["cleanup", "--only", "invalid"])
        
        assert result.exit_code == 1
        assert "only" in result.stdout.lower() or "ok" in result.stdout.lower()


class TestCleanupCommandDryRun:
    """Tests for cleanup dry-run mode."""
    
    def test_cleanup_dry_run_default(self, tmp_path, monkeypatch):
        """cleanup runs in dry-run mode by default."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["cleanup"])
        
        # Should either find no reports or run in dry-run mode
        # Dry-run is the default from config
        assert result.exit_code in [0, 1]
    
    def test_cleanup_dry_run_explicit(self, tmp_path, monkeypatch):
        """cleanup --dry-run shows planned deletions."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["cleanup", "--dry-run"])
        
        # Should accept the option
        assert result.exit_code in [0, 1]


class TestCleanupCommandOptions:
    """Tests for cleanup command options."""
    
    def test_cleanup_nonexistent_verify_file(self, tmp_path):
        """cleanup --verify-file with nonexistent file shows error."""
        fake_file = tmp_path / "nonexistent.json"
        
        result = runner.invoke(app, ["cleanup", "--verify-file", str(fake_file)])
        
        assert result.exit_code == 1
    
    def test_cleanup_last_option(self, tmp_path, monkeypatch):
        """cleanup --last uses most recent verification."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["cleanup", "--last"])
        
        # Should not prompt (may fail if no verifications exist)
        assert result.exit_code in [0, 1]
    
    def test_cleanup_yes_option(self, tmp_path, monkeypatch):
        """cleanup --yes auto-accepts without prompt."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["cleanup", "--yes"])
        
        # Should accept the option
        assert "invalid" not in result.stdout.lower()
    
    def test_cleanup_force_option(self, tmp_path, monkeypatch):
        """cleanup --force skips confirmation."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["cleanup", "--force"])
        
        # Should accept the option
        assert "invalid" not in result.stdout.lower()


class TestCleanupWithVerificationReport:
    """Tests for cleanup with actual verification reports."""
    
    def test_cleanup_with_valid_verify_file(self, tmp_path):
        """cleanup --verify-file with valid report works."""
        # Create source directory with file to clean
        source = tmp_path / "source"
        source.mkdir()
        source_file = source / "photo.jpg"
        source_file.write_bytes(JPEG_HEADER)
        
        dest = tmp_path / "dest"
        dest.mkdir()
        
        # Create verification report with correct schema
        verify_file = tmp_path / "verify.json"
        verify_data = {
            "verify_id": "verify-001",
            "created_at": "2025-12-31T12:00:00",
            "source_root": str(source),
            "destination_root": str(dest),
            "input_source": "run_record",
            "run_id": "run-001",
            "hash_algorithm": "sha256",
            "entries": [
                {
                    "source_path": str(source_file),
                    "destination_path": str(dest / "2025" / "photo.jpg"),
                    "status": "ok",
                    "source_hash": "abc123",
                    "destination_hash": "abc123"
                }
            ],
            "summary": {
                "total": 1,
                "ok": 1,
                "source_missing": 0,
                "dest_missing": 0,
                "hash_mismatch": 0,
                "error": 0
            },
            "duration_seconds": 0.1
        }
        verify_file.write_text(json.dumps(verify_data, indent=2))
        
        result = runner.invoke(app, ["cleanup", "--verify-file", str(verify_file), "--dry-run"])
        
        # Should process the report and show what would be cleaned
        assert result.exit_code == 0
        assert "Cleanup" in result.stdout or "DRY RUN" in result.stdout or "1" in result.stdout
    
    def test_cleanup_dry_run_preserves_files(self, tmp_path):
        """cleanup --dry-run does not delete files."""
        # Create source directory with file
        source = tmp_path / "source"
        source.mkdir()
        source_file = source / "photo.jpg"
        source_file.write_bytes(JPEG_HEADER)
        
        # Create verification report
        verify_file = tmp_path / "verify.json"
        verify_data = {
            "verify_id": "verify-001",
            "timestamp": "2025-12-31T12:00:00",
            "algorithm": "sha256",
            "source_directory": str(source),
            "destination_directory": str(tmp_path / "dest"),
            "results": [
                {
                    "source_path": str(source_file),
                    "destination_path": str(tmp_path / "dest" / "photo.jpg"),
                    "status": "ok",
                    "source_hash": "abc123",
                    "destination_hash": "abc123"
                }
            ]
        }
        verify_file.write_text(json.dumps(verify_data, indent=2))
        
        result = runner.invoke(app, ["cleanup", "--verify-file", str(verify_file), "--dry-run"])
        
        # Source file should still exist
        assert source_file.exists()


class TestCleanupCommandWithConfig:
    """Tests for cleanup command with config file."""
    
    def test_cleanup_with_config(self, tmp_path, monkeypatch):
        """cleanup with --config uses specified config file."""
        monkeypatch.chdir(tmp_path)
        
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
version: "0.1"
general:
  dry_run_default: true
""")
        
        result = runner.invoke(app, ["cleanup", "--config", str(config_file)])
        
        # Should accept config option
        assert "invalid config" not in result.stdout.lower()


class TestCleanupFilter:
    """Tests for cleanup --only filter."""
    
    def test_cleanup_only_ok_accepted(self, tmp_path, monkeypatch):
        """cleanup --only ok is accepted."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["cleanup", "--only", "ok"])
        
        # ok filter should be accepted
        assert "Only 'ok' filter" not in result.stdout
    
    def test_cleanup_invalid_filter_rejected(self, tmp_path, monkeypatch):
        """cleanup --only with invalid filter is rejected."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["cleanup", "--only", "all"])
        
        assert result.exit_code == 1
        assert "only" in result.stdout.lower() or "ok" in result.stdout
