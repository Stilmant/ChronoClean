"""Cleaner module for ChronoClean v0.3.1.

Handles safe deletion of source files after verification.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from chronoclean.core.verification import (
    VerificationReport,
    VerificationStatus,
    VerifyEntry,
)

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    
    total_eligible: int = 0
    deleted: int = 0
    skipped: int = 0
    failed: int = 0
    bytes_freed: int = 0
    
    deleted_paths: list[Path] = field(default_factory=list)
    failed_paths: list[tuple[Path, str]] = field(default_factory=list)
    skipped_paths: list[tuple[Path, str]] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Percentage of successful deletions."""
        if self.total_eligible == 0:
            return 0.0
        return (self.deleted / self.total_eligible) * 100


class Cleaner:
    """Safely deletes source files after verification."""
    
    def __init__(
        self,
        dry_run: bool = True,
        require_sha256: bool = True,
    ):
        """Initialize the cleaner.
        
        Args:
            dry_run: If True, don't actually delete files.
            require_sha256: Only delete if verification used sha256 algorithm.
        """
        self.dry_run = dry_run
        self.require_sha256 = require_sha256
    
    def get_cleanup_eligible(
        self,
        report: VerificationReport,
    ) -> list[VerifyEntry]:
        """Get entries eligible for cleanup.
        
        Args:
            report: Verification report.
            
        Returns:
            List of entries that can be safely deleted.
        """
        eligible = []
        
        for entry in report.entries:
            if self._is_eligible(entry):
                eligible.append(entry)
        
        return eligible
    
    def _is_eligible(self, entry: VerifyEntry) -> bool:
        """Check if an entry is eligible for cleanup.
        
        Args:
            entry: Verification entry.
            
        Returns:
            True if eligible for cleanup.
        """
        # Status must be OK or OK_EXISTING_DUPLICATE
        if entry.status not in (VerificationStatus.OK, VerificationStatus.OK_EXISTING_DUPLICATE):
            return False
        
        # Must have sha256 verification (unless require_sha256 is False)
        if self.require_sha256 and entry.hash_algorithm != "sha256":
            return False
        
        # Source path must exist
        source_path = Path(entry.source_path)
        if not source_path.exists():
            return False
        
        # Destination must exist (or have been verified as existing)
        if entry.actual_destination_path:
            dest_path = Path(entry.actual_destination_path)
            if not dest_path.exists():
                return False
        
        return True
    
    def cleanup(
        self,
        report: VerificationReport,
        progress_callback: Optional[callable] = None,
    ) -> CleanupResult:
        """Delete source files for verified OK entries.
        
        Args:
            report: Verification report.
            progress_callback: Optional callback(current, total) for progress.
            
        Returns:
            CleanupResult with counts and details.
        """
        result = CleanupResult()
        eligible = self.get_cleanup_eligible(report)
        result.total_eligible = len(eligible)
        
        for i, entry in enumerate(eligible):
            if progress_callback:
                progress_callback(i + 1, len(eligible))
            
            source_path = Path(entry.source_path)
            
            # Double-check destination still exists
            if entry.actual_destination_path:
                dest_path = Path(entry.actual_destination_path)
                if not dest_path.exists():
                    result.skipped += 1
                    result.skipped_paths.append((source_path, "destination no longer exists"))
                    continue
            
            # Get file size before deletion
            try:
                file_size = source_path.stat().st_size
            except OSError:
                file_size = 0
            
            # Delete or simulate
            if self.dry_run:
                result.deleted += 1
                result.bytes_freed += file_size
                result.deleted_paths.append(source_path)
                logger.debug(f"Would delete: {source_path}")
            else:
                try:
                    source_path.unlink()
                    result.deleted += 1
                    result.bytes_freed += file_size
                    result.deleted_paths.append(source_path)
                    logger.info(f"Deleted: {source_path}")
                except OSError as e:
                    result.failed += 1
                    result.failed_paths.append((source_path, str(e)))
                    logger.warning(f"Failed to delete {source_path}: {e}")
        
        return result
    
    def cleanup_single(
        self,
        entry: VerifyEntry,
    ) -> tuple[bool, Optional[str]]:
        """Delete a single source file.
        
        Args:
            entry: Verification entry.
            
        Returns:
            Tuple of (success, error_message).
        """
        if not self._is_eligible(entry):
            return (False, "Entry not eligible for cleanup")
        
        source_path = Path(entry.source_path)
        
        if self.dry_run:
            return (True, None)
        
        try:
            source_path.unlink()
            return (True, None)
        except OSError as e:
            return (False, str(e))


def format_bytes(num_bytes: int) -> str:
    """Format bytes as human-readable string.
    
    Args:
        num_bytes: Number of bytes.
        
    Returns:
        Formatted string like "1.5 GB".
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"
