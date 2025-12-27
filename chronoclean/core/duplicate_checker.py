"""Duplicate detection via file hashing (v0.2)."""

import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DuplicateChecker:
    """
    Detect duplicate files using content hashing.
    
    Uses SHA-256 by default for reliable duplicate detection.
    Can detect duplicates before file operations to avoid unnecessary copies.
    """

    # Chunk size for reading files (4MB)
    CHUNK_SIZE = 4 * 1024 * 1024

    def __init__(
        self,
        algorithm: str = "sha256",
        cache_enabled: bool = True,
    ):
        """
        Initialize the duplicate checker.

        Args:
            algorithm: Hash algorithm to use ('sha256' or 'md5')
            cache_enabled: Whether to cache computed hashes
        """
        self.algorithm = algorithm.lower()
        self.cache_enabled = cache_enabled
        self._hash_cache: dict[Path, str] = {}

        # Validate algorithm
        if self.algorithm not in ("sha256", "md5"):
            logger.warning(f"Unknown algorithm '{algorithm}', using sha256")
            self.algorithm = "sha256"

    def compute_hash(self, file_path: Path) -> Optional[str]:
        """
        Compute the hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest of the file hash, or None on error
        """
        # Check cache first
        resolved_path = file_path.resolve()
        if self.cache_enabled and resolved_path in self._hash_cache:
            return self._hash_cache[resolved_path]

        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None

        if not file_path.is_file():
            logger.warning(f"Not a file: {file_path}")
            return None

        try:
            if self.algorithm == "md5":
                hasher = hashlib.md5()
            else:
                hasher = hashlib.sha256()

            with open(file_path, "rb") as f:
                while chunk := f.read(self.CHUNK_SIZE):
                    hasher.update(chunk)

            file_hash = hasher.hexdigest()

            # Cache the result
            if self.cache_enabled:
                self._hash_cache[resolved_path] = file_hash

            return file_hash

        except OSError as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None

    def are_duplicates(self, file1: Path, file2: Path) -> bool:
        """
        Check if two files are duplicates (have identical content).

        Args:
            file1: First file path
            file2: Second file path

        Returns:
            True if files have identical content, False otherwise
        """
        # Quick checks first
        if not file1.exists() or not file2.exists():
            return False

        # Same file (by path)
        if file1.resolve() == file2.resolve():
            return True

        # Different sizes means different content
        try:
            if file1.stat().st_size != file2.stat().st_size:
                return False
        except OSError:
            return False

        # Compare hashes
        hash1 = self.compute_hash(file1)
        hash2 = self.compute_hash(file2)

        if hash1 is None or hash2 is None:
            return False

        return hash1 == hash2

    def find_duplicates_in_list(
        self,
        files: list[Path],
    ) -> dict[str, list[Path]]:
        """
        Find duplicate files within a list.

        Args:
            files: List of file paths to check

        Returns:
            Dictionary mapping hash to list of files with that hash.
            Only includes hashes with multiple files (actual duplicates).
        """
        hash_to_files: dict[str, list[Path]] = {}

        for file_path in files:
            file_hash = self.compute_hash(file_path)
            if file_hash:
                if file_hash not in hash_to_files:
                    hash_to_files[file_hash] = []
                hash_to_files[file_hash].append(file_path)

        # Filter to only include duplicates (2+ files with same hash)
        return {
            h: paths for h, paths in hash_to_files.items()
            if len(paths) > 1
        }

    def check_collision(
        self,
        source: Path,
        destination: Path,
    ) -> tuple[bool, bool]:
        """
        Check if moving/copying source to destination would create a collision.

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            Tuple of (collision_exists, is_duplicate)
            - collision_exists: True if destination already exists
            - is_duplicate: True if destination is a duplicate of source
        """
        if not destination.exists():
            return False, False

        # Destination exists - check if it's a duplicate
        is_dup = self.are_duplicates(source, destination)
        return True, is_dup

    def clear_cache(self) -> None:
        """Clear the hash cache."""
        self._hash_cache.clear()

    def get_cache_size(self) -> int:
        """Get the number of cached hashes."""
        return len(self._hash_cache)


def compute_file_hash(
    file_path: Path,
    algorithm: str = "sha256",
) -> Optional[str]:
    """
    Convenience function to compute a file hash.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm ('sha256' or 'md5')

    Returns:
        Hex digest of the file hash, or None on error
    """
    checker = DuplicateChecker(algorithm=algorithm, cache_enabled=False)
    return checker.compute_hash(file_path)


def are_files_identical(file1: Path, file2: Path) -> bool:
    """
    Convenience function to check if two files are identical.

    Args:
        file1: First file path
        file2: Second file path

    Returns:
        True if files have identical content
    """
    checker = DuplicateChecker(cache_enabled=False)
    return checker.are_duplicates(file1, file2)
