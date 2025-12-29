"""Tests for the run record module."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.core.run_record import (
    ApplyRunRecord,
    ConfigSignature,
    OperationType,
    RunEntry,
    RunMode,
    generate_run_id,
    get_run_filename,
)


class TestRunEntry:
    """Tests for RunEntry dataclass."""
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        entry = RunEntry(
            source_path="/source/file.jpg",
            destination_path="/dest/2024/01/file.jpg",
            operation=OperationType.COPY,
            reason="renamed",
        )
        
        result = entry.to_dict()
        
        assert result["source_path"] == "/source/file.jpg"
        assert result["destination_path"] == "/dest/2024/01/file.jpg"
        assert result["operation"] == "copy"
        assert result["reason"] == "renamed"
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "source_path": "/source/file.jpg",
            "destination_path": "/dest/file.jpg",
            "operation": "move",
            "reason": None,
        }
        
        entry = RunEntry.from_dict(data)
        
        assert entry.source_path == "/source/file.jpg"
        assert entry.destination_path == "/dest/file.jpg"
        assert entry.operation == OperationType.MOVE
        assert entry.reason is None
    
    def test_skip_entry_has_no_destination(self):
        """Test that skip entries can have no destination."""
        entry = RunEntry(
            source_path="/source/file.jpg",
            destination_path=None,
            operation=OperationType.SKIP,
            reason="no date detected",
        )
        
        result = entry.to_dict()
        
        assert result["destination_path"] is None
        assert result["operation"] == "skip"


class TestConfigSignature:
    """Tests for ConfigSignature dataclass."""
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        sig = ConfigSignature(
            folder_structure="YYYY/MM",
            renaming_enabled=True,
            renaming_pattern="{date}_{time}",
            folder_tags_enabled=False,
            on_collision="check_hash",
        )
        
        result = sig.to_dict()
        
        assert result["folder_structure"] == "YYYY/MM"
        assert result["renaming_enabled"] is True
        assert result["on_collision"] == "check_hash"
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "folder_structure": "YYYY/MM/DD",
            "renaming_enabled": False,
            "renaming_pattern": "{date}",
            "folder_tags_enabled": True,
            "on_collision": "rename",
        }
        
        sig = ConfigSignature.from_dict(data)
        
        assert sig.folder_structure == "YYYY/MM/DD"
        assert sig.folder_tags_enabled is True


class TestApplyRunRecord:
    """Tests for ApplyRunRecord dataclass."""
    
    @pytest.fixture
    def sample_config_signature(self):
        """Create a sample config signature."""
        return ConfigSignature(
            folder_structure="YYYY/MM",
            renaming_enabled=True,
            renaming_pattern="{date}_{time}",
            folder_tags_enabled=False,
            on_collision="check_hash",
        )
    
    @pytest.fixture
    def sample_run_record(self, sample_config_signature):
        """Create a sample run record."""
        return ApplyRunRecord(
            run_id="20241229_120000",
            created_at=datetime(2024, 12, 29, 12, 0, 0),
            source_root="/source",
            destination_root="/dest",
            mode=RunMode.LIVE_COPY,
            config_signature=sample_config_signature,
        )
    
    def test_to_dict_empty_record(self, sample_run_record):
        """Test serialization of empty run record."""
        result = sample_run_record.to_dict()
        
        assert result["run_id"] == "20241229_120000"
        assert result["mode"] == "live_copy"
        assert result["entries"] == []
        assert result["summary"]["total_files"] == 0
    
    def test_add_entry_updates_counts(self, sample_run_record, tmp_path):
        """Test that add_entry updates summary counts."""
        source = tmp_path / "source.jpg"
        dest = tmp_path / "dest" / "2024" / "01" / "source.jpg"
        source.write_bytes(b"test")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"test")
        
        sample_run_record.add_entry(source, dest, OperationType.COPY)
        
        assert sample_run_record.total_files == 1
        assert sample_run_record.copied_files == 1
        assert len(sample_run_record.entries) == 1
    
    def test_add_skip_entry(self, sample_run_record, tmp_path):
        """Test adding a skip entry."""
        source = tmp_path / "source.jpg"
        source.write_bytes(b"test")
        
        sample_run_record.add_entry(source, None, OperationType.SKIP, "no date")
        
        assert sample_run_record.skipped_files == 1
        assert sample_run_record.entries[0].destination_path is None
    
    def test_to_json_and_back(self, sample_run_record, tmp_path):
        """Test JSON serialization roundtrip."""
        source = tmp_path / "file.jpg"
        dest = tmp_path / "dest.jpg"
        source.write_bytes(b"test")
        dest.write_bytes(b"test")
        
        sample_run_record.add_entry(source, dest, OperationType.COPY)
        
        json_str = sample_run_record.to_json()
        restored = ApplyRunRecord.from_json(json_str)
        
        assert restored.run_id == sample_run_record.run_id
        assert restored.mode == sample_run_record.mode
        assert len(restored.entries) == 1
        assert restored.copied_files == 1
    
    def test_verifiable_entries_filters_copies(self, sample_run_record, tmp_path):
        """Test that verifiable_entries only returns copy operations."""
        file1 = tmp_path / "file1.jpg"
        file2 = tmp_path / "file2.jpg"
        file1.write_bytes(b"test")
        file2.write_bytes(b"test")
        
        sample_run_record.add_entry(file1, tmp_path / "dest1.jpg", OperationType.COPY)
        sample_run_record.add_entry(file2, tmp_path / "dest2.jpg", OperationType.MOVE)
        sample_run_record.add_entry(tmp_path / "file3.jpg", None, OperationType.SKIP, "skip")
        
        verifiable = sample_run_record.verifiable_entries
        
        assert len(verifiable) == 1
        assert verifiable[0].operation == OperationType.COPY


class TestRunIdGeneration:
    """Tests for run ID and filename generation."""
    
    def test_generate_run_id_format(self):
        """Test run ID format includes timestamp and suffix."""
        ts = datetime(2024, 12, 29, 15, 30, 45)
        
        result = generate_run_id(ts)
        
        # Format: YYYYMMDD_HHMMSS_<4-char-hex>
        assert result.startswith("20241229_153045_")
        assert len(result) == 20  # 8 + 1 + 6 + 1 + 4
        # Check suffix is valid hex
        suffix = result.split("_")[2]
        int(suffix, 16)  # Should not raise
    
    def test_generate_run_id_uses_now_by_default(self):
        """Test that generate_run_id uses current time by default."""
        result = generate_run_id()
        
        # Should be in YYYYMMDD_HHMMSS_XXXX format
        parts = result.split("_")
        assert len(parts) == 3
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS
        assert len(parts[2]) == 4  # hex suffix
    
    def test_generate_run_id_uniqueness(self):
        """Test that run IDs differ when suffix differs."""
        from unittest.mock import patch
        
        ts = datetime(2024, 12, 29, 15, 30, 45)
        
        # Mock token_hex to return different values
        with patch("secrets.token_hex", return_value="aaaa"):
            id1 = generate_run_id(ts)
        
        with patch("secrets.token_hex", return_value="bbbb"):
            id2 = generate_run_id(ts)
        
        # Same timestamp but different suffix should produce different IDs
        assert id1 != id2
        assert id1.endswith("_aaaa")
        assert id2.endswith("_bbbb")
    
    def test_get_run_filename_live_copy(self):
        """Test filename for live copy run."""
        result = get_run_filename("20241229_120000_abcd", RunMode.LIVE_COPY)
        
        assert result == "20241229_120000_abcd_apply.json"
    
    def test_get_run_filename_dry_run(self):
        """Test filename for dry run."""
        result = get_run_filename("20241229_120000_abcd", RunMode.DRY_RUN)
        
        assert result == "20241229_120000_abcd_apply_dryrun.json"
    
    def test_get_run_filename_live_move(self):
        """Test filename for live move run."""
        result = get_run_filename("20241229_120000_abcd", RunMode.LIVE_MOVE)
        
        assert result == "20241229_120000_abcd_apply.json"
