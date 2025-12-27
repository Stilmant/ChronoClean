"""Date inference engine for ChronoClean."""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from chronoclean.core.exif_reader import ExifReader
from chronoclean.core.models import DateSource

logger = logging.getLogger(__name__)


# Regex patterns for extracting dates from folder names
FOLDER_DATE_PATTERNS = [
    # Full date patterns
    (re.compile(r"^(\d{4})-(\d{2})-(\d{2})"), "ymd"),           # 2024-03-15
    (re.compile(r"^(\d{4})_(\d{2})_(\d{2})"), "ymd"),           # 2024_03_15
    (re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})"), "ymd"),         # 2024.03.15
    (re.compile(r"^(\d{4})(\d{2})(\d{2})(?!\d)"), "ymd"),       # 20240315

    # Year-month patterns
    (re.compile(r"^(\d{4})-(\d{2})(?!\d)"), "ym"),              # 2024-03
    (re.compile(r"^(\d{4})_(\d{2})(?!\d)"), "ym"),              # 2024_03
    (re.compile(r"^(\d{4})\.(\d{2})(?!\d)"), "ym"),             # 2024.03

    # Date anywhere in string
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), "ymd"),            # ...2024-03-15...
    (re.compile(r"(\d{4})_(\d{2})_(\d{2})"), "ymd"),            # ...2024_03_15...

    # Year-month anywhere
    (re.compile(r"(\d{4})-(\d{2})(?!\d)"), "ym"),               # ...2024-03...

    # Just year (with word boundary)
    (re.compile(r"(?:^|\D)(\d{4})(?:\D|$)"), "y"),              # ...2024...
]


class DateInferenceEngine:
    """Infers dates from multiple sources with configurable priority."""

    def __init__(
        self,
        priority: Optional[list[str]] = None,
        exif_reader: Optional[ExifReader] = None,
    ):
        """
        Initialize the date inference engine.

        Args:
            priority: Ordered list of sources to try.
                      Default: ["exif", "filesystem", "folder_name"]
            exif_reader: ExifReader instance (optional, created if not provided)
        """
        self.priority = priority or ["exif", "filesystem", "folder_name"]
        self.exif_reader = exif_reader or ExifReader()

        # Map source names to methods
        self._source_methods = {
            "exif": self._get_exif_date,
            "filesystem": self._get_filesystem_date,
            "folder_name": self._get_folder_date,
        }

    def infer_date(self, file_path: Path) -> tuple[Optional[datetime], DateSource]:
        """
        Infer the date for a file using configured priority.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (datetime or None, DateSource indicating origin)
        """
        for source_name in self.priority:
            method = self._source_methods.get(source_name)
            if not method:
                logger.warning(f"Unknown date source: {source_name}")
                continue

            result = method(file_path)
            if result:
                date, date_source = result
                if date:
                    logger.debug(f"Date for {file_path.name}: {date} (from {source_name})")
                    return date, date_source

        logger.debug(f"No date found for {file_path.name}")
        return None, DateSource.UNKNOWN

    def _get_exif_date(self, file_path: Path) -> Optional[tuple[datetime, DateSource]]:
        """Extract date from EXIF metadata."""
        date = self.exif_reader.get_date(file_path)
        if date:
            return date, DateSource.EXIF
        return None

    def _get_filesystem_date(self, file_path: Path) -> Optional[tuple[datetime, DateSource]]:
        """
        Get date from filesystem.

        Prefers creation date (birth time), falls back to modification date.
        """
        try:
            stat = file_path.stat()

            # Try to get creation time (not available on all platforms)
            ctime = None
            if hasattr(stat, "st_birthtime"):
                # macOS
                ctime = datetime.fromtimestamp(stat.st_birthtime)
            elif os.name == "nt":
                # Windows: st_ctime is creation time
                ctime = datetime.fromtimestamp(stat.st_ctime)

            if ctime:
                return ctime, DateSource.FILESYSTEM_CREATED

            # Fall back to modification time
            mtime = datetime.fromtimestamp(stat.st_mtime)
            return mtime, DateSource.FILESYSTEM_MODIFIED

        except OSError as e:
            logger.warning(f"Cannot get filesystem date for {file_path}: {e}")
            return None

    def _get_folder_date(self, file_path: Path) -> Optional[tuple[datetime, DateSource]]:
        """
        Try to parse date from parent folder name.

        Walks up the directory tree looking for date patterns.
        """
        # Check parent folders (up to 3 levels)
        current = file_path.parent
        for _ in range(3):
            if not current or current == current.parent:
                break

            folder_name = current.name
            date = self._parse_folder_date(folder_name)
            if date:
                return date, DateSource.FOLDER_NAME

            current = current.parent

        return None

    def _parse_folder_date(self, folder_name: str) -> Optional[datetime]:
        """
        Parse a date from a folder name.

        Args:
            folder_name: Name of the folder

        Returns:
            datetime object or None
        """
        if not folder_name:
            return None

        for pattern, date_type in FOLDER_DATE_PATTERNS:
            match = pattern.search(folder_name)
            if not match:
                continue

            try:
                groups = match.groups()

                if date_type == "ymd" and len(groups) >= 3:
                    year = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])
                    if self._is_valid_date(year, month, day):
                        return datetime(year, month, day)

                elif date_type == "ym" and len(groups) >= 2:
                    year = int(groups[0])
                    month = int(groups[1])
                    if self._is_valid_date(year, month, 1):
                        return datetime(year, month, 1)

                elif date_type == "y" and len(groups) >= 1:
                    year = int(groups[0])
                    if 1990 <= year <= 2100:  # Reasonable year range
                        return datetime(year, 1, 1)

            except (ValueError, IndexError):
                continue

        return None

    def _is_valid_date(self, year: int, month: int, day: int) -> bool:
        """Check if the date components form a valid date."""
        if not (1990 <= year <= 2100):
            return False
        if not (1 <= month <= 12):
            return False
        if not (1 <= day <= 31):
            return False

        # Check day validity for month
        days_in_month = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if day > days_in_month[month]:
            return False

        return True


def get_best_date(
    file_path: Path,
    priority: Optional[list[str]] = None,
) -> tuple[Optional[datetime], DateSource]:
    """
    Convenience function to get the best date for a file.

    Args:
        file_path: Path to the file
        priority: Optional custom priority list

    Returns:
        Tuple of (datetime or None, DateSource)
    """
    engine = DateInferenceEngine(priority=priority)
    return engine.infer_date(file_path)
