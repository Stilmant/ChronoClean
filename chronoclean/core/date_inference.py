"""Date inference engine for ChronoClean."""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from chronoclean.core.exif_reader import ExifReader
from chronoclean.core.models import DateSource, FileType
from chronoclean.core.video_metadata import VideoMetadataReader

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


# v0.2: Regex patterns for extracting dates from filenames
FILENAME_DATE_PATTERNS = [
    # YYYYMMDD_HHMMSS (Screenshot, camera)
    (re.compile(r"(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})"), "ymdhms"),
    # Screenshot_YYYYMMDD-HHMMSS (Android screenshots)
    (re.compile(r"Screenshot[_-](\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})"), "ymdhms"),
    # IMG-YYYYMMDD-WA (WhatsApp)
    (re.compile(r"IMG-(\d{4})(\d{2})(\d{2})-WA\d+", re.IGNORECASE), "ymd"),
    # VID-YYYYMMDD-WA (WhatsApp video)
    (re.compile(r"VID-(\d{4})(\d{2})(\d{2})-WA\d+", re.IGNORECASE), "ymd"),
    # IMG_YYYYMMDD (standard camera format with 8 digits)
    (re.compile(r"IMG[_-](\d{4})(\d{2})(\d{2})(?!\d)", re.IGNORECASE), "ymd"),
    # YYYYMMDD anywhere (8-digit date)
    (re.compile(r"(?:^|[^0-9])(\d{4})(\d{2})(\d{2})(?!\d)"), "ymd"),
    # YYYY-MM-DD anywhere
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), "ymd"),
    # YYYY_MM_DD anywhere
    (re.compile(r"(\d{4})_(\d{2})_(\d{2})"), "ymd"),
    # IMG_YYMMDD (2-digit year format, e.g., IMG_090831)
    (re.compile(r"IMG[_-](\d{2})(\d{2})(\d{2})(?!\d)", re.IGNORECASE), "yymmdd"),
    # YYMMDD at start of filename
    (re.compile(r"^(\d{2})(\d{2})(\d{2})(?!\d)"), "yymmdd"),
]


class DateInferenceEngine:
    """Infers dates from multiple sources with configurable priority."""

    def __init__(
        self,
        priority: Optional[list[str]] = None,
        exif_reader: Optional[ExifReader] = None,
        video_reader: Optional["VideoMetadataReader"] = None,
        year_cutoff: int = 30,
        filename_date_enabled: bool = True,
        video_metadata_enabled: bool = True,
    ):
        """
        Initialize the date inference engine.

        Args:
            priority: Ordered list of sources to try.
                      Default: ["exif", "video_metadata", "filename", "filesystem", "folder_name"]
            exif_reader: ExifReader instance (optional, created if not provided)
            video_reader: VideoMetadataReader instance (optional, created with defaults if not provided
                          and video_metadata_enabled is True)
            year_cutoff: For 2-digit years: 00-cutoff = 2000s, cutoff-99 = 1900s
            filename_date_enabled: Whether to extract dates from filenames
            video_metadata_enabled: Whether video metadata extraction is enabled
        """
        self.priority = priority or ["exif", "video_metadata", "filename", "filesystem", "folder_name"]
        self.exif_reader = exif_reader or ExifReader()
        self.video_metadata_enabled = video_metadata_enabled
        
        # Create default video reader if enabled and not provided
        if video_reader is not None:
            self.video_reader = video_reader
        elif video_metadata_enabled:
            self.video_reader = VideoMetadataReader()
        else:
            self.video_reader = None
            
        self.year_cutoff = year_cutoff
        self.filename_date_enabled = filename_date_enabled

        # Map source names to methods
        self._source_methods = {
            "exif": self._get_exif_date,
            "video_metadata": self._get_video_metadata_date,
            "filesystem": self._get_filesystem_date,
            "folder_name": self._get_folder_date,
            "filename": self._get_filename_date,
        }

    def infer_date(
        self,
        file_path: Path,
        file_type: Optional[FileType] = None,
    ) -> tuple[Optional[datetime], DateSource]:
        """
        Infer the date for a file using configured priority.

        Args:
            file_path: Path to the file
            file_type: Optional file type hint (IMAGE, VIDEO, RAW).
                       If provided, skips inapplicable sources.
                       If None, video_metadata is skipped for safety.

        Returns:
            Tuple of (datetime or None, DateSource indicating origin)
        """
        for source_name in self.priority:
            # Skip EXIF for videos
            if file_type == FileType.VIDEO and source_name == "exif":
                continue
            
            # Skip video_metadata for non-videos or when disabled
            if source_name == "video_metadata":
                # Skip if video metadata is disabled
                if not self.video_metadata_enabled or self.video_reader is None:
                    continue
                # Skip for images/raw files
                if file_type in (FileType.IMAGE, FileType.RAW):
                    continue
                # Skip if file_type not specified (safety: don't run ffprobe on unknown files)
                if file_type is None:
                    continue
            
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

    def get_filename_date(self, file_path: Path) -> Optional[datetime]:
        """
        Extract date from filename only.

        Used for date mismatch detection (comparing filename date vs EXIF date).
        This is a public method that wraps _get_filename_date.

        Args:
            file_path: Path to the file

        Returns:
            datetime or None (also returns None if filename_date_enabled=False)
        """
        if not self.filename_date_enabled:
            return None
        result = self._get_filename_date(file_path)
        if result:
            return result[0]
        return None

    def get_video_metadata_date(self, file_path: Path) -> Optional[datetime]:
        """
        Extract date from video metadata only.

        Used for populating video_metadata_date field in FileRecord.

        Args:
            file_path: Path to the video file

        Returns:
            datetime or None (also returns None if video_reader is disabled)
        """
        if self.video_reader is None:
            return None
        result = self._get_video_metadata_date(file_path)
        if result:
            return result[0]
        return None

    def _get_exif_date(self, file_path: Path) -> Optional[tuple[datetime, DateSource]]:
        """Extract date from EXIF metadata."""
        date = self.exif_reader.get_date(file_path)
        if date:
            return date, DateSource.EXIF
        return None

    def _get_video_metadata_date(self, file_path: Path) -> Optional[tuple[datetime, DateSource]]:
        """Extract date from video metadata (creation_time, etc.)."""
        if self.video_reader is None:
            return None
        date = self.video_reader.get_creation_date(file_path)
        if date:
            return date, DateSource.VIDEO_METADATA
        return None

    def _get_filesystem_date(self, file_path: Path) -> Optional[tuple[datetime, DateSource]]:
        """
        Get date from filesystem.

        Prefers modification date (more reliable after file copies),
        falls back to creation date.
        """
        try:
            stat = file_path.stat()

            # Prefer modification time (survives file copies)
            mtime = datetime.fromtimestamp(stat.st_mtime)
            if mtime:
                return mtime, DateSource.FILESYSTEM_MODIFIED

            # Fall back to creation time
            ctime = None
            if hasattr(stat, "st_birthtime"):
                # macOS
                ctime = datetime.fromtimestamp(stat.st_birthtime)
            elif os.name == "nt":
                # Windows: st_ctime is creation time
                ctime = datetime.fromtimestamp(stat.st_ctime)

            if ctime:
                return ctime, DateSource.FILESYSTEM_CREATED

            return None

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

    def _get_filename_date(self, file_path: Path) -> Optional[tuple[datetime, DateSource]]:
        """
        Extract date from filename patterns.

        Recognizes patterns like:
        - IMG_20240315_143000.jpg (YYYYMMDD_HHMMSS)
        - IMG_090831.jpg (YYMMDD)
        - 2024-03-15_photo.jpg (YYYY-MM-DD)
        - IMG-20240315-WA0001.jpg (WhatsApp)
        - Screenshot_20240315_143000.png (Screenshots)
        
        Returns None if filename_date_enabled is False.
        """
        if not self.filename_date_enabled:
            return None
            
        filename = file_path.stem  # Filename without extension

        for pattern, date_type in FILENAME_DATE_PATTERNS:
            match = pattern.search(filename)
            if not match:
                continue

            try:
                groups = match.groups()

                if date_type == "ymdhms" and len(groups) >= 6:
                    year = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])
                    hour = int(groups[3])
                    minute = int(groups[4])
                    second = int(groups[5])
                    if self._is_valid_date(year, month, day) and self._is_valid_time(hour, minute, second):
                        return datetime(year, month, day, hour, minute, second), DateSource.FILENAME

                elif date_type == "ymd" and len(groups) >= 3:
                    year = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])
                    if self._is_valid_date(year, month, day):
                        return datetime(year, month, day), DateSource.FILENAME

                elif date_type == "yymmdd" and len(groups) >= 3:
                    # 2-digit year: apply year cutoff
                    yy = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])
                    year = self._expand_two_digit_year(yy)
                    if self._is_valid_date(year, month, day):
                        return datetime(year, month, day), DateSource.FILENAME

            except (ValueError, IndexError):
                continue

        return None

    def _expand_two_digit_year(self, yy: int) -> int:
        """
        Expand a 2-digit year to 4 digits.

        Uses year_cutoff: 00 to cutoff -> 2000s, cutoff+1 to 99 -> 1900s
        Default cutoff=30: 00-30 = 2000-2030, 31-99 = 1931-1999
        """
        if yy <= self.year_cutoff:
            return 2000 + yy
        return 1900 + yy

    def _is_valid_time(self, hour: int, minute: int, second: int) -> bool:
        """Check if time components are valid."""
        return 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59

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


def get_filename_date(
    file_path: Path,
    year_cutoff: int = 30,
) -> Optional[datetime]:
    """
    Convenience function to extract date from filename only.

    Used for date mismatch detection (comparing filename date vs EXIF date).

    Args:
        file_path: Path to the file
        year_cutoff: For 2-digit years

    Returns:
        datetime or None
    """
    engine = DateInferenceEngine(year_cutoff=year_cutoff)
    result = engine._get_filename_date(file_path)
    if result:
        return result[0]
    return None
