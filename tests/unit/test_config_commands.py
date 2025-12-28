"""Tests for config CLI commands (init, show, path)."""

import os
import pytest
from pathlib import Path
from typer.testing import CliRunner
from chronoclean.cli.main import app


runner = CliRunner()


class TestConfigInit:
    """Tests for 'chronoclean config init' command."""
    
    def test_init_creates_minimal_config(self, tmp_path, monkeypatch):
        """config init creates minimal config by default."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["config", "init"])
        
        assert result.exit_code == 0
        assert "Created config file" in result.stdout
        
        config_file = tmp_path / "chronoclean.yaml"
        assert config_file.exists()
        
        content = config_file.read_text()
        assert "sorting:" in content
        # Minimal config should be reasonably short (includes v0.2 commented options)
        assert len(content.splitlines()) < 35
    
    def test_init_full_creates_complete_config(self, tmp_path, monkeypatch):
        """config init --full creates full config with all options."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["config", "init", "--full"])
        
        assert result.exit_code == 0
        assert "Full configuration" in result.stdout
        
        config_file = tmp_path / "chronoclean.yaml"
        content = config_file.read_text()
        
        # Full config should have all sections documented
        assert "sorting:" in content
        assert "folder_tags:" in content
        assert "renaming:" in content
        assert "scan:" in content  # Full template uses 'scan:' not 'scanning:'
        # Should have more lines than minimal
        assert len(content.splitlines()) > 50
    
    def test_init_custom_output_path(self, tmp_path, monkeypatch):
        """config init --output creates config at specified path."""
        monkeypatch.chdir(tmp_path)
        output_path = tmp_path / "custom" / "my-config.yaml"
        
        # Create parent directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = runner.invoke(app, ["config", "init", "-o", str(output_path)])
        
        assert result.exit_code == 0
        assert output_path.exists()
    
    def test_init_refuses_overwrite_without_force(self, tmp_path, monkeypatch):
        """config init won't overwrite existing file without --force."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "chronoclean.yaml"
        config_file.write_text("existing content")
        
        result = runner.invoke(app, ["config", "init"])
        
        assert result.exit_code == 1
        assert "already exists" in result.stdout
        assert config_file.read_text() == "existing content"
    
    def test_init_force_overwrites(self, tmp_path, monkeypatch):
        """config init --force overwrites existing file."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "chronoclean.yaml"
        config_file.write_text("old content")
        
        result = runner.invoke(app, ["config", "init", "--force"])
        
        assert result.exit_code == 0
        # Check for key elements of generated config
        content = config_file.read_text()
        assert "ChronoClean" in content
        assert "sorting:" in content
    
    def test_init_shows_next_steps(self, tmp_path, monkeypatch):
        """config init displays helpful next steps."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["config", "init"])
        
        assert "Next steps:" in result.stdout
        assert "chronoclean scan" in result.stdout


class TestConfigShow:
    """Tests for 'chronoclean config show' command."""
    
    def test_show_displays_defaults(self, tmp_path, monkeypatch):
        """config show displays defaults when no config file exists."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["config", "show"])
        
        assert result.exit_code == 0
        assert "ChronoClean Configuration" in result.stdout
        assert "built-in defaults" in result.stdout
        # Should show some config values
        assert "sorting:" in result.stdout
    
    def test_show_loads_config_file(self, tmp_path, monkeypatch):
        """config show loads and displays config from file."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "chronoclean.yaml"
        config_file.write_text("""
version: "0.1"
sorting:
  folder_structure: "YYYY"
""")
        
        result = runner.invoke(app, ["config", "show"])
        
        assert result.exit_code == 0
        # Check that config source is shown
        assert "chronoclean.yaml" in result.stdout
    
    def test_show_specific_section(self, tmp_path, monkeypatch):
        """config show --section displays only that section."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["config", "show", "--section", "sorting"])
        
        assert result.exit_code == 0
        assert "sorting:" in result.stdout
    
    def test_show_unknown_section_error(self, tmp_path, monkeypatch):
        """config show --section with unknown section shows error."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["config", "show", "--section", "nonexistent"])
        
        assert result.exit_code == 1
        assert "Unknown section" in result.stdout
    
    def test_show_explicit_config_path(self, tmp_path, monkeypatch):
        """config show --config loads specified file."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "custom.yaml"
        config_file.write_text("""
version: "0.1"
sorting:
  folder_structure: "YYYY/MM/DD"
""")
        
        result = runner.invoke(app, ["config", "show", "-c", str(config_file)])
        
        assert result.exit_code == 0
        # Should show the custom file as source
        assert "custom.yaml" in result.stdout


class TestConfigPath:
    """Tests for 'chronoclean config path' command."""
    
    def test_path_shows_search_paths(self, tmp_path, monkeypatch):
        """config path displays all search paths."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["config", "path"])
        
        assert result.exit_code == 0
        assert "Config file search paths" in result.stdout
        assert "chronoclean.yaml" in result.stdout
    
    def test_path_marks_active_config(self, tmp_path, monkeypatch):
        """config path marks the active config file."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "chronoclean.yaml"
        config_file.write_text("version: '0.1'")
        
        result = runner.invoke(app, ["config", "path"])
        
        assert result.exit_code == 0
        assert "ACTIVE" in result.stdout
    
    def test_path_shows_hint_when_no_config(self, tmp_path, monkeypatch):
        """config path shows init hint when no config found."""
        monkeypatch.chdir(tmp_path)
        
        result = runner.invoke(app, ["config", "path"])
        
        assert result.exit_code == 0
        assert "config init" in result.stdout


class TestConfigTemplates:
    """Tests for config template content."""
    
    def test_minimal_template_valid_yaml(self, tmp_path, monkeypatch):
        """Minimal config template is valid YAML that loads correctly."""
        import yaml
        from chronoclean.config.templates import get_config_template
        
        template = get_config_template(full=False)
        config = yaml.safe_load(template)
        
        assert config is not None
        # Minimal template has sorting section
        assert "sorting" in config
    
    def test_full_template_valid_yaml(self, tmp_path, monkeypatch):
        """Full config template is valid YAML that loads correctly."""
        import yaml
        from chronoclean.config.templates import get_config_template
        
        template = get_config_template(full=True)
        config = yaml.safe_load(template)
        
        assert config is not None
        assert "version" in config
        assert "sorting" in config
        assert "folder_tags" in config
    
    def test_full_template_has_comments(self):
        """Full config template includes helpful comments."""
        from chronoclean.config.templates import get_config_template
        
        template = get_config_template(full=True)
        
        assert "#" in template  # Has comments
        assert "format" in template.lower()  # Describes formats
