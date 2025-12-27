"""Folder tag detection and classification for ChronoClean."""

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FolderTagger:
    """Detects and classifies folder names for potential use as file tags."""

    # Default ignore patterns (case-insensitive)
    DEFAULT_IGNORE_LIST = [
        "tosort", "unsorted", "misc", "backup", "temp", "tmp",
        "download", "downloads", "dcim", "camera", "pictures",
        "photos", "images", "100apple", "100andro", "camera roll",
        "new folder", "untitled", "unknown", "other", "various",
        "screenshot", "screenshots", "inbox", "import", "imported",
        "exports", "export", "shared", "public", "private",
    ]

    # Patterns that look like camera-generated folder names
    CAMERA_FOLDER_PATTERNS = [
        re.compile(r"^\d{3}[A-Z]{5}$", re.IGNORECASE),    # 100APPLE, 101ANDRO
        re.compile(r"^\d{3}_\d{4}$"),                      # 100_0001
        re.compile(r"^IMG_\d+$", re.IGNORECASE),          # IMG_0001
        re.compile(r"^DSC_?\d+$", re.IGNORECASE),         # DSC0001, DSC_0001
        re.compile(r"^DCIM$", re.IGNORECASE),             # DCIM
        re.compile(r"^\d{8}$"),                            # 20240315 (just date)
    ]

    def __init__(
        self,
        ignore_list: Optional[list[str]] = None,
        force_list: Optional[list[str]] = None,
        min_length: int = 3,
        max_length: int = 40,
        distance_threshold: float = 0.75,
    ):
        """
        Initialize the folder tagger.

        Args:
            ignore_list: Folder names to never use as tags
            force_list: Folder names to always use as tags
            min_length: Minimum tag length
            max_length: Maximum tag length
            distance_threshold: Similarity threshold for detecting existing tags
        """
        self.ignore_list = {s.lower() for s in (ignore_list or self.DEFAULT_IGNORE_LIST)}
        self.force_list = {s.lower() for s in (force_list or [])}
        self.min_length = min_length
        self.max_length = max_length
        self.distance_threshold = distance_threshold

    def is_meaningful(self, folder_name: str) -> bool:
        """
        Determine if a folder name is meaningful for tagging.

        Returns True if:
        - Not in ignore list
        - Meets length requirements
        - Contains actual words (not just numbers/dates)
        - Not a camera-generated folder name

        Args:
            folder_name: Name of the folder

        Returns:
            True if the folder name is meaningful
        """
        usable, _ = self.classify_folder(folder_name)
        return usable

    def classify_folder(self, folder_name: str) -> tuple[bool, str]:
        """
        Classify a folder name.

        Args:
            folder_name: Name of the folder

        Returns:
            Tuple of (usable: bool, reason: str)
        """
        if not folder_name:
            return False, "empty"

        name_lower = folder_name.lower().strip()

        # Check force list first (overrides everything)
        if name_lower in self.force_list:
            return True, "in_force_list"

        # Check ignore list
        if name_lower in self.ignore_list:
            return False, "in_ignore_list"

        # Check length
        if len(folder_name) < self.min_length:
            return False, "too_short"

        if len(folder_name) > self.max_length:
            return False, "too_long"

        # Check for camera-generated patterns
        for pattern in self.CAMERA_FOLDER_PATTERNS:
            if pattern.match(folder_name):
                return False, "camera_generated"

        # Check if it's just numbers or date-like
        if self._is_only_numbers_or_date(folder_name):
            return False, "numbers_only"

        # Check if it contains at least some letters
        if not any(c.isalpha() for c in folder_name):
            return False, "no_letters"

        return True, "meaningful"

    def _is_only_numbers_or_date(self, name: str) -> bool:
        """Check if the name is only numbers, possibly with separators."""
        # Remove common separators
        cleaned = re.sub(r"[-_./\s]", "", name)
        return cleaned.isdigit()

    def extract_tag(self, folder_path: Path) -> Optional[str]:
        """
        Extract the best tag from a folder path.

        Walks up the path to find the first meaningful folder name.

        Args:
            folder_path: Path to check (can be file path, will use parent)

        Returns:
            Meaningful folder name or None
        """
        if folder_path.is_file():
            folder_path = folder_path.parent

        # Walk up the path (check up to 3 levels)
        current = folder_path
        for _ in range(3):
            if not current or current == current.parent:
                break

            folder_name = current.name
            if self.is_meaningful(folder_name):
                return self.format_tag(folder_name)

            current = current.parent

        return None

    def format_tag(self, folder_name: str) -> str:
        """
        Format a folder name for use as a tag.

        - Strips whitespace
        - Replaces spaces with underscores
        - Removes special characters (keeps alphanumeric and underscore)
        - Truncates to max_length

        Args:
            folder_name: Raw folder name

        Returns:
            Formatted tag string
        """
        # Strip and replace spaces
        tag = folder_name.strip()
        tag = re.sub(r"\s+", "_", tag)

        # Remove special characters except underscore and hyphen
        tag = re.sub(r"[^\w\-]", "", tag)

        # Remove leading/trailing underscores
        tag = tag.strip("_-")

        # Truncate if needed
        if len(tag) > self.max_length:
            tag = tag[:self.max_length].rstrip("_-")

        return tag

    def is_tag_in_filename(
        self,
        filename: str,
        tag: str,
        threshold: Optional[float] = None,
    ) -> bool:
        """
        Check if tag is already present in filename (fuzzy match).

        Uses string similarity to detect if the tag or similar
        text already appears in the filename.

        Args:
            filename: Filename to check
            tag: Tag to look for
            threshold: Similarity threshold (default: self.distance_threshold)

        Returns:
            True if tag appears to be in filename
        """
        if not filename or not tag:
            return False

        threshold = threshold or self.distance_threshold

        # Exact match (case-insensitive)
        filename_lower = filename.lower()
        tag_lower = tag.lower()

        if tag_lower in filename_lower:
            return True

        # Check similarity with parts of the filename
        # Split filename into parts (by underscore, hyphen, space)
        filename_stem = Path(filename).stem
        parts = re.split(r"[-_\s]+", filename_stem)

        for part in parts:
            if len(part) < 2:
                continue

            similarity = SequenceMatcher(None, part.lower(), tag_lower).ratio()
            if similarity >= threshold:
                return True

        # Also check the whole stem
        similarity = SequenceMatcher(None, filename_stem.lower(), tag_lower).ratio()
        if similarity >= threshold:
            return True

        return False

    def should_add_tag(
        self,
        filename: str,
        folder_path: Path,
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if a tag should be added to a filename.

        Args:
            filename: Current filename
            folder_path: Path to the folder

        Returns:
            Tuple of (should_add: bool, tag: str or None)
        """
        tag = self.extract_tag(folder_path)

        if not tag:
            return False, None

        # Check if tag is already in filename
        if self.is_tag_in_filename(filename, tag):
            logger.debug(f"Tag '{tag}' already in filename '{filename}'")
            return False, tag

        return True, tag


def get_folder_tag(folder_path: Path) -> Optional[str]:
    """
    Convenience function to get a folder tag.

    Args:
        folder_path: Path to check

    Returns:
        Tag string or None
    """
    tagger = FolderTagger()
    return tagger.extract_tag(folder_path)
