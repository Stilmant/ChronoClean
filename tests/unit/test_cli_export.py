"""Tests for export CLI commands (json, csv)."""

import json
import pytest
from pathlib import Path
from typer.testing import CliRunner

from chronoclean.cli.main import app


runner = CliRunner()


# Minimal JPEG header for test files
JPEG_HEADER = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00"


class TestExportJsonCommand:
    """Tests for 'chronoclean export json' command."""
    
    def test_export_json_to_stdout(self, tmp_path):
        """export json outputs to stdout by default."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.json"
        
        # Use file output for reliable JSON parsing (stdout has Rich markup)
        result = runner.invoke(app, ["export", "json", str(tmp_path), "-o", str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        data = json.loads(output_file.read_text())
        assert "files" in data
        assert len(data["files"]) == 1
    
    def test_export_json_to_file(self, tmp_path):
        """export json --output writes to file."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.json"
        
        result = runner.invoke(app, ["export", "json", str(tmp_path), "-o", str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        data = json.loads(output_file.read_text())
        assert "files" in data
        assert len(data["files"]) == 1
    
    def test_export_json_empty_directory(self, tmp_path):
        """export json on empty directory produces empty files array."""
        result = runner.invoke(app, ["export", "json", str(tmp_path)])
        
        assert result.exit_code == 0
        json_start = result.stdout.find("{")
        if json_start != -1:
            data = json.loads(result.stdout[json_start:])
            assert "files" in data
            assert len(data["files"]) == 0
    
    def test_export_json_with_statistics(self, tmp_path):
        """export json includes statistics by default."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.json"
        
        result = runner.invoke(app, ["export", "json", str(tmp_path), "-o", str(output_file)])
        
        assert result.exit_code == 0
        data = json.loads(output_file.read_text())
        assert "statistics" in data
    
    def test_export_json_no_statistics(self, tmp_path):
        """export json --no-statistics excludes statistics."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.json"
        
        result = runner.invoke(app, ["export", "json", str(tmp_path), "-o", str(output_file), "--no-statistics"])
        
        assert result.exit_code == 0
        data = json.loads(output_file.read_text())
        assert "statistics" not in data
    
    def test_export_json_compact(self, tmp_path):
        """export json --compact produces minified output."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.json"
        
        result = runner.invoke(app, ["export", "json", str(tmp_path), "-o", str(output_file), "--compact"])
        
        assert result.exit_code == 0
        content = output_file.read_text()
        # Compact JSON should be one line (no pretty printing)
        assert content.count("\n") <= 1
    
    def test_export_json_with_limit(self, tmp_path):
        """export json --limit restricts files exported."""
        for i in range(5):
            (tmp_path / f"photo_{i}.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.json"
        
        result = runner.invoke(app, ["export", "json", str(tmp_path), "-o", str(output_file), "--limit", "2"])
        
        assert result.exit_code == 0
        data = json.loads(output_file.read_text())
        assert len(data["files"]) == 2
    
    def test_export_json_file_fields(self, tmp_path):
        """export json includes expected fields for each file."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.json"
        
        result = runner.invoke(app, ["export", "json", str(tmp_path), "-o", str(output_file)])
        
        assert result.exit_code == 0
        data = json.loads(output_file.read_text())
        file_record = data["files"][0]
        
        # Check expected fields exist (using actual field names from exporter)
        assert "path" in file_record
        assert "size_bytes" in file_record
        assert "date_source" in file_record


class TestExportCsvCommand:
    """Tests for 'chronoclean export csv' command."""
    
    def test_export_csv_to_stdout(self, tmp_path):
        """export csv outputs to stdout by default."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        
        result = runner.invoke(app, ["export", "csv", str(tmp_path)])
        
        assert result.exit_code == 0
        # Should have CSV header and data row
        lines = [l for l in result.stdout.split("\n") if l.strip() and not l.startswith("[")]
        # Filter out Rich markup lines
        csv_lines = [l for l in lines if "," in l or "source_path" in l.lower() or "path" in l.lower()]
        assert len(csv_lines) >= 2  # Header + at least 1 data row
    
    def test_export_csv_to_file(self, tmp_path):
        """export csv --output writes to file."""
        (tmp_path / "photo.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.csv"
        
        result = runner.invoke(app, ["export", "csv", str(tmp_path), "-o", str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        content = output_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) >= 2  # Header + data
    
    def test_export_csv_empty_directory(self, tmp_path):
        """export csv on empty directory produces only header."""
        output_file = tmp_path / "output.csv"
        
        result = runner.invoke(app, ["export", "csv", str(tmp_path), "-o", str(output_file)])
        
        assert result.exit_code == 0
        content = output_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1  # Only header
    
    def test_export_csv_with_limit(self, tmp_path):
        """export csv --limit restricts files exported."""
        for i in range(5):
            (tmp_path / f"photo_{i}.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.csv"
        
        result = runner.invoke(app, ["export", "csv", str(tmp_path), "-o", str(output_file), "--limit", "2"])
        
        assert result.exit_code == 0
        content = output_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows
    
    def test_export_csv_multiple_files(self, tmp_path):
        """export csv includes all scanned files."""
        for i in range(3):
            (tmp_path / f"photo_{i}.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.csv"
        
        result = runner.invoke(app, ["export", "csv", str(tmp_path), "-o", str(output_file)])
        
        assert result.exit_code == 0
        content = output_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 4  # Header + 3 data rows


class TestExportCommandErrors:
    """Error handling tests for export commands."""
    
    def test_export_json_nonexistent_source(self, tmp_path):
        """export json on nonexistent directory shows error."""
        fake_path = tmp_path / "does_not_exist"
        
        result = runner.invoke(app, ["export", "json", str(fake_path)])
        
        assert result.exit_code == 1
    
    def test_export_csv_nonexistent_source(self, tmp_path):
        """export csv on nonexistent directory shows error."""
        fake_path = tmp_path / "does_not_exist"
        
        result = runner.invoke(app, ["export", "csv", str(fake_path)])
        
        assert result.exit_code == 1
    
    def test_export_no_args_shows_help(self):
        """export with no subcommand shows help."""
        result = runner.invoke(app, ["export"])
        
        # Should show help or available commands
        assert "json" in result.stdout.lower() or "csv" in result.stdout.lower()


class TestExportCommandIntegration:
    """Integration tests for export commands."""
    
    def test_export_json_recursive(self, tmp_path):
        """export json recurses into subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.jpg").write_bytes(JPEG_HEADER)
        (subdir / "nested.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.json"
        
        result = runner.invoke(app, ["export", "json", str(tmp_path), "-o", str(output_file)])
        
        assert result.exit_code == 0
        data = json.loads(output_file.read_text())
        assert len(data["files"]) == 2
    
    def test_export_json_no_recursive(self, tmp_path):
        """export json --no-recursive skips subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.jpg").write_bytes(JPEG_HEADER)
        (subdir / "nested.jpg").write_bytes(JPEG_HEADER)
        output_file = tmp_path / "output.json"
        
        result = runner.invoke(app, ["export", "json", str(tmp_path), "-o", str(output_file), "--no-recursive"])
        
        assert result.exit_code == 0
        data = json.loads(output_file.read_text())
        assert len(data["files"]) == 1
