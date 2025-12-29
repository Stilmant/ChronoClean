"""Tests for the verifier module."""

from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.core.run_record import (
    ApplyRunRecord,
    ConfigSignature,
    OperationType,
    RunMode,
)
from chronoclean.core.verification import (
    InputSource,
    MatchType,
    VerificationStatus,
)
from chronoclean.core.verifier import Verifier


class TestVerifier:
    """Tests for Verifier class."""
    
    @pytest.fixture
    def verifier(self):
        """Create a default verifier."""
        return Verifier(algorithm="sha256")
    
    @pytest.fixture
    def quick_verifier(self):
        """Create a quick mode verifier."""
        return Verifier(algorithm="quick")
    
    def test_verify_single_matching_files(self, verifier, tmp_path):
        """Test verification of matching files."""
        source = tmp_path / "source.jpg"
        dest = tmp_path / "dest.jpg"
        content = b"Same content"
        source.write_bytes(content)
        dest.write_bytes(content)
        
        entry = verifier.verify_single(source, dest)
        
        assert entry.status == VerificationStatus.OK
        assert entry.source_hash == entry.destination_hash
        assert entry.source_hash is not None
    
    def test_verify_single_mismatched_files(self, verifier, tmp_path):
        """Test verification of mismatched files."""
        source = tmp_path / "source.jpg"
        dest = tmp_path / "dest.jpg"
        source.write_bytes(b"Content A")
        dest.write_bytes(b"Content B")
        
        entry = verifier.verify_single(source, dest)
        
        assert entry.status == VerificationStatus.MISMATCH
        assert entry.source_hash != entry.destination_hash
    
    def test_verify_single_missing_destination(self, verifier, tmp_path):
        """Test verification when destination is missing."""
        source = tmp_path / "source.jpg"
        dest = tmp_path / "nonexistent.jpg"
        source.write_bytes(b"content")
        
        entry = verifier.verify_single(source, dest)
        
        assert entry.status == VerificationStatus.MISSING_DESTINATION
    
    def test_verify_single_missing_source(self, verifier, tmp_path):
        """Test verification when source is missing."""
        source = tmp_path / "nonexistent.jpg"
        dest = tmp_path / "dest.jpg"
        dest.write_bytes(b"content")
        
        entry = verifier.verify_single(source, dest)
        
        assert entry.status == VerificationStatus.MISSING_SOURCE
    
    def test_quick_mode_size_match(self, quick_verifier, tmp_path):
        """Test quick mode with matching size."""
        source = tmp_path / "source.jpg"
        dest = tmp_path / "dest.jpg"
        content = b"Same size content"
        source.write_bytes(content)
        dest.write_bytes(content)  # Same size
        
        entry = quick_verifier.verify_single(source, dest)
        
        assert entry.status == VerificationStatus.OK
        assert entry.hash_algorithm == "quick"
    
    def test_quick_mode_size_mismatch(self, quick_verifier, tmp_path):
        """Test quick mode with different size."""
        source = tmp_path / "source.jpg"
        dest = tmp_path / "dest.jpg"
        source.write_bytes(b"Short")
        dest.write_bytes(b"Much longer content here")
        
        entry = quick_verifier.verify_single(source, dest)
        
        assert entry.status == VerificationStatus.MISMATCH
        assert "Size mismatch" in (entry.error or "")
    
    def test_invalid_algorithm_raises(self):
        """Test that invalid algorithm raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            Verifier(algorithm="invalid")


class TestVerifyFromRunRecord:
    """Tests for verify_from_run_record method."""
    
    @pytest.fixture
    def sample_config_signature(self):
        """Create a sample config signature."""
        return ConfigSignature(
            folder_structure="YYYY/MM",
            renaming_enabled=False,
            renaming_pattern="{date}",
            folder_tags_enabled=False,
            on_collision="check_hash",
        )
    
    @pytest.fixture
    def run_record_with_copies(self, sample_config_signature, tmp_path):
        """Create a run record with copy operations."""
        record = ApplyRunRecord(
            run_id="20241229_120000",
            created_at=datetime(2024, 12, 29, 12, 0, 0),
            source_root=str(tmp_path / "source"),
            destination_root=str(tmp_path / "dest"),
            mode=RunMode.LIVE_COPY,
            config_signature=sample_config_signature,
        )
        
        # Create test files
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()
        
        # File 1: Matching
        (source_dir / "file1.jpg").write_bytes(b"content1")
        (dest_dir / "file1.jpg").write_bytes(b"content1")
        record.add_entry(
            source_dir / "file1.jpg",
            dest_dir / "file1.jpg",
            OperationType.COPY,
        )
        
        # File 2: Mismatched
        (source_dir / "file2.jpg").write_bytes(b"content2a")
        (dest_dir / "file2.jpg").write_bytes(b"content2b")
        record.add_entry(
            source_dir / "file2.jpg",
            dest_dir / "file2.jpg",
            OperationType.COPY,
        )
        
        return record
    
    def test_verify_run_record_creates_report(self, run_record_with_copies):
        """Test that verification creates a report."""
        verifier = Verifier()
        
        report = verifier.verify_from_run_record(run_record_with_copies)
        
        assert report.input_source == InputSource.RUN_RECORD
        assert report.run_id == "20241229_120000"
        assert report.summary.total == 2
        assert report.summary.ok == 1
        assert report.summary.mismatch == 1
    
    def test_verify_empty_run_record(self, sample_config_signature, tmp_path):
        """Test verification of empty run record."""
        record = ApplyRunRecord(
            run_id="20241229_120000",
            created_at=datetime(2024, 12, 29, 12, 0, 0),
            source_root=str(tmp_path),
            destination_root=str(tmp_path / "dest"),
            mode=RunMode.LIVE_COPY,
            config_signature=sample_config_signature,
        )
        
        verifier = Verifier()
        report = verifier.verify_from_run_record(record)
        
        assert report.summary.total == 0
    
    def test_verify_progress_callback(self, run_record_with_copies):
        """Test that progress callback is called."""
        verifier = Verifier()
        progress_calls = []
        
        def callback(current, total):
            progress_calls.append((current, total))
        
        verifier.verify_from_run_record(run_record_with_copies, progress_callback=callback)
        
        # Should be called once per verifiable entry
        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 2)
        assert progress_calls[1] == (2, 2)


class TestVerifyWithContentSearch:
    """Tests for content search verification."""
    
    def test_content_search_disabled_returns_missing(self, tmp_path):
        """Test that disabled content search returns missing_destination."""
        verifier = Verifier(content_search_on_reconstruct=False)
        
        source = tmp_path / "source.jpg"
        dest = tmp_path / "dest.jpg"  # Will not exist
        source.write_bytes(b"content")
        
        entry = verifier.verify_with_content_search(source, dest, tmp_path)
        
        assert entry.status == VerificationStatus.MISSING_DESTINATION
    
    def test_content_search_finds_match(self, tmp_path):
        """Test that content search finds matching file."""
        verifier = Verifier(content_search_on_reconstruct=True)
        
        source = tmp_path / "source.jpg"
        expected_dest = tmp_path / "expected.jpg"  # Does not exist
        actual_dest = tmp_path / "actual.jpg"  # Has matching content
        
        content = b"unique content here"
        source.write_bytes(content)
        actual_dest.write_bytes(content)
        
        entry = verifier.verify_with_content_search(source, expected_dest, tmp_path)
        
        assert entry.status == VerificationStatus.OK_EXISTING_DUPLICATE
        assert entry.actual_destination_path == str(actual_dest)
        assert entry.match_type == MatchType.CONTENT_SEARCH
    
    def test_content_search_expected_path_exists_takes_priority(self, tmp_path):
        """Test that expected path takes priority over content search."""
        verifier = Verifier(content_search_on_reconstruct=True)
        
        source = tmp_path / "source.jpg"
        expected_dest = tmp_path / "dest.jpg"
        
        content = b"content"
        source.write_bytes(content)
        expected_dest.write_bytes(content)
        
        entry = verifier.verify_with_content_search(source, expected_dest, tmp_path)
        
        assert entry.status == VerificationStatus.OK
        assert entry.match_type == MatchType.EXPECTED_PATH
    
    def test_content_search_no_match_returns_missing(self, tmp_path):
        """Test that no content match returns missing_destination."""
        verifier = Verifier(content_search_on_reconstruct=True)
        
        # Source is in source_dir, search happens in dest_dir
        source_dir = tmp_path / "source"
        dest_dir = tmp_path / "dest"
        source_dir.mkdir()
        dest_dir.mkdir()
        
        source = source_dir / "source.jpg"
        expected_dest = dest_dir / "expected.jpg"
        other = dest_dir / "other.jpg"
        
        source.write_bytes(b"source content")
        other.write_bytes(b"different content")  # No match for source
        
        entry = verifier.verify_with_content_search(source, expected_dest, dest_dir)
        
        assert entry.status == VerificationStatus.MISSING_DESTINATION
    
    def test_content_search_quick_mode_not_supported(self, tmp_path):
        """Test that quick mode doesn't support content search."""
        verifier = Verifier(algorithm="quick", content_search_on_reconstruct=True)
        
        source = tmp_path / "source.jpg"
        expected_dest = tmp_path / "expected.jpg"  # Does not exist
        source.write_bytes(b"content")
        
        entry = verifier.verify_with_content_search(source, expected_dest, tmp_path)
        
        assert entry.status == VerificationStatus.MISSING_DESTINATION
        assert "Content search not supported" in (entry.error or "")
