"""EXIF metadata reader for ChronoClean."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import exifread

logger = logging.getLogger(__name__)


class ExifReadError(Exception):
    """Error reading EXIF data."""

    pass


@dataclass
class ExifData:
    """Extracted EXIF information."""

    date_taken: Optional[datetime] = None
    date_original: Optional[datetime] = None
    date_digitized: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    orientation: Optional[int] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    raw_tags: dict[str, Any] = field(default_factory=dict)

    @property
    def best_date(self) -> Optional[datetime]:
        """Get the best available date in priority order."""
        return self.date_original or self.date_taken or self.date_digitized


class ExifReader:
    """Reads EXIF data from image files."""

    # EXIF date tags to check, in priority order
    DATE_TAGS = [
        "EXIF DateTimeOriginal",
        "EXIF DateTimeDigitized",
        "Image DateTime",
        "EXIF DateTime",
    ]

    # Common EXIF date formats
    DATE_FORMATS = [
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y:%m:%d %H:%M",
        "%Y-%m-%d %H:%M",
    ]

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        ".jpg", ".jpeg", ".tiff", ".tif", ".heic", ".heif",
        ".png", ".webp", ".cr2", ".nef", ".arw", ".dng"
    }

    def __init__(self, skip_errors: bool = True):
        """
        Initialize the EXIF reader.

        Args:
            skip_errors: If True, return empty ExifData on errors instead of raising
        """
        self.skip_errors = skip_errors

    def read(self, file_path: Path) -> ExifData:
        """
        Read EXIF data from an image file.

        Args:
            file_path: Path to the image file

        Returns:
            ExifData object with extracted metadata

        Raises:
            ExifReadError: If the file cannot be read and skip_errors is False
        """
        if not file_path.exists():
            if self.skip_errors:
                logger.warning(f"File not found: {file_path}")
                return ExifData()
            raise ExifReadError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            logger.debug(f"Unsupported extension for EXIF: {ext}")
            return ExifData()

        try:
            with open(file_path, "rb") as f:
                tags = exifread.process_file(f, details=False)

            return self._parse_tags(tags)

        except Exception as e:
            logger.warning(f"Error reading EXIF from {file_path}: {e}")
            if self.skip_errors:
                return ExifData()
            raise ExifReadError(f"Cannot read EXIF from {file_path}: {e}")

    def _parse_tags(self, tags: dict[str, Any]) -> ExifData:
        """Parse EXIF tags into ExifData object."""
        data = ExifData()
        data.raw_tags = {str(k): str(v) for k, v in tags.items()}

        # Parse dates
        if "EXIF DateTimeOriginal" in tags:
            data.date_original = self._parse_date(str(tags["EXIF DateTimeOriginal"]))
        if "EXIF DateTimeDigitized" in tags:
            data.date_digitized = self._parse_date(str(tags["EXIF DateTimeDigitized"]))
        if "Image DateTime" in tags:
            data.date_taken = self._parse_date(str(tags["Image DateTime"]))

        # Parse camera info
        if "Image Make" in tags:
            data.camera_make = str(tags["Image Make"]).strip()
        if "Image Model" in tags:
            data.camera_model = str(tags["Image Model"]).strip()

        # Parse orientation
        if "Image Orientation" in tags:
            try:
                data.orientation = int(str(tags["Image Orientation"]).split()[0])
            except (ValueError, IndexError):
                pass

        # Parse dimensions
        if "EXIF ExifImageWidth" in tags:
            try:
                data.image_width = int(str(tags["EXIF ExifImageWidth"]))
            except ValueError:
                pass
        if "EXIF ExifImageLength" in tags:
            try:
                data.image_height = int(str(tags["EXIF ExifImageLength"]))
            except ValueError:
                pass

        return data

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse an EXIF date string into a datetime object.

        Args:
            date_str: Date string from EXIF tags

        Returns:
            datetime object or None if parsing fails
        """
        if not date_str or date_str.strip() in ("", "0000:00:00 00:00:00"):
            return None

        date_str = date_str.strip()

        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.debug(f"Could not parse EXIF date: {date_str}")
        return None

    def get_date(self, file_path: Path) -> Optional[datetime]:
        """
        Convenience method to get just the date.

        Returns the first valid date found in priority order:
        1. DateTimeOriginal
        2. DateTimeDigitized
        3. DateTime

        Args:
            file_path: Path to the image file

        Returns:
            datetime object or None
        """
        exif_data = self.read(file_path)
        return exif_data.best_date

    def has_exif(self, file_path: Path) -> bool:
        """
        Check if a file has EXIF data.

        Args:
            file_path: Path to the image file

        Returns:
            True if the file has EXIF data with a date
        """
        return self.get_date(file_path) is not None
