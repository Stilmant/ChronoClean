"""Tests for the verification module."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.core.verification import (
    InputSource,
    MatchType,
    VerificationReport,
    VerificationStatus,
    VerificationSummary,
    VerifyEntry,
    generate_verify_id,
    get_verification_filename,
)


class TestVerifyEntry:
    """Tests for VerifyEntry dataclass."""
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        entry = VerifyEntry(
            source_path="/source/file.jpg",
            expected_destination_path="/dest/2024/01/file.jpg",
            actual_destination_path="/dest/2024/01/file.jpg",
            status=VerificationStatus.OK,
            match_type=MatchType.EXPECTED_PATH,
            hash_algorithm="sha256",
            source_hash="abc123",
            destination_hash="abc123",
        )
        
        result = entry.to_dict()
        
        assert result["source_path"] == "/source/file.jpg"
        assert result["status"] == "ok"
        assert result["match_type"] == "expected_path"
        assert result["source_hash"] == "abc123"
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "source_path": "/source/file.jpg",
            "expected_destination_path": "/dest/file.jpg",
            "actual_destination_path": "/dest/file.jpg",
            "status": "mismatch",
            "match_type": "expected_path",
            "hash_algorithm": "sha256",
            "source_hash": "abc",
            "destination_hash": "def",
            "error": None,
        }
        
        entry = VerifyEntry.from_dict(data)
        
        assert entry.source_path == "/source/file.jpg"
        assert entry.status == VerificationStatus.MISMATCH
        assert entry.source_hash == "abc"
        assert entry.destination_hash == "def"
    
    def test_is_cleanup_eligible_ok_sha256(self):
        """Test that OK with sha256 is cleanup eligible."""
        entry = VerifyEntry(
            source_path="/source/file.jpg",
            expected_destination_path="/dest/file.jpg",
            actual_destination_path="/dest/file.jpg",
            status=VerificationStatus.OK,
            hash_algorithm="sha256",
        )
        
        assert entry.is_cleanup_eligible is True
    
    def test_is_cleanup_eligible_ok_existing_duplicate(self):
        """Test that OK_EXISTING_DUPLICATE is cleanup eligible."""
        entry = VerifyEntry(
            source_path="/source/file.jpg",
            expected_destination_path="/dest/file.jpg",
            actual_destination_path="/dest/other.jpg",
            status=VerificationStatus.OK_EXISTING_DUPLICATE,
            hash_algorithm="sha256",
        )
        
        assert entry.is_cleanup_eligible is True
    
    def test_is_cleanup_eligible_mismatch_not_eligible(self):
        """Test that mismatch is not cleanup eligible."""
        entry = VerifyEntry(
            source_path="/source/file.jpg",
            expected_destination_path="/dest/file.jpg",
            actual_destination_path="/dest/file.jpg",
            status=VerificationStatus.MISMATCH,
            hash_algorithm="sha256",
        )
        
        assert entry.is_cleanup_eligible is False
    
    def test_is_cleanup_eligible_quick_not_eligible(self):
        """Test that quick mode is not cleanup eligible."""
        entry = VerifyEntry(
            source_path="/source/file.jpg",
            expected_destination_path="/dest/file.jpg",
            actual_destination_path="/dest/file.jpg",
            status=VerificationStatus.OK,
            hash_algorithm="quick",
        )
        
        assert entry.is_cleanup_eligible is False


class TestVerificationSummary:
    """Tests for VerificationSummary dataclass."""
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        summary = VerificationSummary(
            total=10,
            ok=7,
            ok_existing_duplicate=1,
            mismatch=1,
            missing_destination=1,
        )
        
        result = summary.to_dict()
        
        assert result["total"] == 10
        assert result["ok"] == 7
        assert result["ok_existing_duplicate"] == 1
    
    def test_cleanup_eligible_count(self):
        """Test cleanup eligible count property."""
        summary = VerificationSummary(
            total=10,
            ok=5,
            ok_existing_duplicate=2,
            mismatch=3,
        )
        
        assert summary.cleanup_eligible_count == 7


class TestVerificationReport:
    """Tests for VerificationReport dataclass."""
    
    @pytest.fixture
    def sample_report(self):
        """Create a sample verification report."""
        return VerificationReport(
            verify_id="20241229_120000",
            created_at=datetime(2024, 12, 29, 12, 0, 0),
            source_root="/source",
            destination_root="/dest",
            input_source=InputSource.RUN_RECORD,
            run_id="20241229_110000",
        )
    
    def test_add_entry_updates_summary(self, sample_report):
        """Test that add_entry updates summary counts."""
        entry = VerifyEntry(
            source_path="/source/file.jpg",
            expected_destination_path="/dest/file.jpg",
            actual_destination_path="/dest/file.jpg",
            status=VerificationStatus.OK,
        )
        
        sample_report.add_entry(entry)
        
        assert sample_report.summary.total == 1
        assert sample_report.summary.ok == 1
        assert len(sample_report.entries) == 1
    
    def test_add_multiple_entries_tracks_statuses(self, sample_report):
        """Test tracking multiple entry statuses."""
        entries = [
            VerifyEntry("/s/1.jpg", "/d/1.jpg", "/d/1.jpg", VerificationStatus.OK),
            VerifyEntry("/s/2.jpg", "/d/2.jpg", "/d/2.jpg", VerificationStatus.OK),
            VerifyEntry("/s/3.jpg", "/d/3.jpg", "/d/3.jpg", VerificationStatus.MISMATCH),
            VerifyEntry("/s/4.jpg", "/d/4.jpg", None, VerificationStatus.MISSING_DESTINATION),
        ]
        
        for entry in entries:
            sample_report.add_entry(entry)
        
        assert sample_report.summary.total == 4
        assert sample_report.summary.ok == 2
        assert sample_report.summary.mismatch == 1
        assert sample_report.summary.missing_destination == 1
    
    def test_to_json_and_back(self, sample_report):
        """Test JSON serialization roundtrip."""
        entry = VerifyEntry(
            source_path="/source/file.jpg",
            expected_destination_path="/dest/file.jpg",
            actual_destination_path="/dest/file.jpg",
            status=VerificationStatus.OK,
            source_hash="abc123",
            destination_hash="abc123",
        )
        sample_report.add_entry(entry)
        
        json_str = sample_report.to_json()
        restored = VerificationReport.from_json(json_str)
        
        assert restored.verify_id == sample_report.verify_id
        assert restored.input_source == InputSource.RUN_RECORD
        assert len(restored.entries) == 1
        assert restored.summary.ok == 1
    
    def test_cleanup_eligible_entries_filters(self, sample_report):
        """Test that cleanup_eligible_entries filters correctly."""
        entries = [
            VerifyEntry("/s/1.jpg", "/d/1.jpg", "/d/1.jpg", VerificationStatus.OK, hash_algorithm="sha256"),
            VerifyEntry("/s/2.jpg", "/d/2.jpg", "/d/2.jpg", VerificationStatus.OK, hash_algorithm="quick"),
            VerifyEntry("/s/3.jpg", "/d/3.jpg", "/d/3.jpg", VerificationStatus.MISMATCH, hash_algorithm="sha256"),
        ]
        
        for entry in entries:
            sample_report.add_entry(entry)
        
        eligible = sample_report.cleanup_eligible_entries
        
        assert len(eligible) == 1
        assert eligible[0].source_path == "/s/1.jpg"
    
    def test_ok_entries_includes_ok_and_duplicate(self, sample_report):
        """Test that ok_entries includes both OK and OK_EXISTING_DUPLICATE."""
        entries = [
            VerifyEntry("/s/1.jpg", "/d/1.jpg", "/d/1.jpg", VerificationStatus.OK),
            VerifyEntry("/s/2.jpg", "/d/2.jpg", "/d/other.jpg", VerificationStatus.OK_EXISTING_DUPLICATE),
            VerifyEntry("/s/3.jpg", "/d/3.jpg", "/d/3.jpg", VerificationStatus.MISMATCH),
        ]
        
        for entry in entries:
            sample_report.add_entry(entry)
        
        ok_entries = sample_report.ok_entries
        
        assert len(ok_entries) == 2


class TestVerificationIdGeneration:
    """Tests for verification ID and filename generation."""
    
    def test_generate_verify_id_format(self):
        """Test verification ID format includes timestamp and suffix."""
        ts = datetime(2024, 12, 29, 15, 30, 45)
        
        result = generate_verify_id(ts)
        
        # Format: YYYYMMDD_HHMMSS_<4-char-hex>
        assert result.startswith("20241229_153045_")
        assert len(result) == 20  # 8 + 1 + 6 + 1 + 4
        # Check suffix is valid hex
        suffix = result.split("_")[2]
        int(suffix, 16)  # Should not raise
    
    def test_generate_verify_id_uniqueness(self):
        """Test that verification IDs differ when suffix differs."""
        from unittest.mock import patch
        
        ts = datetime(2024, 12, 29, 15, 30, 45)
        
        # Mock token_hex to return different values
        with patch("secrets.token_hex", return_value="aaaa"):
            id1 = generate_verify_id(ts)
        
        with patch("secrets.token_hex", return_value="bbbb"):
            id2 = generate_verify_id(ts)
        
        # Same timestamp but different suffix should produce different IDs
        assert id1 != id2
        assert id1.endswith("_aaaa")
        assert id2.endswith("_bbbb")
    
    def test_get_verification_filename(self):
        """Test filename generation."""
        result = get_verification_filename("20241229_120000_abcd")
        
        assert result == "20241229_120000_abcd_verify.json"
