"""Tests for doctor CLI command."""

import pytest
from pathlib import Path
from unittest.mock import patch
from typer.testing import CliRunner

from chronoclean import __version__
from chronoclean.cli.main import app


runner = CliRunner()


class TestDoctorCommand:
    """Tests for 'chronoclean doctor' command."""
    
    def test_doctor_runs_successfully(self):
        """doctor command runs without errors."""
        result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        assert "ChronoClean Doctor" in result.stdout
    
    def test_doctor_shows_version(self):
        """doctor displays ChronoClean version."""
        result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        assert __version__ in result.stdout
    
    def test_doctor_checks_ffprobe(self):
        """doctor checks ffprobe availability."""
        result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        assert "ffprobe" in result.stdout.lower()
    
    def test_doctor_checks_hachoir(self):
        """doctor checks hachoir availability."""
        result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        assert "hachoir" in result.stdout.lower()
    
    def test_doctor_checks_exifread(self):
        """doctor checks exifread availability."""
        result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        assert "exifread" in result.stdout.lower()
    
    def test_doctor_shows_python_info(self):
        """doctor displays Python environment info."""
        result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        assert "python" in result.stdout.lower()
    
    def test_doctor_shows_dependencies_table(self):
        """doctor shows external dependencies table."""
        result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        assert "Dependencies" in result.stdout or "Component" in result.stdout
    
    def test_doctor_with_config(self, tmp_path):
        """doctor with --config uses specified config file."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
version: "0.1"
video_metadata:
  ffprobe_path: "/nonexistent/ffprobe"
""")
        
        result = runner.invoke(app, ["doctor", "--config", str(config_file)])
        
        # Should run (may show warnings about ffprobe path)
        assert result.exit_code == 0


class TestDoctorCommandWithMocks:
    """Tests for doctor command with mocked dependencies."""
    
    def test_doctor_ffprobe_not_available(self):
        """doctor handles missing ffprobe gracefully."""
        with patch("chronoclean.cli.doctor_cmd.is_ffprobe_available", return_value=False):
            with patch("chronoclean.cli.doctor_cmd.find_ffprobe_path", return_value=None):
                result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        # Should show warning or not-found status
        assert "ffprobe" in result.stdout.lower()
    
    def test_doctor_hachoir_not_available(self):
        """doctor handles missing hachoir gracefully."""
        with patch("chronoclean.cli.doctor_cmd.is_hachoir_available", return_value=False):
            result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        assert "hachoir" in result.stdout.lower()
    
    def test_doctor_all_dependencies_available(self):
        """doctor shows success when all dependencies found."""
        with patch("chronoclean.cli.doctor_cmd.is_ffprobe_available", return_value=True):
            with patch("chronoclean.cli.doctor_cmd.is_hachoir_available", return_value=True):
                with patch("chronoclean.cli.doctor_cmd.get_ffprobe_version", return_value="ffprobe version 5.0"):
                    with patch("chronoclean.cli.doctor_cmd.get_hachoir_version", return_value="3.0"):
                        result = runner.invoke(app, ["doctor"])
        
        assert result.exit_code == 0
        # Should show found/success indicators
        assert "✓" in result.stdout or "found" in result.stdout.lower()


class TestDoctorFixMode:
    """Tests for doctor --fix mode."""
    
    def test_doctor_fix_flag_accepted(self):
        """doctor accepts --fix flag."""
        # Use input to simulate user declining any fixes
        result = runner.invoke(app, ["doctor", "--fix"], input="n\n" * 10)
        
        # Should run without error (exit code depends on issues found)
        assert result.exit_code in [0, 1]
    
    def test_doctor_fix_shows_issues(self):
        """doctor --fix shows issues that can be fixed."""
        with patch("chronoclean.cli.doctor_cmd.is_ffprobe_available", return_value=False):
            with patch("chronoclean.cli.doctor_cmd.find_ffprobe_path", return_value="/usr/bin/ffprobe"):
                result = runner.invoke(app, ["doctor", "--fix"], input="n\n")
        
        # Should show the issue and offer to fix
        assert result.exit_code in [0, 1]
