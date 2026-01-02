"""Unit tests for TagRulesStore (v0.3.4)."""

import pytest
from pathlib import Path
from datetime import datetime, timezone

from chronoclean.core.tag_rules_store import TagRulesStore, TagRules
from chronoclean.config.schema import FolderTagsConfig


class TestTagRules:
    """Tests for TagRules dataclass."""
    
    def test_default_init(self):
        """Test default initialization."""
        rules = TagRules()
        assert rules.version == 1
        assert rules.use == []
        assert rules.ignore == []
        assert rules.aliases == {}
        assert rules.updated_at is not None
    
    def test_custom_init(self):
        """Test initialization with custom values."""
        rules = TagRules(
            version=2,
            use=["Paris 2022"],
            ignore=["tosort"],
            aliases={"Paris 2022": "ParisTrip"},
        )
        assert rules.version == 2
        assert "Paris 2022" in rules.use
        assert "tosort" in rules.ignore
        assert rules.aliases["Paris 2022"] == "ParisTrip"


class TestTagRulesStoreInit:
    """Tests for TagRulesStore initialization."""
    
    def test_default_path(self, tmp_path, monkeypatch):
        """Test default path is .chronoclean/tag_rules.yaml."""
        monkeypatch.chdir(tmp_path)
        store = TagRulesStore()
        assert store.rules_path == tmp_path / ".chronoclean" / "tag_rules.yaml"
    
    def test_custom_path(self, tmp_path):
        """Test custom path is used when provided."""
        custom_path = tmp_path / "custom" / "rules.yaml"
        store = TagRulesStore(rules_path=custom_path)
        assert store.rules_path == custom_path
    
    def test_load_empty_when_file_missing(self, tmp_path):
        """Test loading returns empty rules when file doesn't exist."""
        store = TagRulesStore(rules_path=tmp_path / "nonexistent.yaml")
        rules = store.load()
        assert rules.use == []
        assert rules.ignore == []
        assert rules.aliases == {}


class TestTagRulesStoreSaveLoad:
    """Tests for save/load roundtrip."""
    
    def test_save_creates_directory(self, tmp_path):
        """Test save creates parent directory if needed."""
        rules_path = tmp_path / "deep" / "nested" / "rules.yaml"
        store = TagRulesStore(rules_path=rules_path)
        
        store.add_use("Paris 2022")
        
        assert rules_path.exists()
        assert rules_path.parent.exists()
    
    def test_roundtrip_use_list(self, tmp_path):
        """Test use list survives save/load."""
        rules_path = tmp_path / "rules.yaml"
        store = TagRulesStore(rules_path=rules_path)
        
        store.add_use("Paris 2022")
        store.add_use("Wedding")
        
        # Reload from disk
        store2 = TagRulesStore(rules_path=rules_path)
        rules = store2.load()
        
        assert "Paris 2022" in rules.use
        assert "Wedding" in rules.use
    
    def test_roundtrip_ignore_list(self, tmp_path):
        """Test ignore list survives save/load."""
        rules_path = tmp_path / "rules.yaml"
        store = TagRulesStore(rules_path=rules_path)
        
        store.add_ignore("tosort")
        store.add_ignore("misc")
        
        # Reload from disk
        store2 = TagRulesStore(rules_path=rules_path)
        rules = store2.load()
        
        assert "tosort" in rules.ignore
        assert "misc" in rules.ignore
    
    def test_roundtrip_aliases(self, tmp_path):
        """Test aliases survive save/load."""
        rules_path = tmp_path / "rules.yaml"
        store = TagRulesStore(rules_path=rules_path)
        
        store.add_use("Paris 2022", alias="ParisTrip")
        store.add_use("Wedding John", alias="JohnWedding")
        
        # Reload from disk
        store2 = TagRulesStore(rules_path=rules_path)
        rules = store2.load()
        
        assert rules.aliases["Paris 2022"] == "ParisTrip"
        assert rules.aliases["Wedding John"] == "JohnWedding"


class TestTagRulesStoreAddUse:
    """Tests for add_use method."""
    
    def test_add_use_basic(self, tmp_path):
        """Test adding a folder to use list."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("Paris 2022")
        
        assert "Paris 2022" in store.rules.use
        assert "Paris 2022" not in store.rules.ignore
    
    def test_add_use_with_alias(self, tmp_path):
        """Test adding a folder with alias."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("Paris 2022", alias="ParisTrip")
        
        assert "Paris 2022" in store.rules.use
        assert store.rules.aliases["Paris 2022"] == "ParisTrip"
    
    def test_add_use_removes_from_ignore(self, tmp_path):
        """Test add_use removes folder from ignore list."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_ignore("Paris 2022")
        assert "Paris 2022" in store.rules.ignore
        
        store.add_use("Paris 2022")
        
        assert "Paris 2022" in store.rules.use
        assert "Paris 2022" not in store.rules.ignore
    
    def test_add_use_no_duplicate(self, tmp_path):
        """Test add_use doesn't create duplicates."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("Paris 2022")
        store.add_use("Paris 2022")
        
        assert store.rules.use.count("Paris 2022") == 1
    
    def test_add_use_clears_alias_when_none(self, tmp_path):
        """Test add_use clears alias when called without alias."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("Paris 2022", alias="ParisTrip")
        assert store.rules.aliases["Paris 2022"] == "ParisTrip"
        
        store.add_use("Paris 2022")  # No alias
        
        assert "Paris 2022" not in store.rules.aliases


class TestTagRulesStoreAddIgnore:
    """Tests for add_ignore method."""
    
    def test_add_ignore_basic(self, tmp_path):
        """Test adding a folder to ignore list."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_ignore("tosort")
        
        assert "tosort" in store.rules.ignore
        assert "tosort" not in store.rules.use
    
    def test_add_ignore_removes_from_use(self, tmp_path):
        """Test add_ignore removes folder from use list."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("tosort")
        assert "tosort" in store.rules.use
        
        store.add_ignore("tosort")
        
        assert "tosort" in store.rules.ignore
        assert "tosort" not in store.rules.use
    
    def test_add_ignore_removes_alias(self, tmp_path):
        """Test add_ignore removes any existing alias."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("folder", alias="FolderAlias")
        assert "folder" in store.rules.aliases
        
        store.add_ignore("folder")
        
        assert "folder" not in store.rules.aliases


class TestTagRulesStoreClear:
    """Tests for clear method."""
    
    def test_clear_from_use(self, tmp_path):
        """Test clear removes from use list."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("Paris 2022")
        
        store.clear("Paris 2022")
        
        assert "Paris 2022" not in store.rules.use
    
    def test_clear_from_ignore(self, tmp_path):
        """Test clear removes from ignore list."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_ignore("tosort")
        
        store.clear("tosort")
        
        assert "tosort" not in store.rules.ignore
    
    def test_clear_removes_alias(self, tmp_path):
        """Test clear removes alias."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("Paris 2022", alias="ParisTrip")
        
        store.clear("Paris 2022")
        
        assert "Paris 2022" not in store.rules.aliases
    
    def test_clear_nonexistent_is_safe(self, tmp_path):
        """Test clear on nonexistent folder doesn't raise."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.clear("nonexistent")  # Should not raise


class TestTagRulesStoreShouldUse:
    """Tests for should_use precedence logic."""
    
    def test_rules_use_takes_precedence(self, tmp_path):
        """Test tag rules use list has highest precedence."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        config = FolderTagsConfig(ignore_list=["Paris 2022"])
        
        store.add_use("Paris 2022")
        
        # Rules use overrides config ignore
        assert store.should_use("Paris 2022", config) is True
    
    def test_rules_ignore_takes_precedence(self, tmp_path):
        """Test tag rules ignore list has highest precedence."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        config = FolderTagsConfig(force_list=["tosort"])
        
        store.add_ignore("tosort")
        
        # Rules ignore overrides config force
        assert store.should_use("tosort", config) is False
    
    def test_config_force_used_when_no_rules(self, tmp_path):
        """Test config force_list is used when no rules defined."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        config = FolderTagsConfig(force_list=["Paris 2022"])
        
        assert store.should_use("Paris 2022", config) is True
    
    def test_config_ignore_used_when_no_rules(self, tmp_path):
        """Test config ignore_list is used when no rules defined."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        config = FolderTagsConfig(ignore_list=["tosort"])
        
        assert store.should_use("tosort", config) is False
    
    def test_returns_none_for_heuristics(self, tmp_path):
        """Test returns None when no rules or config match."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        config = FolderTagsConfig()
        
        assert store.should_use("unknown_folder", config) is None


class TestTagRulesStoreAliases:
    """Tests for alias methods."""
    
    def test_get_alias_returns_alias(self, tmp_path):
        """Test get_alias returns defined alias."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("Paris 2022", alias="ParisTrip")
        
        assert store.get_alias("Paris 2022") == "ParisTrip"
    
    def test_get_alias_returns_none_when_missing(self, tmp_path):
        """Test get_alias returns None for undefined alias."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        
        assert store.get_alias("Paris 2022") is None
    
    def test_apply_alias_uses_alias(self, tmp_path):
        """Test apply_alias returns alias when defined."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        store.add_use("Paris 2022", alias="ParisTrip")
        
        result = store.apply_alias("Paris 2022", "Paris_2022")
        assert result == "ParisTrip"
    
    def test_apply_alias_uses_default_when_no_alias(self, tmp_path):
        """Test apply_alias returns default when no alias."""
        store = TagRulesStore(rules_path=tmp_path / "rules.yaml")
        
        result = store.apply_alias("Paris 2022", "Paris_2022")
        assert result == "Paris_2022"
