"""
Tag Rules Store - Persistent folder tag decisions and aliases.

Stores user decisions about folder name classification (use/ignore/clear)
and optional aliases (folder name -> custom tag text).

File location: .chronoclean/tag_rules.yaml
Precedence: tag_rules.yaml > config force/ignore lists > FolderTagger heuristics
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from chronoclean.config.schema import FolderTagsConfig


@dataclass
class TagRules:
    """Tag classification rules and aliases."""
    
    version: int = 1
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    use: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)


class TagRulesStore:
    """
    Manages persistent tag rules and aliases.
    
    Provides precedence-aware tag classification:
    1. Tag rules file (use/ignore/aliases)
    2. Config force_list/ignore_list
    3. FolderTagger heuristics
    """
    
    DEFAULT_FILENAME = "tag_rules.yaml"
    DEFAULT_DIR = ".chronoclean"
    
    def __init__(self, rules_path: Optional[Path] = None):
        """
        Initialize tag rules store.
        
        Args:
            rules_path: Optional explicit path to tag_rules.yaml.
                       If None, uses .chronoclean/tag_rules.yaml relative to CWD.
        """
        if rules_path is None:
            rules_path = Path.cwd() / self.DEFAULT_DIR / self.DEFAULT_FILENAME
        
        self.rules_path = rules_path
        self._rules: Optional[TagRules] = None
    
    @property
    def rules(self) -> TagRules:
        """Get current rules, loading from disk if not cached."""
        if self._rules is None:
            self._rules = self.load()
        return self._rules
    
    def load(self) -> TagRules:
        """
        Load tag rules from disk.
        
        Returns:
            TagRules object (empty if file doesn't exist)
        """
        if not self.rules_path.exists():
            return TagRules()
        
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            return TagRules(
                version=data.get("version", 1),
                updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
                use=data.get("use", []),
                ignore=data.get("ignore", []),
                aliases=data.get("aliases", {}),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load tag rules from {self.rules_path}: {e}") from e
    
    def save(self, rules: Optional[TagRules] = None) -> None:
        """
        Save tag rules to disk.
        
        Args:
            rules: Rules to save. If None, uses current cached rules.
        """
        if rules is None:
            rules = self.rules
        
        # Update timestamp
        rules.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Ensure directory exists
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare data for YAML
        data = {
            "version": rules.version,
            "updated_at": rules.updated_at,
            "use": sorted(rules.use),  # Sort for cleaner diffs
            "ignore": sorted(rules.ignore),
            "aliases": dict(sorted(rules.aliases.items())),
        }
        
        try:
            with open(self.rules_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            # Update cache
            self._rules = rules
        except Exception as e:
            raise RuntimeError(f"Failed to save tag rules to {self.rules_path}: {e}") from e
    
    def add_use(self, folder_name: str, alias: Optional[str] = None) -> None:
        """
        Mark a folder name as "use" (force tagging).
        
        Args:
            folder_name: Folder name to force-use
            alias: Optional custom tag text (if None, uses folder name)
        """
        rules = self.rules
        
        # Remove from ignore if present
        if folder_name in rules.ignore:
            rules.ignore.remove(folder_name)
        
        # Add to use list
        if folder_name not in rules.use:
            rules.use.append(folder_name)
        
        # Set alias if provided
        if alias:
            rules.aliases[folder_name] = alias
        elif folder_name in rules.aliases:
            # Clear alias if not provided
            del rules.aliases[folder_name]
        
        self.save(rules)
    
    def add_ignore(self, folder_name: str) -> None:
        """
        Mark a folder name as "ignore" (skip tagging).
        
        Args:
            folder_name: Folder name to ignore
        """
        rules = self.rules
        
        # Remove from use if present
        if folder_name in rules.use:
            rules.use.remove(folder_name)
        
        # Remove alias if present
        if folder_name in rules.aliases:
            del rules.aliases[folder_name]
        
        # Add to ignore list
        if folder_name not in rules.ignore:
            rules.ignore.append(folder_name)
        
        self.save(rules)
    
    def clear(self, folder_name: str) -> None:
        """
        Clear any decision for a folder name (returns to heuristics).
        
        Args:
            folder_name: Folder name to clear
        """
        rules = self.rules
        
        # Remove from both lists
        if folder_name in rules.use:
            rules.use.remove(folder_name)
        if folder_name in rules.ignore:
            rules.ignore.remove(folder_name)
        
        # Remove alias if present
        if folder_name in rules.aliases:
            del rules.aliases[folder_name]
        
        self.save(rules)
    
    def should_use(self, folder_name: str, config: FolderTagsConfig) -> Optional[bool]:
        """
        Check if a folder name should be used for tagging (precedence-aware).
        
        Returns:
            True: Force use (from rules or config)
            False: Force ignore (from rules or config)
            None: No override (use FolderTagger heuristics)
        
        Precedence:
            1. Tag rules file (use/ignore)
            2. Config force_list/ignore_list
            3. None (defer to heuristics)
        """
        rules = self.rules
        
        # Priority 1: Tag rules file
        if folder_name in rules.use:
            return True
        if folder_name in rules.ignore:
            return False
        
        # Priority 2: Config lists
        if folder_name in config.force_list:
            return True
        if folder_name in config.ignore_list:
            return False
        
        # Priority 3: Defer to heuristics
        return None
    
    def get_alias(self, folder_name: str) -> Optional[str]:
        """
        Get custom tag alias for a folder name.
        
        Args:
            folder_name: Folder name to look up
        
        Returns:
            Custom tag text, or None if no alias defined
        """
        return self.rules.aliases.get(folder_name)
    
    def apply_alias(self, folder_name: str, default_tag: str) -> str:
        """
        Apply alias if defined, otherwise return default tag.
        
        Args:
            folder_name: Original folder name
            default_tag: Tag text from FolderTagger.format_tag()
        
        Returns:
            Alias if defined, otherwise default_tag
        """
        alias = self.get_alias(folder_name)
        return alias if alias else default_tag
