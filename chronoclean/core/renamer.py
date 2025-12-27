"""File renaming logic for ChronoClean."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Renamer:
    """Generates new filenames based on configurable patterns."""

    DEFAULT_PATTERN = "{date}_{time}"
    DEFAULT_DATE_FORMAT = "%Y%m%d"
    DEFAULT_TIME_FORMAT = "%H%M%S"

    def __init__(
        self,
        pattern: Optional[str] = None,
        date_format: Optional[str] = None,
        time_format: Optional[str] = None,
        tag_format: str = "_{tag}",
        lowercase_ext: bool = True,
    ):
        """
        Initialize the renamer.

        Args:
            pattern: Filename pattern with placeholders.
                     Supported: {date}, {time}, {tag}, {original}, {counter}
            date_format: strftime format for date
            time_format: strftime format for time
            tag_format: Format for tag insertion (default: "_{tag}")
            lowercase_ext: Convert extensions to lowercase
        """
        self.pattern = pattern or self.DEFAULT_PATTERN
        self.date_format = date_format or self.DEFAULT_DATE_FORMAT
        self.time_format = time_format or self.DEFAULT_TIME_FORMAT
        self.tag_format = tag_format
        self.lowercase_ext = lowercase_ext

    def generate_filename(
        self,
        original_path: Path,
        date: datetime,
        tag: Optional[str] = None,
        counter: Optional[int] = None,
    ) -> str:
        """
        Generate a new filename.

        Args:
            original_path: Original file path (for extension)
            date: Date to use in filename
            tag: Optional folder tag to include
            counter: Optional counter for duplicates

        Returns:
            New filename with extension

        Example:
            original="IMG_1234.JPG", date=2024-03-15 14:30:00
            → "20240315_143000.jpg"
        """
        # Format date and time
        date_str = date.strftime(self.date_format)
        time_str = date.strftime(self.time_format)

        # Get original stem (filename without extension)
        original_stem = original_path.stem

        # Build filename from pattern
        filename = self.pattern

        # Replace placeholders
        filename = filename.replace("{date}", date_str)
        filename = filename.replace("{time}", time_str)
        filename = filename.replace("{original}", original_stem)

        # Handle tag
        if "{tag}" in filename:
            if tag:
                formatted_tag = self._format_tag(tag)
                filename = filename.replace("{tag}", formatted_tag)
            else:
                filename = filename.replace("{tag}", "")
        elif tag:
            # Add tag if pattern doesn't have explicit placeholder
            formatted_tag = self._format_tag(tag)
            tag_part = self.tag_format.replace("{tag}", formatted_tag)
            filename = filename + tag_part

        # Handle counter
        if counter is not None:
            if "{counter}" in filename:
                filename = filename.replace("{counter}", f"{counter:03d}")
            else:
                filename = f"{filename}_{counter:03d}"

        # Clean up any double underscores or trailing underscores
        filename = re.sub(r"_+", "_", filename)
        filename = filename.strip("_")

        # Add extension
        ext = original_path.suffix
        if self.lowercase_ext:
            ext = ext.lower()

        return f"{filename}{ext}"

    def _format_tag(self, tag: str) -> str:
        """
        Format tag for filename inclusion.

        - Remove special characters
        - Replace spaces with underscores
        - Limit length

        Args:
            tag: Raw tag string

        Returns:
            Formatted tag
        """
        # Strip and replace spaces
        formatted = tag.strip()
        formatted = re.sub(r"\s+", "_", formatted)

        # Remove special characters except underscore and hyphen
        formatted = re.sub(r"[^\w\-]", "", formatted)

        # Remove leading/trailing underscores
        formatted = formatted.strip("_-")

        # Limit length (max 30 chars for tag portion)
        max_tag_length = 30
        if len(formatted) > max_tag_length:
            formatted = formatted[:max_tag_length].rstrip("_-")

        return formatted

    def needs_rename(
        self,
        original_path: Path,
        date: datetime,
        tag: Optional[str] = None,
    ) -> bool:
        """
        Check if a file needs to be renamed.

        Returns False if the file already matches the expected pattern.

        Args:
            original_path: Original file path
            date: Expected date
            tag: Optional expected tag

        Returns:
            True if file should be renamed
        """
        expected = self.generate_filename(original_path, date, tag)
        return original_path.name.lower() != expected.lower()


class ConflictResolver:
    """Resolves filename conflicts by adding counters."""

    def __init__(self, renamer: Optional[Renamer] = None):
        """
        Initialize the conflict resolver.

        Args:
            renamer: Renamer instance to use
        """
        self.renamer = renamer or Renamer()
        self._used_names: set[str] = set()

    def resolve(
        self,
        original_path: Path,
        date: datetime,
        tag: Optional[str] = None,
        existing_files: Optional[set[str]] = None,
    ) -> str:
        """
        Generate a unique filename, resolving conflicts.

        Args:
            original_path: Original file path
            date: Date for filename
            tag: Optional tag
            existing_files: Set of existing filenames to avoid

        Returns:
            Unique filename
        """
        existing = existing_files or set()
        all_used = self._used_names | {f.lower() for f in existing}

        # Try base filename first
        filename = self.renamer.generate_filename(original_path, date, tag)

        if filename.lower() not in all_used:
            self._used_names.add(filename.lower())
            return filename

        # Add counter to resolve conflict
        counter = 1
        while True:
            filename = self.renamer.generate_filename(
                original_path, date, tag, counter=counter
            )
            if filename.lower() not in all_used:
                self._used_names.add(filename.lower())
                return filename
            counter += 1

            # Safety limit
            if counter > 9999:
                raise RuntimeError(
                    f"Cannot resolve filename conflict for {original_path}"
                )

    def reset(self) -> None:
        """Reset the used names tracking."""
        self._used_names.clear()
