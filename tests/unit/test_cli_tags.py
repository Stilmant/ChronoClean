"""Unit tests for tags CLI commands (v0.3.4)."""

import json
import pytest
from pathlib import Path
from typer.testing import CliRunner

from chronoclean.cli.main import app
from chronoclean.core.tag_rules_store import TagRulesStore


runner = CliRunner()


class TestTagsClassifyCommand:
    """Tests for `chronoclean tags classify` command."""
    
    def test_classify_use_basic(self, tmp_path, monkeypatch):
        """Test classifying a folder as 'use'."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["tags", "classify", "Paris 2022", "use"])
        
        assert result.exit_code == 0
        assert "Marked 'Paris 2022' as usable" in result.output
        
        # Verify persistence
        store = TagRulesStore()
        assert "Paris 2022" in store.rules.use
    
    def test_classify_use_with_alias(self, tmp_path, monkeypatch):
        """Test classifying a folder with alias."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, [
            "tags", "classify", "Paris 2022", "use", 
            "--tag", "ParisTrip"
        ])
        
        assert result.exit_code == 0
        assert "alias 'ParisTrip'" in result.output
        
        store = TagRulesStore()
        assert store.rules.aliases["Paris 2022"] == "ParisTrip"
    
    def test_classify_ignore(self, tmp_path, monkeypatch):
        """Test classifying a folder as 'ignore'."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["tags", "classify", "tosort", "ignore"])
        
        assert result.exit_code == 0
        assert "Marked 'tosort' as ignored" in result.output
        
        store = TagRulesStore()
        assert "tosort" in store.rules.ignore
    
    def test_classify_clear(self, tmp_path, monkeypatch):
        """Test clearing classification."""
        monkeypatch.chdir(tmp_path)
        
        # First add to use list
        runner.invoke(app, ["tags", "classify", "Paris 2022", "use"])
        
        # Then clear
        result = runner.invoke(app, ["tags", "classify", "Paris 2022", "clear"])
        
        assert result.exit_code == 0
        assert "Cleared classification" in result.output
        
        store = TagRulesStore()
        assert "Paris 2022" not in store.rules.use
    
    def test_classify_invalid_action(self, tmp_path, monkeypatch):
        """Test invalid action is rejected."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["tags", "classify", "Paris 2022", "invalid"])
        
        assert result.exit_code == 1
        assert "Invalid action" in result.output
    
    def test_classify_tag_option_only_with_use(self, tmp_path, monkeypatch):
        """Test --tag option is rejected with non-use actions."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, [
            "tags", "classify", "tosort", "ignore",
            "--tag", "SomeTag"
        ])
        
        assert result.exit_code == 1
        assert "--tag option is only valid" in result.output


class TestTagsListCommand:
    """Tests for `chronoclean tags list` command."""
    
    @pytest.fixture
    def source_with_folders(self, tmp_path):
        """Create a source directory with some folders and files."""
        # Create meaningful folder
        meaningful = tmp_path / "source" / "Paris 2022"
        meaningful.mkdir(parents=True)
        
        # Create a minimal JPEG in meaningful folder
        img = meaningful / "IMG_001.jpg"
        img.write_bytes(
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9LDJ2444'
            b'\xff\xd9'
        )
        
        # Create ignored folder (too short)
        ignored = tmp_path / "source" / "ab"
        ignored.mkdir(parents=True)
        img2 = ignored / "IMG_002.jpg"
        img2.write_bytes(
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9LDJ2444'
            b'\xff\xd9'
        )
        
        return tmp_path / "source"
    
    def test_list_text_output(self, source_with_folders):
        """Test tags list with text output."""
        result = runner.invoke(app, [
            "tags", "list", str(source_with_folders),
            "--no-videos"
        ])
        
        assert result.exit_code == 0
        # Should show meaningful folders in "Will Tag" section
        assert "Will Tag" in result.output or "No tags detected" in result.output
    
    def test_list_json_output(self, source_with_folders):
        """Test tags list with JSON output."""
        result = runner.invoke(app, [
            "tags", "list", str(source_with_folders),
            "--format", "json",
            "--no-videos"
        ])
        
        assert result.exit_code == 0
        
        # Extract JSON from output (may contain logging prefixes)
        output = result.output
        # Find JSON start (either { or [)
        json_start = output.find("{")
        if json_start == -1:
            json_start = output.find("[")
        assert json_start != -1, f"No JSON found in output: {output}"
        
        json_str = output[json_start:]
        data = json.loads(json_str)
        assert "tag_candidates" in data
        assert "ignored_folders" in data
    
    def test_list_json_to_file(self, source_with_folders, tmp_path):
        """Test tags list JSON output to file."""
        output_file = tmp_path / "tags.json"
        
        result = runner.invoke(app, [
            "tags", "list", str(source_with_folders),
            "--format", "json",
            "--output", str(output_file),
            "--no-videos"
        ])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        data = json.loads(output_file.read_text())
        assert "tag_candidates" in data
    
    def test_list_no_show_ignored(self, source_with_folders):
        """Test --no-show-ignored hides ignored folders."""
        result = runner.invoke(app, [
            "tags", "list", str(source_with_folders),
            "--format", "json",
            "--no-show-ignored",
            "--no-videos"
        ])
        
        assert result.exit_code == 0
        
        # Extract JSON from output (may contain logging prefixes)
        output = result.output
        json_start = output.find("{")
        if json_start == -1:
            json_start = output.find("[")
        assert json_start != -1
        
        json_str = output[json_start:]
        data = json.loads(json_str)
        assert data["ignored_folders"] == []


class TestTagsHelpMessages:
    """Tests for tags command help messages."""
    
    def test_tags_help(self):
        """Test tags --help shows available commands."""
        result = runner.invoke(app, ["tags", "--help"])
        
        assert result.exit_code == 0
        assert "list" in result.output
        assert "classify" in result.output
    
    def test_tags_list_help(self):
        """Test tags list --help shows options."""
        result = runner.invoke(app, ["tags", "list", "--help"])
        
        assert result.exit_code == 0
        assert "--recursive" in result.output
        assert "--format" in result.output
        assert "--samples" in result.output
    
    def test_tags_classify_help(self):
        """Test tags classify --help shows options."""
        result = runner.invoke(app, ["tags", "classify", "--help"])
        
        assert result.exit_code == 0
        assert "--tag" in result.output
        assert "use" in result.output.lower()
        assert "ignore" in result.output.lower()
        assert "clear" in result.output.lower()
