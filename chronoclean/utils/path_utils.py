"""Path utility functions for ChronoClean."""

import os
import re
from pathlib import Path
from typing import Optional


def normalize_path(path: Path) -> Path:
    """
    Normalize a path for consistent handling.

    Args:
        path: Path to normalize

    Returns:
        Normalized absolute path
    """
    return Path(path).resolve()


def is_hidden(path: Path) -> bool:
    """
    Check if a path is hidden.

    Args:
        path: Path to check

    Returns:
        True if the path or any parent is hidden
    """
    for part in path.parts:
        if part.startswith(".") and part not in (".", ".."):
            return True
    return False


def safe_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename for safe filesystem use.

    Args:
        filename: Original filename
        max_length: Maximum filename length

    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    # Windows forbidden: < > : " / \ | ? *
    # Also remove control characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    safe = re.sub(invalid_chars, "_", filename)

    # Remove leading/trailing spaces and dots
    safe = safe.strip(". ")

    # Ensure not empty
    if not safe:
        safe = "unnamed"

    # Truncate if needed (preserve extension)
    if len(safe) > max_length:
        stem = Path(safe).stem
        suffix = Path(safe).suffix
        max_stem = max_length - len(suffix)
        safe = stem[:max_stem] + suffix

    return safe


def get_unique_path(path: Path) -> Path:
    """
    Get a unique path by adding a counter if needed.

    Args:
        path: Desired path

    Returns:
        Unique path
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter:03d}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1
        if counter > 9999:
            raise ValueError(f"Cannot find unique path for {path}")


def relative_to_safe(path: Path, base: Path) -> Optional[Path]:
    """
    Safely get relative path, returning None if not relative.

    Args:
        path: Path to make relative
        base: Base path

    Returns:
        Relative path or None
    """
    try:
        return path.relative_to(base)
    except ValueError:
        return None


def get_common_prefix(paths: list[Path]) -> Optional[Path]:
    """
    Find the common prefix directory of a list of paths.

    Args:
        paths: List of paths

    Returns:
        Common prefix path or None
    """
    if not paths:
        return None

    # Convert to absolute paths
    abs_paths = [p.resolve() for p in paths]

    # Get parts
    parts_list = [p.parts for p in abs_paths]

    # Find common prefix
    common = []
    for parts in zip(*parts_list):
        if len(set(parts)) == 1:
            common.append(parts[0])
        else:
            break

    if not common:
        return None

    return Path(*common)


def format_size(size_bytes: int) -> str:
    """
    Format a byte size as human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string like "1.5 MB"
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
