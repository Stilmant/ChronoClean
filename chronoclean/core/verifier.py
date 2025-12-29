"""Verifier engine for ChronoClean v0.3.1.

Handles hash-based verification of copy operations.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from chronoclean.config.schema import VerifyConfig
from chronoclean.core.hashing import compute_file_hash, compare_file_hashes, hash_matches_any
from chronoclean.core.run_record import ApplyRunRecord, OperationType
from chronoclean.core.verification import (
    InputSource,
    MatchType,
    VerificationReport,
    VerificationStatus,
    VerifyEntry,
    generate_verify_id,
)

logger = logging.getLogger(__name__)


class Verifier:
    """Verifies copy operations by comparing source and destination hashes."""
    
    def __init__(
        self,
        algorithm: str = "sha256",
        content_search_on_reconstruct: bool = False,
    ):
        """Initialize the verifier.
        
        Args:
            algorithm: Hash algorithm to use ('sha256' or 'quick').
            content_search_on_reconstruct: Enable content search for reconstruction mode.
        """
        if algorithm not in ("sha256", "quick"):
            raise ValueError(f"Unsupported algorithm: {algorithm}. Use 'sha256' or 'quick'.")
        
        self.algorithm = algorithm
        self.content_search_on_reconstruct = content_search_on_reconstruct
    
    def verify_from_run_record(
        self,
        run_record: ApplyRunRecord,
        progress_callback: Optional[callable] = None,
    ) -> VerificationReport:
        """Verify operations from an apply run record.
        
        Args:
            run_record: The run record to verify.
            progress_callback: Optional callback(current, total) for progress updates.
            
        Returns:
            VerificationReport with results.
        """
        start_time = time.time()
        timestamp = datetime.now()
        
        report = VerificationReport(
            verify_id=generate_verify_id(timestamp),
            created_at=timestamp,
            source_root=run_record.source_root,
            destination_root=run_record.destination_root,
            input_source=InputSource.RUN_RECORD,
            run_id=run_record.run_id,
            hash_algorithm=self.algorithm,
        )
        
        # Only verify copy operations (moves have no source to verify)
        verifiable = run_record.verifiable_entries
        total = len(verifiable)
        
        for i, entry in enumerate(verifiable):
            if progress_callback:
                progress_callback(i + 1, total)
            
            source_path = Path(entry.source_path)
            dest_path = Path(entry.destination_path) if entry.destination_path else None
            
            verify_entry = self._verify_single_entry(
                source_path=source_path,
                expected_dest_path=dest_path,
                match_type=MatchType.EXPECTED_PATH,
            )
            report.add_entry(verify_entry)
        
        # Also record move operations as missing_source (source no longer exists)
        for entry in run_record.move_entries:
            source_path = Path(entry.source_path)
            dest_path = Path(entry.destination_path) if entry.destination_path else None
            
            verify_entry = VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(dest_path) if dest_path else None,
                actual_destination_path=str(dest_path) if dest_path and dest_path.exists() else None,
                status=VerificationStatus.MISSING_SOURCE,
                match_type=MatchType.EXPECTED_PATH,
                hash_algorithm=self.algorithm,
            )
            report.add_entry(verify_entry)
        
        report.duration_seconds = time.time() - start_time
        return report
    
    def verify_single(
        self,
        source_path: Path,
        destination_path: Path,
    ) -> VerifyEntry:
        """Verify a single source-destination pair.
        
        Args:
            source_path: Path to source file.
            destination_path: Path to destination file.
            
        Returns:
            VerifyEntry with result.
        """
        return self._verify_single_entry(
            source_path=source_path,
            expected_dest_path=destination_path,
            match_type=MatchType.EXPECTED_PATH,
        )
    
    def _verify_single_entry(
        self,
        source_path: Path,
        expected_dest_path: Optional[Path],
        match_type: MatchType,
    ) -> VerifyEntry:
        """Internal verification of a single file pair.
        
        Args:
            source_path: Path to source file.
            expected_dest_path: Expected destination path.
            match_type: How the destination was determined.
            
        Returns:
            VerifyEntry with result.
        """
        # Check source exists
        if not source_path.exists():
            return VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(expected_dest_path) if expected_dest_path else None,
                actual_destination_path=None,
                status=VerificationStatus.MISSING_SOURCE,
                match_type=match_type,
                hash_algorithm=self.algorithm,
            )
        
        # Check destination exists
        if expected_dest_path is None or not expected_dest_path.exists():
            return VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(expected_dest_path) if expected_dest_path else None,
                actual_destination_path=None,
                status=VerificationStatus.MISSING_DESTINATION,
                match_type=match_type,
                hash_algorithm=self.algorithm,
            )
        
        # Quick mode: compare size and modification time only
        if self.algorithm == "quick":
            try:
                source_stat = source_path.stat()
                dest_stat = expected_dest_path.stat()
                
                # Size must match exactly
                if source_stat.st_size != dest_stat.st_size:
                    return VerifyEntry(
                        source_path=str(source_path),
                        expected_destination_path=str(expected_dest_path),
                        actual_destination_path=str(expected_dest_path),
                        status=VerificationStatus.MISMATCH,
                        match_type=match_type,
                        hash_algorithm="quick",
                        error="Size mismatch",
                    )
                
                # For quick mode, size match is enough (timestamps may differ due to copy)
                return VerifyEntry(
                    source_path=str(source_path),
                    expected_destination_path=str(expected_dest_path),
                    actual_destination_path=str(expected_dest_path),
                    status=VerificationStatus.OK,
                    match_type=match_type,
                    hash_algorithm="quick",
                )
            except OSError as e:
                return VerifyEntry(
                    source_path=str(source_path),
                    expected_destination_path=str(expected_dest_path),
                    actual_destination_path=None,
                    status=VerificationStatus.ERROR,
                    match_type=match_type,
                    hash_algorithm="quick",
                    error=str(e),
                )
        
        # SHA-256 mode: compare hashes
        try:
            match, source_hash, dest_hash = compare_file_hashes(
                source_path,
                expected_dest_path,
                algorithm=self.algorithm,
            )
            
            if source_hash is None:
                return VerifyEntry(
                    source_path=str(source_path),
                    expected_destination_path=str(expected_dest_path),
                    actual_destination_path=None,
                    status=VerificationStatus.ERROR,
                    match_type=match_type,
                    hash_algorithm=self.algorithm,
                    error="Could not compute source hash",
                )
            
            if dest_hash is None:
                return VerifyEntry(
                    source_path=str(source_path),
                    expected_destination_path=str(expected_dest_path),
                    actual_destination_path=None,
                    status=VerificationStatus.ERROR,
                    match_type=match_type,
                    hash_algorithm=self.algorithm,
                    source_hash=source_hash,
                    error="Could not compute destination hash",
                )
            
            status = VerificationStatus.OK if match else VerificationStatus.MISMATCH
            
            return VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(expected_dest_path),
                actual_destination_path=str(expected_dest_path),
                status=status,
                match_type=match_type,
                hash_algorithm=self.algorithm,
                source_hash=source_hash,
                destination_hash=dest_hash,
            )
            
        except Exception as e:
            logger.warning(f"Error verifying {source_path}: {e}")
            return VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(expected_dest_path),
                actual_destination_path=None,
                status=VerificationStatus.ERROR,
                match_type=match_type,
                hash_algorithm=self.algorithm,
                error=str(e),
            )
    
    def verify_with_content_search(
        self,
        source_path: Path,
        expected_dest_path: Optional[Path],
        search_root: Path,
    ) -> VerifyEntry:
        """Verify with content search fallback.
        
        Used in reconstruction mode when expected destination doesn't exist.
        
        Args:
            source_path: Path to source file.
            expected_dest_path: Expected destination path (may not exist).
            search_root: Root directory to search for matching content.
            
        Returns:
            VerifyEntry with result.
        """
        # First try expected path
        if expected_dest_path and expected_dest_path.exists():
            return self._verify_single_entry(
                source_path=source_path,
                expected_dest_path=expected_dest_path,
                match_type=MatchType.EXPECTED_PATH,
            )
        
        # Source must exist for content search
        if not source_path.exists():
            return VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(expected_dest_path) if expected_dest_path else None,
                actual_destination_path=None,
                status=VerificationStatus.MISSING_SOURCE,
                match_type=MatchType.UNKNOWN,
                hash_algorithm=self.algorithm,
            )
        
        # Content search disabled
        if not self.content_search_on_reconstruct:
            return VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(expected_dest_path) if expected_dest_path else None,
                actual_destination_path=None,
                status=VerificationStatus.MISSING_DESTINATION,
                match_type=MatchType.EXPECTED_PATH,
                hash_algorithm=self.algorithm,
            )
        
        # Quick mode doesn't support content search
        if self.algorithm == "quick":
            return VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(expected_dest_path) if expected_dest_path else None,
                actual_destination_path=None,
                status=VerificationStatus.MISSING_DESTINATION,
                match_type=MatchType.EXPECTED_PATH,
                hash_algorithm="quick",
                error="Content search not supported in quick mode",
            )
        
        # Build candidate list: same extension, similar size
        try:
            source_ext = source_path.suffix.lower()
            source_size = source_path.stat().st_size
            size_tolerance = 0  # Exact size match for content search
            
            candidates = []
            for candidate in search_root.rglob(f"*{source_ext}"):
                if candidate.is_file():
                    try:
                        if abs(candidate.stat().st_size - source_size) <= size_tolerance:
                            candidates.append(candidate)
                    except OSError:
                        continue
            
            if not candidates:
                return VerifyEntry(
                    source_path=str(source_path),
                    expected_destination_path=str(expected_dest_path) if expected_dest_path else None,
                    actual_destination_path=None,
                    status=VerificationStatus.MISSING_DESTINATION,
                    match_type=MatchType.CONTENT_SEARCH,
                    hash_algorithm=self.algorithm,
                )
            
            # Search for content match
            found, match_path, source_hash, dest_hash = hash_matches_any(
                source_path,
                candidates,
                algorithm=self.algorithm,
            )
            
            if found and match_path:
                return VerifyEntry(
                    source_path=str(source_path),
                    expected_destination_path=str(expected_dest_path) if expected_dest_path else None,
                    actual_destination_path=str(match_path),
                    status=VerificationStatus.OK_EXISTING_DUPLICATE,
                    match_type=MatchType.CONTENT_SEARCH,
                    hash_algorithm=self.algorithm,
                    source_hash=source_hash,
                    destination_hash=dest_hash,
                )
            
            return VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(expected_dest_path) if expected_dest_path else None,
                actual_destination_path=None,
                status=VerificationStatus.MISSING_DESTINATION,
                match_type=MatchType.CONTENT_SEARCH,
                hash_algorithm=self.algorithm,
                source_hash=source_hash,
            )
            
        except Exception as e:
            logger.warning(f"Error during content search for {source_path}: {e}")
            return VerifyEntry(
                source_path=str(source_path),
                expected_destination_path=str(expected_dest_path) if expected_dest_path else None,
                actual_destination_path=None,
                status=VerificationStatus.ERROR,
                match_type=MatchType.CONTENT_SEARCH,
                hash_algorithm=self.algorithm,
                error=str(e),
            )


def create_verifier_from_config(verify_config: VerifyConfig) -> Verifier:
    """Create a Verifier from configuration.
    
    Args:
        verify_config: Verify configuration.
        
    Returns:
        Configured Verifier instance.
    """
    return Verifier(
        algorithm=verify_config.algorithm,
        content_search_on_reconstruct=verify_config.content_search_on_reconstruct,
    )
