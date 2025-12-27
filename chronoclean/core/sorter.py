"""Sorting logic for ChronoClean."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Sorter:
    """Computes destination paths for files based on their dates."""

    # Supported folder structures
    STRUCTURES = {
        "YYYY": "{year}",
        "YYYY/MM": "{year}/{month:02d}",
        "YYYY/MM/DD": "{year}/{month:02d}/{day:02d}",
    }

    def __init__(
        self,
        destination_root: Path,
        folder_structure: str = "YYYY/MM",
    ):
        """
        Initialize the sorter.

        Args:
            destination_root: Root folder for sorted files
            folder_structure: Pattern like "YYYY/MM" or "YYYY/MM/DD"
        """
        self.destination_root = Path(destination_root)
        self.folder_structure = folder_structure

        if folder_structure not in self.STRUCTURES:
            logger.warning(
                f"Unknown folder structure '{folder_structure}', using 'YYYY/MM'"
            )
            self.folder_structure = "YYYY/MM"

    def compute_destination_folder(self, date: datetime) -> Path:
        """
        Compute the destination folder for a given date.

        Args:
            date: Date to use for folder computation

        Returns:
            Path to the destination folder

        Example:
            date=2024-03-15, structure="YYYY/MM"
            → destination_root / "2024" / "03"
        """
        template = self.STRUCTURES[self.folder_structure]
        folder_path = template.format(
            year=date.year,
            month=date.month,
            day=date.day,
        )
        return self.destination_root / folder_path

    def compute_full_destination(
        self,
        source_path: Path,
        date: datetime,
        new_filename: Optional[str] = None,
    ) -> Path:
        """
        Compute full destination path including filename.

        Args:
            source_path: Original file path (for extension if needed)
            date: Detected date
            new_filename: Optional renamed filename (with or without extension)

        Returns:
            Full destination path
        """
        folder = self.compute_destination_folder(date)

        if new_filename:
            # If new_filename doesn't have extension, add from source
            if not Path(new_filename).suffix:
                ext = source_path.suffix.lower()
                new_filename = f"{new_filename}{ext}"
            return folder / new_filename
        else:
            return folder / source_path.name

    def get_relative_destination(
        self,
        date: datetime,
        filename: str,
    ) -> str:
        """
        Get the relative destination path (for display purposes).

        Args:
            date: Date to use for folder computation
            filename: Filename to include

        Returns:
            Relative path string like "2024/03/photo.jpg"
        """
        template = self.STRUCTURES[self.folder_structure]
        folder_path = template.format(
            year=date.year,
            month=date.month,
            day=date.day,
        )
        return f"{folder_path}/{filename}"


class SortingPlan:
    """Builds a sorting plan for multiple files."""

    def __init__(
        self,
        destination_root: Path,
        folder_structure: str = "YYYY/MM",
    ):
        """
        Initialize the sorting plan builder.

        Args:
            destination_root: Root folder for sorted files
            folder_structure: Pattern like "YYYY/MM" or "YYYY/MM/DD"
        """
        self.sorter = Sorter(destination_root, folder_structure)
        self._destinations: dict[Path, Path] = {}
        self._conflicts: list[tuple[Path, Path]] = []

    def add_file(
        self,
        source_path: Path,
        date: datetime,
        new_filename: Optional[str] = None,
    ) -> Path:
        """
        Add a file to the sorting plan.

        Args:
            source_path: Original file path
            date: Detected date
            new_filename: Optional new filename

        Returns:
            Computed destination path
        """
        destination = self.sorter.compute_full_destination(
            source_path, date, new_filename
        )

        # Check for conflicts
        if destination in self._destinations.values():
            # Find which source maps to this destination
            for existing_src, existing_dst in self._destinations.items():
                if existing_dst == destination:
                    self._conflicts.append((source_path, existing_src))
                    break

        self._destinations[source_path] = destination
        return destination

    @property
    def destinations(self) -> dict[Path, Path]:
        """Get all source -> destination mappings."""
        return self._destinations.copy()

    @property
    def conflicts(self) -> list[tuple[Path, Path]]:
        """Get list of conflicting file pairs."""
        return self._conflicts.copy()

    @property
    def has_conflicts(self) -> bool:
        """Check if there are any conflicts."""
        return len(self._conflicts) > 0
