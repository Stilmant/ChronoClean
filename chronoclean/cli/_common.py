"""Shared state and utilities for CLI commands.

This module centralizes common CLI dependencies to support
the modular command structure (scan_cmd, apply_cmd, etc.).
"""

from rich.console import Console

from chronoclean.config import ConfigLoader


# Initialize console (shared across all commands)
console = Console()

# Load config at module level to generate dynamic help text
# This allows --help to show actual defaults from config (or built-in if no config)
_default_cfg = ConfigLoader.load(None)
_has_config_file = any(p.exists() for p in ConfigLoader.DEFAULT_CONFIG_PATHS)
_cfg_note = " via config" if _has_config_file else ""


def bool_show_default(value: bool, true_word: str, false_word: str) -> str:
    """Generate show_default string for boolean flags.

    Args:
        value: The boolean value to display
        true_word: Word to show when value is True (e.g., "recursive")
        false_word: Word to show when value is False (e.g., "no-recursive")

    Returns:
        String like "recursive via config" or "no-recursive"
    """
    return f"{true_word if value else false_word}{_cfg_note}"


# Sentinel value for detecting if CLI option was explicitly set
# Use `is UNSET` to check if user provided a value vs using default
UNSET = None
