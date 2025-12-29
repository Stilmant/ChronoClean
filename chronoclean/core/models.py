"""Data models for ChronoClean."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class DateSource(Enum):
    """Origin of the detected date."""

    EXIF = "exif"
    VIDEO_METADATA = "video_metadata"  # v0.3: Date from video container metadata
    FILESYSTEM_CREATED = "filesystem_created"
    FILESYSTEM_MODIFIED = "filesystem_modified"
    FOLDER_NAME = "folder_name"
    FILENAME = "filename"  # v0.2: Date extracted from filename
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"


class FileType(Enum):
    """Supported file types."""

    IMAGE = "image"
    VIDEO = "video"
    RAW = "raw"
    UNKNOWN = "unknown"


@dataclass
class FileRecord:
    """Represents a single file in the scan."""

    source_path: Path
    file_type: FileType
    size_bytes: int

    # Date information
    detected_date: Optional[datetime] = None
    date_source: DateSource = DateSource.UNKNOWN

    # Computed destinations (filled by sorter)
    destination_folder: Optional[Path] = None
    destination_filename: Optional[str] = None

    # Folder tag info
    source_folder_name: Optional[str] = None
    folder_tag: Optional[str] = None
    folder_tag_usable: bool = False

    # Status flags
    needs_rename: bool = False
    has_exif: bool = False
    exif_error: Optional[str] = None

    # v0.2: Filename date and mismatch detection
    filename_date: Optional[datetime] = None
    date_mismatch: bool = False
    date_mismatch_days: Optional[int] = None

    # v0.2: Duplicate detection
    file_hash: Optional[str] = None
    duplicate_of: Optional[Path] = None
    is_duplicate: bool = False

    # v0.3: Video metadata and error categorization
    video_metadata_date: Optional[datetime] = None  # Raw video creation date
    error_category: Optional[str] = None  # Categorized error type

    @property
    def destination_path(self) -> Optional[Path]:
        """Full destination path if both folder and filename are set."""
        if self.destination_folder and self.destination_filename:
            return self.destination_folder / self.destination_filename
        return None

    @property
    def extension(self) -> str:
        """File extension (lowercase, with dot)."""
        return self.source_path.suffix.lower()

    @property
    def original_filename(self) -> str:
        """Original filename without path."""
        return self.source_path.name


@dataclass
class ScanResult:
    """Result of scanning a directory."""

    source_root: Path
    total_files: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    error_files: int = 0

    files: list[FileRecord] = field(default_factory=list)
    folder_tags_detected: list[str] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)

    # v0.3: Error categorization
    errors_by_category: dict[str, int] = field(default_factory=dict)

    scan_duration_seconds: float = 0.0
    scan_timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """Percentage of successfully processed files."""
        if self.total_files == 0:
            return 0.0
        return (self.processed_files / self.total_files) * 100

    def add_file(self, record: FileRecord) -> None:
        """Add a file record to the result."""
        self.files.append(record)
        self.processed_files += 1

    def add_error(self, path: Path, error: str, category: Optional[str] = None) -> None:
        """Record an error for a file.
        
        Args:
            path: Path to the file that caused the error
            error: Error message
            category: Optional error category for aggregation
        """
        self.errors.append((path, error))
        self.error_files += 1
        if category:
            self.errors_by_category[category] = self.errors_by_category.get(category, 0) + 1

    def add_skipped(self) -> None:
        """Record a skipped file."""
        self.skipped_files += 1

    def increment_error_category(self, category: str) -> None:
        """Increment error count for a category without adding to errors list.
        
        Use for warnings/issues that don't prevent processing.
        """
        self.errors_by_category[category] = self.errors_by_category.get(category, 0) + 1


@dataclass
class MoveOperation:
    """Represents a single file move operation."""

    source: Path
    destination: Path
    new_filename: Optional[str] = None
    reason: str = ""

    @property
    def destination_path(self) -> Path:
        """Full destination path including filename."""
        if self.new_filename:
            return self.destination / self.new_filename
        return self.destination / self.source.name


@dataclass
class OperationPlan:
    """Plan for file operations (for dry-run and apply)."""

    moves: list[MoveOperation] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)  # path, reason
    conflicts: list[tuple[Path, Path, str]] = field(default_factory=list)  # src, dst, reason

    @property
    def total_operations(self) -> int:
        """Total number of planned operations."""
        return len(self.moves)

    @property
    def total_skipped(self) -> int:
        """Total number of skipped files."""
        return len(self.skipped)

    def add_move(
        self,
        source: Path,
        destination: Path,
        new_filename: Optional[str] = None,
        reason: str = "",
    ) -> None:
        """Add a move operation to the plan."""
        self.moves.append(MoveOperation(source, destination, new_filename, reason))

    def add_skip(self, path: Path, reason: str) -> None:
        """Add a skipped file to the plan."""
        self.skipped.append((path, reason))

    def add_conflict(self, source: Path, destination: Path, reason: str) -> None:
        """Add a conflict to the plan."""
        self.conflicts.append((source, destination, reason))
