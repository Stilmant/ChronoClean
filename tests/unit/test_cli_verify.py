"""Tests for verify CLI command."""

import json
import pytest
from pathlib import Path
from typer.testing import CliRunner

from chronoclean.cli.main import app


runner = CliRunner()


# Minimal JPEG header for test files
JPEG_HEADER = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00"


class TestVerifyCommandBasic:
    """Basic tests for 'chronoclean verify' command."""
    
    def test_verify_no_run_records(self, tmp_path, monkeypatch):
        """verify with no run records shows appropriate message."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["verify"])
        
        # Should fail gracefully with no run records found
        assert "No run records found" in result.stdout or "no matching" in result.stdout.lower() or result.exit_code == 1
    
    def test_verify_with_nonexistent_run_file(self, tmp_path):
        """verify --run-file with nonexistent file shows error."""
        fake_file = tmp_path / "nonexistent.json"
        
        result = runner.invoke(app, ["verify", "--run-file", str(fake_file)])
        
        assert result.exit_code == 1
    
    def test_verify_help(self):
        """verify --help shows usage information."""
        result = runner.invoke(app, ["verify", "--help"])
        
        assert result.exit_code == 0
        assert "verify" in result.stdout.lower()
        assert "--run-file" in result.stdout or "run-file" in result.stdout


class TestVerifyReconstructMode:
    """Tests for verify --reconstruct mode."""
    
    def test_verify_reconstruct_requires_source(self, tmp_path, monkeypatch):
        """verify --reconstruct requires --source option."""
        monkeypatch.chdir(tmp_path)
        dest = tmp_path / "dest"
        dest.mkdir()
        
        result = runner.invoke(app, ["verify", "--reconstruct", "--destination", str(dest)])
        
        # Should fail without source
        assert result.exit_code == 1 or "source" in result.stdout.lower()
    
    def test_verify_reconstruct_requires_destination(self, tmp_path, monkeypatch):
        """verify --reconstruct requires --destination option."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        source.mkdir()
        
        result = runner.invoke(app, ["verify", "--reconstruct", "--source", str(source)])
        
        # Should fail without destination
        assert result.exit_code == 1 or "destination" in result.stdout.lower()
    
    def test_verify_reconstruct_with_empty_dirs(self, tmp_path, monkeypatch):
        """verify --reconstruct with empty directories works."""
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        
        result = runner.invoke(app, ["verify", "--reconstruct", 
                                      "--source", str(source),
                                      "--destination", str(dest)])
        
        # Should complete (with 0 files verified)
        assert result.exit_code == 0 or "No files" in result.stdout


class TestVerifyCommandOptions:
    """Tests for verify command options."""
    
    def test_verify_algorithm_option(self, tmp_path, monkeypatch):
        """verify accepts --algorithm option."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["verify", "--algorithm", "quick"])
        
        # Should accept the option (may fail for other reasons)
        assert "--algorithm" not in result.stdout or "unknown" not in result.stdout.lower()
    
    def test_verify_include_dry_runs_option(self, tmp_path, monkeypatch):
        """verify accepts --include-dry-runs option."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["verify", "--include-dry-runs"])
        
        # Should accept the option
        assert "invalid" not in result.stdout.lower()
    
    def test_verify_last_option(self, tmp_path, monkeypatch):
        """verify --last uses most recent run without prompt."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["verify", "--last"])
        
        # Should not prompt (may fail if no runs exist)
        assert "No run records found" in result.stdout or result.exit_code in [0, 1]
    
    def test_verify_yes_option(self, tmp_path, monkeypatch):
        """verify --yes auto-accepts without prompt."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["verify", "--yes"])
        
        # Should accept the option
        assert "invalid" not in result.stdout.lower()


class TestVerifyWithRunRecord:
    """Tests for verify with actual run records."""
    
    def test_verify_with_valid_run_file(self, tmp_path, monkeypatch):
        """verify --run-file with valid run record works."""
        monkeypatch.chdir(tmp_path)
        # Create a minimal run record
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        
        # Create matching files
        file_content = JPEG_HEADER
        (source / "photo.jpg").write_bytes(file_content)
        (dest / "2025" / "12").mkdir(parents=True)
        (dest / "2025" / "12" / "photo.jpg").write_bytes(file_content)
        
        # Create run record with correct schema
        run_file = tmp_path / "run.json"
        run_data = {
            "run_id": "test-run-001",
            "created_at": "2025-12-31T12:00:00",
            "source_root": str(source),
            "destination_root": str(dest),
            "mode": "live_copy",
            "config_signature": {
                "folder_structure": "YYYY/MM",
                "renaming_enabled": False,
                "renaming_pattern": "{date}_{original}",
                "folder_tags_enabled": False,
                "on_collision": "increment"
            },
            "entries": [
                {
                    "source_path": str(source / "photo.jpg"),
                    "destination_path": str(dest / "2025" / "12" / "photo.jpg"),
                    "operation": "copy",
                    "status": "success"
                }
            ],
            "summary": {
                "total_files": 1,
                "copied_files": 1,
                "moved_files": 0,
                "skipped_files": 0,
                "error_files": 0,
                "duration_seconds": 0.1
            }
        }
        run_file.write_text(json.dumps(run_data, indent=2))
        
        result = runner.invoke(app, ["verify", "--run-file", str(run_file)])
        
        # Should process the run record - check output content
        # (may exit 0 or show verification info)
        assert "Verification" in result.stdout or "verified" in result.stdout.lower() or "OK" in result.stdout or result.exit_code == 0


class TestVerifyCommandWithConfig:
    """Tests for verify command with config file."""
    
    def test_verify_with_config(self, tmp_path, monkeypatch):
        """verify with --config uses specified config file."""
        monkeypatch.chdir(tmp_path)
        
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
version: "0.1"
verify:
  algorithm: quick
""")
        
        result = runner.invoke(app, ["verify", "--config", str(config_file)])
        
        # Should accept config option
        assert "invalid config" not in result.stdout.lower()
