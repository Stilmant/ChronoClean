"""Safe file operations for ChronoClean."""

import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileOperationError(Exception):
    """Error during file operation."""

    pass


class FileOperations:
    """Safe file operations with conflict handling."""

    def __init__(
        self,
        dry_run: bool = True,
        create_dirs: bool = True,
        preserve_metadata: bool = True,
    ):
        """
        Initialize file operations handler.

        Args:
            dry_run: If True, only simulate operations
            create_dirs: If True, create destination directories as needed
            preserve_metadata: If True, preserve file metadata during copy/move
        """
        self.dry_run = dry_run
        self.create_dirs = create_dirs
        self.preserve_metadata = preserve_metadata

    def move_file(
        self,
        source: Path,
        destination: Path,
    ) -> tuple[bool, str]:
        """
        Move a file safely.

        Args:
            source: Source file path
            destination: Destination file path (full path including filename)

        Returns:
            Tuple of (success: bool, message: str)
        """
        source = Path(source).resolve()
        destination = Path(destination).resolve()

        # Validate source
        if not source.exists():
            return False, f"Source file not found: {source}"

        if not source.is_file():
            return False, f"Source is not a file: {source}"

        # Check if destination already exists
        if destination.exists():
            return False, f"Destination already exists: {destination}"

        # Dry run mode
        if self.dry_run:
            logger.info(f"[DRY RUN] Would move: {source} -> {destination}")
            return True, "Dry run - no changes made"

        try:
            # Create destination directory if needed
            if self.create_dirs:
                destination.parent.mkdir(parents=True, exist_ok=True)

            # Move the file
            if self.preserve_metadata:
                shutil.move(str(source), str(destination))
            else:
                shutil.copy2(str(source), str(destination))
                source.unlink()

            logger.info(f"Moved: {source} -> {destination}")
            return True, "File moved successfully"

        except OSError as e:
            logger.error(f"Failed to move {source}: {e}")
            return False, f"Move failed: {e}"

    def copy_file(
        self,
        source: Path,
        destination: Path,
    ) -> tuple[bool, str]:
        """
        Copy a file safely.

        Args:
            source: Source file path
            destination: Destination file path (full path including filename)

        Returns:
            Tuple of (success: bool, message: str)
        """
        source = Path(source).resolve()
        destination = Path(destination).resolve()

        # Validate source
        if not source.exists():
            return False, f"Source file not found: {source}"

        if not source.is_file():
            return False, f"Source is not a file: {source}"

        # Check if destination already exists
        if destination.exists():
            return False, f"Destination already exists: {destination}"

        # Dry run mode
        if self.dry_run:
            logger.info(f"[DRY RUN] Would copy: {source} -> {destination}")
            return True, "Dry run - no changes made"

        try:
            # Create destination directory if needed
            if self.create_dirs:
                destination.parent.mkdir(parents=True, exist_ok=True)

            # Copy the file
            if self.preserve_metadata:
                shutil.copy2(str(source), str(destination))
            else:
                shutil.copy(str(source), str(destination))

            logger.info(f"Copied: {source} -> {destination}")
            return True, "File copied successfully"

        except OSError as e:
            logger.error(f"Failed to copy {source}: {e}")
            return False, f"Copy failed: {e}"

    def ensure_unique_path(self, path: Path) -> Path:
        """
        Ensure the path is unique by adding suffix if needed.

        Args:
            path: Desired file path

        Returns:
            Unique path (may be same as input if already unique)

        Example:
            "photo.jpg" exists → "photo_001.jpg"
        """
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        counter = 1
        while True:
            new_name = f"{stem}_{counter:03d}{suffix}"
            new_path = parent / new_name

            if not new_path.exists():
                return new_path

            counter += 1

            # Safety limit
            if counter > 9999:
                raise FileOperationError(
                    f"Cannot find unique filename for {path}"
                )

    def check_disk_space(
        self,
        path: Path,
        required_bytes: int,
    ) -> tuple[bool, int]:
        """
        Check if sufficient disk space is available.

        Args:
            path: Path to check (will use the volume containing this path)
            required_bytes: Required space in bytes

        Returns:
            Tuple of (has_space: bool, available_bytes: int)
        """
        try:
            # Get disk usage for the volume containing path
            if path.exists():
                usage = shutil.disk_usage(path)
            else:
                # Use parent directory
                parent = path.parent
                while not parent.exists() and parent != parent.parent:
                    parent = parent.parent
                usage = shutil.disk_usage(parent)

            available = usage.free
            has_space = available >= required_bytes

            return has_space, available

        except OSError as e:
            logger.warning(f"Cannot check disk space for {path}: {e}")
            return True, 0  # Assume OK if we can't check

    def ensure_directory(self, path: Path) -> bool:
        """
        Ensure a directory exists.

        Args:
            path: Directory path to create

        Returns:
            True if directory exists or was created
        """
        if self.dry_run:
            logger.debug(f"[DRY RUN] Would create directory: {path}")
            return True

        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as e:
            logger.error(f"Cannot create directory {path}: {e}")
            return False


class BatchOperations:
    """Execute multiple file operations with rollback support."""

    def __init__(
        self,
        file_ops: Optional[FileOperations] = None,
        dry_run: bool = True,
    ):
        """
        Initialize batch operations handler.

        Args:
            file_ops: FileOperations instance
            dry_run: If True, only simulate operations
        """
        self.file_ops = file_ops or FileOperations(dry_run=dry_run)
        self.dry_run = dry_run
        self._completed: list[tuple[Path, Path]] = []
        self._failed: list[tuple[Path, Path, str]] = []

    def execute_moves(
        self,
        operations: list[tuple[Path, Path]],
    ) -> tuple[int, int]:
        """
        Execute a batch of move operations.

        Args:
            operations: List of (source, destination) tuples

        Returns:
            Tuple of (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0

        for source, destination in operations:
            success, message = self.file_ops.move_file(source, destination)

            if success:
                self._completed.append((source, destination))
                success_count += 1
            else:
                self._failed.append((source, destination, message))
                failure_count += 1

        return success_count, failure_count

    def rollback(self) -> int:
        """
        Rollback completed operations (move files back).

        Returns:
            Number of successfully rolled back operations
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would rollback operations")
            return len(self._completed)

        rolled_back = 0

        for source, destination in reversed(self._completed):
            # Move back: destination -> source
            success, _ = self.file_ops.move_file(destination, source)
            if success:
                rolled_back += 1

        self._completed.clear()
        return rolled_back

    @property
    def completed(self) -> list[tuple[Path, Path]]:
        """Get list of completed operations."""
        return self._completed.copy()

    @property
    def failed(self) -> list[tuple[Path, Path, str]]:
        """Get list of failed operations with error messages."""
        return self._failed.copy()

    def reset(self) -> None:
        """Reset operation tracking."""
        self._completed.clear()
        self._failed.clear()
