"""Dependency availability helpers for ChronoClean.

Provides generic functions to check if optional packages are installed
and retrieve their versions. Used by exif_reader and video_metadata modules.
"""

from typing import Optional


def is_package_available(package_name: str) -> bool:
    """Check if a Python package is importable.

    Args:
        package_name: Name of the package to check (e.g., 'hachoir', 'exiftool')

    Returns:
        True if the package can be imported
    """
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def get_package_version(package_name: str, default: Optional[str] = None) -> Optional[str]:
    """Get the version of an installed package.

    Args:
        package_name: Name of the package
        default: Value to return if version is unavailable (default: None)

    Returns:
        Version string, default value, or None if not installed
    """
    try:
        module = __import__(package_name)
        return getattr(module, "__version__", default or "unknown")
    except ImportError:
        return None


# Convenience wrappers for commonly used packages
def is_hachoir_available() -> bool:
    """Check if hachoir package is installed."""
    return is_package_available("hachoir")


def get_hachoir_version() -> Optional[str]:
    """Get hachoir package version."""
    return get_package_version("hachoir")


def is_exiftool_available() -> bool:
    """Check if exiftool (PyExifTool) package is available."""
    return is_package_available("exiftool")


def get_exifread_version() -> str:
    """Get exifread package version."""
    return get_package_version("exifread", default="unknown") or "not installed"
