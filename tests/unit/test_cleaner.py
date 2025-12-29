"""Tests for the cleaner module."""

from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.core.cleaner import Cleaner, CleanupResult
from chronoclean.core.verification import (
    InputSource,
    MatchType,
    VerificationReport,
    VerificationStatus,
    VerificationSummary,
    VerifyEntry,
)


class TestCleanupResult:
    """Tests for CleanupResult dataclass."""
    
    def test_success_rate_with_deletions(self):
        """Test success_rate calculation."""
        result = CleanupResult(
            total_eligible=10,
            deleted=8,
            skipped=1,
            failed=1,
        )
        
        assert result.success_rate == 80.0
    
    def test_success_rate_with_no_eligible(self):
        """Test success_rate with no eligible files."""
        result = CleanupResult()
        
        assert result.success_rate == 0.0


class TestCleaner:
    """Tests for Cleaner class."""
    
    @pytest.fixture
    def sample_verification_report(self, tmp_path) -> VerificationReport:
        """Create a sample verification report."""
        summary = VerificationSummary(
            total=3,
            ok=2,
            mismatch=1,
        )
        
        # Create source files
        source1 = tmp_path / "source1.jpg"
        source2 = tmp_path / "source2.jpg"
        source3 = tmp_path / "source3.jpg"
        
        source1.write_bytes(b"content1")  # OK
        source2.write_bytes(b"content2")  # OK
        source3.write_bytes(b"content3")  # MISMATCH
        
        # Create destination files (for eligible cleanup)
        dest1 = tmp_path / "dest1.jpg"
        dest2 = tmp_path / "dest2.jpg"
        dest3 = tmp_path / "dest3.jpg"
        
        dest1.write_bytes(b"content1")  # Matching
        dest2.write_bytes(b"content2")  # Matching
        dest3.write_bytes(b"different")  # Mismatched
        
        entries = [
            VerifyEntry(
                source_path=str(source1),
                expected_destination_path=str(dest1),
                actual_destination_path=str(dest1),
                status=VerificationStatus.OK,
                match_type=MatchType.EXPECTED_PATH,
                hash_algorithm="sha256",
            ),
            VerifyEntry(
                source_path=str(source2),
                expected_destination_path=str(dest2),
                actual_destination_path=str(dest2),
                status=VerificationStatus.OK,
                match_type=MatchType.EXPECTED_PATH,
                hash_algorithm="sha256",
            ),
            VerifyEntry(
                source_path=str(source3),
                expected_destination_path=str(dest3),
                actual_destination_path=str(dest3),
                status=VerificationStatus.MISMATCH,
                hash_algorithm="sha256",
            ),
        ]
        
        return VerificationReport(
            verify_id="verify_test",
            created_at=datetime.now(),
            source_root=str(tmp_path),
            destination_root=str(tmp_path / "dest"),
            input_source=InputSource.RUN_RECORD,
            run_id="test_run",
            hash_algorithm="sha256",
            summary=summary,
            entries=entries,
        )
    
    def test_get_cleanup_eligible_filters_ok(self, sample_verification_report):
        """Test getting cleanup eligible entries."""
        cleaner = Cleaner(dry_run=True, require_sha256=True)
        
        eligible = cleaner.get_cleanup_eligible(sample_verification_report)
        
        # Should only include OK entries
        assert len(eligible) == 2
        for entry in eligible:
            assert entry.status == VerificationStatus.OK
    
    def test_dry_run_does_not_delete(self, sample_verification_report, tmp_path):
        """Test that dry run mode doesn't delete files."""
        cleaner = Cleaner(dry_run=True, require_sha256=True)
        
        result = cleaner.cleanup(sample_verification_report)
        
        # Files should still exist
        source1 = tmp_path / "source1.jpg"
        source2 = tmp_path / "source2.jpg"
        assert source1.exists()
        assert source2.exists()
        
        # Result should reflect what would be deleted
        assert result.total_eligible == 2
        assert result.deleted == 2  # Shows what would be deleted in dry run
    
    def test_live_mode_deletes_files(self, sample_verification_report, tmp_path):
        """Test that live mode deletes files."""
        cleaner = Cleaner(dry_run=False, require_sha256=True)
        
        source1 = tmp_path / "source1.jpg"
        source2 = tmp_path / "source2.jpg"
        source3 = tmp_path / "source3.jpg"
        
        assert source1.exists()
        assert source2.exists()
        
        result = cleaner.cleanup(sample_verification_report)
        
        # OK files should be deleted
        assert not source1.exists()
        assert not source2.exists()
        
        # MISMATCH file should still exist
        assert source3.exists()
        
        assert result.deleted == 2
    
    def test_require_sha256_filters_quick(self, tmp_path):
        """Test that require_sha256 filters out quick verification."""
        source = tmp_path / "source.jpg"
        source.write_bytes(b"content")
        
        entry = VerifyEntry(
            source_path=str(source),
            expected_destination_path=str(tmp_path / "dest.jpg"),
            actual_destination_path=str(tmp_path / "dest.jpg"),
            status=VerificationStatus.OK,
            match_type=MatchType.EXPECTED_PATH,
            hash_algorithm="quick",  # Not sha256
        )
        
        summary = VerificationSummary(total=1, ok=1)
        report = VerificationReport(
            verify_id="test",
            created_at=datetime.now(),
            source_root=str(tmp_path),
            destination_root=str(tmp_path / "dest"),
            input_source=InputSource.RUN_RECORD,
            run_id="test_run",
            hash_algorithm="quick",
            summary=summary,
            entries=[entry],
        )
        
        cleaner = Cleaner(dry_run=True, require_sha256=True)
        eligible = cleaner.get_cleanup_eligible(report)
        
        assert len(eligible) == 0
    
    def test_cleanup_handles_missing_files(self, tmp_path):
        """Test cleanup handles already-deleted files gracefully."""
        summary = VerificationSummary(total=1, ok=1)
        
        entry = VerifyEntry(
            source_path=str(tmp_path / "nonexistent.jpg"),
            expected_destination_path=str(tmp_path / "dest.jpg"),
            actual_destination_path=str(tmp_path / "dest.jpg"),
            status=VerificationStatus.OK,
            match_type=MatchType.EXPECTED_PATH,
            hash_algorithm="sha256",
        )
        
        report = VerificationReport(
            verify_id="test",
            created_at=datetime.now(),
            source_root=str(tmp_path),
            destination_root=str(tmp_path / "dest"),
            input_source=InputSource.RUN_RECORD,
            run_id="test_run",
            hash_algorithm="sha256",
            summary=summary,
            entries=[entry],
        )
        
        cleaner = Cleaner(dry_run=False, require_sha256=True)
        eligible = cleaner.get_cleanup_eligible(report)
        
        # File doesn't exist, so not eligible
        assert len(eligible) == 0


class TestCleanerFilters:
    """Tests for cleaner status filters."""
    
    @pytest.fixture
    def report_with_various_statuses(self, tmp_path) -> VerificationReport:
        """Create report with various verification statuses."""
        # Create source test files
        ok_file = tmp_path / "ok.jpg"
        dup_file = tmp_path / "duplicate.jpg"
        mismatch_file = tmp_path / "mismatch.jpg"
        missing_dest_file = tmp_path / "missing_dest.jpg"
        
        ok_file.write_bytes(b"content")
        dup_file.write_bytes(b"content")
        mismatch_file.write_bytes(b"content")
        missing_dest_file.write_bytes(b"content")
        
        # Create destination files for OK and duplicate entries
        d1 = tmp_path / "d1.jpg"
        d2_actual = tmp_path / "d2_actual.jpg"
        d3 = tmp_path / "d3.jpg"
        
        d1.write_bytes(b"content")  # OK destination
        d2_actual.write_bytes(b"content")  # Duplicate actual destination
        d3.write_bytes(b"different")  # Mismatch destination
        
        entries = [
            VerifyEntry(
                source_path=str(ok_file),
                expected_destination_path=str(d1),
                actual_destination_path=str(d1),
                status=VerificationStatus.OK,
                match_type=MatchType.EXPECTED_PATH,
                hash_algorithm="sha256",
            ),
            VerifyEntry(
                source_path=str(dup_file),
                expected_destination_path=str(tmp_path / "d2.jpg"),
                actual_destination_path=str(d2_actual),
                status=VerificationStatus.OK_EXISTING_DUPLICATE,
                match_type=MatchType.CONTENT_SEARCH,
                hash_algorithm="sha256",
            ),
            VerifyEntry(
                source_path=str(mismatch_file),
                expected_destination_path=str(d3),
                actual_destination_path=str(d3),
                status=VerificationStatus.MISMATCH,
                hash_algorithm="sha256",
            ),
            VerifyEntry(
                source_path=str(tmp_path / "missing_source.jpg"),  # Doesn't exist
                expected_destination_path=str(tmp_path / "d4.jpg"),
                actual_destination_path=None,
                status=VerificationStatus.MISSING_SOURCE,
                hash_algorithm="sha256",
            ),
            VerifyEntry(
                source_path=str(missing_dest_file),
                expected_destination_path=str(tmp_path / "d5.jpg"),
                actual_destination_path=None,
                status=VerificationStatus.MISSING_DESTINATION,
                hash_algorithm="sha256",
            ),
        ]
        
        summary = VerificationSummary(
            total=5,
            ok=1,
            mismatch=1,
            missing_source=1,
            missing_destination=1,
            ok_existing_duplicate=1,
        )
        
        return VerificationReport(
            verify_id="test",
            created_at=datetime.now(),
            source_root=str(tmp_path),
            destination_root=str(tmp_path / "dest"),
            input_source=InputSource.RUN_RECORD,
            run_id="test_run",
            hash_algorithm="sha256",
            summary=summary,
            entries=entries,
        )
    
    def test_ok_and_duplicate_are_eligible(self, report_with_various_statuses):
        """Test that OK and OK_EXISTING_DUPLICATE are eligible."""
        cleaner = Cleaner(dry_run=True, require_sha256=True)
        
        eligible = cleaner.get_cleanup_eligible(report_with_various_statuses)
        
        statuses = {e.status for e in eligible}
        assert VerificationStatus.OK in statuses
        assert VerificationStatus.OK_EXISTING_DUPLICATE in statuses
        assert VerificationStatus.MISMATCH not in statuses
        assert len(eligible) == 2
    
    def test_missing_source_not_eligible(self, report_with_various_statuses):
        """Test that MISSING_SOURCE entries are not eligible."""
        cleaner = Cleaner(dry_run=True, require_sha256=True)
        
        eligible = cleaner.get_cleanup_eligible(report_with_various_statuses)
        
        # MISSING_SOURCE entries should not be in eligible list
        for entry in eligible:
            assert entry.status != VerificationStatus.MISSING_SOURCE
