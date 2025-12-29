"""Tests for the run_discovery module."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.config.schema import VerifyConfig
from chronoclean.core.run_discovery import (
    RunSummary,
    VerificationSummary,
    discover_run_records,
    discover_verification_reports,
    find_run_by_id,
    find_verification_by_id,
    load_run_record,
    load_verification_report,
)
from chronoclean.core.run_record import RunMode


class TestRunSummary:
    """Tests for RunSummary dataclass."""
    
    def test_age_description_days(self):
        """Test age_description for days."""
        summary = RunSummary(
            run_id="test",
            filepath=Path("/runs/test.json"),
            created_at=datetime(2020, 1, 1, 12, 0, 0),  # Old date
            source_root="/source",
            destination_root="/dest",
            mode=RunMode.LIVE_COPY,
            total_files=10,
            is_dry_run=False,
        )
        
        assert "day" in summary.age_description
    
    def test_mode_description_copy(self):
        """Test mode_description for copy."""
        summary = RunSummary(
            run_id="test",
            filepath=Path("/runs/test.json"),
            created_at=datetime.now(),
            source_root="/source",
            destination_root="/dest",
            mode=RunMode.LIVE_COPY,
            total_files=10,
            is_dry_run=False,
        )
        
        assert summary.mode_description == "copy"
    
    def test_mode_description_move(self):
        """Test mode_description for move."""
        summary = RunSummary(
            run_id="test",
            filepath=Path("/runs/test.json"),
            created_at=datetime.now(),
            source_root="/source",
            destination_root="/dest",
            mode=RunMode.LIVE_MOVE,
            total_files=5,
            is_dry_run=False,
        )
        
        assert summary.mode_description == "move"
    
    def test_mode_description_dry_run(self):
        """Test mode_description for dry-run."""
        summary = RunSummary(
            run_id="test",
            filepath=Path("/runs/test.json"),
            created_at=datetime.now(),
            source_root="/source",
            destination_root="/dest",
            mode=RunMode.DRY_RUN,
            total_files=15,
            is_dry_run=True,
        )
        
        assert summary.mode_description == "dry-run"


class TestVerificationSummary:
    """Tests for VerificationSummary dataclass."""
    
    def test_cleanup_eligible_count(self):
        """Test cleanup_eligible_count calculation."""
        summary = VerificationSummary(
            verify_id="verify_test",
            filepath=Path("/verifications/test.json"),
            created_at=datetime.now(),
            source_root="/source",
            destination_root="/dest",
            ok_count=10,
            ok_duplicate_count=3,
            mismatch_count=2,
            missing_count=1,
            total=16,
        )
        
        assert summary.cleanup_eligible_count == 13  # 10 + 3


class TestDiscoverRunRecords:
    """Tests for discover_run_records function."""
    
    @pytest.fixture
    def verify_config(self, tmp_path) -> VerifyConfig:
        """Create verify config with temp state_dir."""
        return VerifyConfig(
            state_dir=str(tmp_path / ".chronoclean"),
        )
    
    @pytest.fixture
    def runs_dir(self, verify_config, tmp_path):
        """Create runs directory structure."""
        runs = Path(verify_config.state_dir) / verify_config.run_record_dir
        runs.mkdir(parents=True)
        return runs
    
    def test_discover_empty_directory(self, verify_config, runs_dir):
        """Test discovery with no run records."""
        records = discover_run_records(verify_config)
        assert records == []
    
    def test_discover_finds_records(self, verify_config, runs_dir, tmp_path):
        """Test discovery finds run records."""
        record_data = {
            "run_id": "20241229_120000",
            "created_at": "2024-12-29T12:00:00",
            "source_root": str(tmp_path / "source"),
            "destination_root": str(tmp_path / "dest"),
            "mode": "live_copy",
            "config_signature": {
                "folder_structure": "YYYY/MM",
                "renaming_enabled": False,
                "renaming_pattern": "{date}",
                "folder_tags_enabled": False,
                "on_collision": "check_hash",
            },
            "entries": [],
            "summary": {"total_files": 5},
        }
        
        record_file = runs_dir / "20241229_120000_apply.json"
        record_file.write_text(json.dumps(record_data))
        
        records = discover_run_records(verify_config)
        
        assert len(records) == 1
        assert records[0].run_id == "20241229_120000"
        assert records[0].mode == RunMode.LIVE_COPY
    
    def test_discover_orders_by_date_descending(self, verify_config, runs_dir, tmp_path):
        """Test that records are ordered by date, newest first."""
        for run_id, timestamp in [
            ("20241225_100000", "2024-12-25T10:00:00"),
            ("20241229_120000", "2024-12-29T12:00:00"),  # Newest
            ("20241227_150000", "2024-12-27T15:00:00"),
        ]:
            record_data = {
                "run_id": run_id,
                "created_at": timestamp,
                "source_root": "/source",
                "destination_root": "/dest",
                "mode": "live_copy",
                "config_signature": {},
                "entries": [],
            }
            (runs_dir / f"{run_id}_apply.json").write_text(json.dumps(record_data))
        
        records = discover_run_records(verify_config)
        
        assert len(records) == 3
        assert records[0].run_id == "20241229_120000"  # Newest first
        assert records[1].run_id == "20241227_150000"
        assert records[2].run_id == "20241225_100000"  # Oldest last
    
    def test_discover_respects_limit(self, verify_config, runs_dir, tmp_path):
        """Test that limit parameter works."""
        for i in range(5):
            record_data = {
                "run_id": f"run_{i:02d}",
                "created_at": f"2024-12-{20 + i:02d}T12:00:00",
                "source_root": "/source",
                "destination_root": "/dest",
                "mode": "live_copy",
                "config_signature": {},
                "entries": [],
            }
            (runs_dir / f"run_{i:02d}_apply.json").write_text(json.dumps(record_data))
        
        records = discover_run_records(verify_config, limit=2)
        
        assert len(records) == 2
    
    def test_discover_ignores_invalid_json(self, verify_config, runs_dir):
        """Test that invalid JSON files are skipped."""
        (runs_dir / "invalid_apply.json").write_text("not valid json")
        (runs_dir / "also_invalid_apply.json").write_text('{"partial":')
        
        records = discover_run_records(verify_config)
        
        assert records == []
    
    def test_discover_excludes_dry_runs_by_default(self, verify_config, runs_dir):
        """Test that dry runs are excluded by default."""
        for run_id, mode in [("live_run", "live_copy"), ("dry_run", "dry_run")]:
            record_data = {
                "run_id": run_id,
                "created_at": "2024-12-29T12:00:00",
                "source_root": "/source",
                "destination_root": "/dest",
                "mode": mode,
                "config_signature": {},
                "entries": [],
            }
            (runs_dir / f"{run_id}_apply.json").write_text(json.dumps(record_data))
        
        records = discover_run_records(verify_config, include_dry_runs=False)
        
        assert len(records) == 1
        assert records[0].run_id == "live_run"
    
    def test_discover_includes_dry_runs_when_requested(self, verify_config, runs_dir):
        """Test that dry runs can be included."""
        for run_id, mode in [("live_run", "live_copy"), ("dry_run", "dry_run")]:
            record_data = {
                "run_id": run_id,
                "created_at": "2024-12-29T12:00:00",
                "source_root": "/source",
                "destination_root": "/dest",
                "mode": mode,
                "config_signature": {},
                "entries": [],
            }
            (runs_dir / f"{run_id}_apply.json").write_text(json.dumps(record_data))
        
        records = discover_run_records(verify_config, include_dry_runs=True)
        
        assert len(records) == 2


class TestDiscoverVerificationReports:
    """Tests for discover_verification_reports function."""
    
    @pytest.fixture
    def verify_config(self, tmp_path) -> VerifyConfig:
        """Create verify config with temp state_dir."""
        return VerifyConfig(
            state_dir=str(tmp_path / ".chronoclean"),
        )
    
    @pytest.fixture
    def verifications_dir(self, verify_config, tmp_path):
        """Create verifications directory structure."""
        verifications = Path(verify_config.state_dir) / verify_config.verification_dir
        verifications.mkdir(parents=True)
        return verifications
    
    def test_discover_empty_directory(self, verify_config, verifications_dir):
        """Test discovery with no verification reports."""
        reports = discover_verification_reports(verify_config)
        assert reports == []
    
    def test_discover_finds_reports(self, verify_config, verifications_dir, tmp_path):
        """Test discovery finds verification reports."""
        report_data = {
            "verify_id": "verify_20241229_130000",
            "created_at": "2024-12-29T13:00:00",
            "run_id": "20241229_120000",
            "source_root": str(tmp_path / "source"),
            "destination_root": str(tmp_path / "dest"),
            "input_source": "run_record",
            "summary": {
                "total": 10,
                "ok": 8,
                "mismatch": 1,
                "missing_source": 0,
                "missing_destination": 1,
                "error": 0,
                "skipped": 0,
                "ok_existing_duplicate": 0,
            },
            "entries": [],
        }
        
        report_file = verifications_dir / "verify_20241229_130000_verify.json"
        report_file.write_text(json.dumps(report_data))
        
        reports = discover_verification_reports(verify_config)
        
        assert len(reports) == 1
        assert reports[0].verify_id == "verify_20241229_130000"
        assert reports[0].ok_count == 8


class TestFindByID:
    """Tests for find_run_by_id and find_verification_by_id functions."""
    
    @pytest.fixture
    def verify_config(self, tmp_path) -> VerifyConfig:
        """Create verify config with temp state_dir."""
        return VerifyConfig(
            state_dir=str(tmp_path / ".chronoclean"),
        )
    
    @pytest.fixture
    def runs_dir(self, verify_config, tmp_path):
        """Create runs directory with sample data."""
        runs = Path(verify_config.state_dir) / verify_config.run_record_dir
        runs.mkdir(parents=True)
        
        record_data = {
            "run_id": "20241229_120000",
            "created_at": "2024-12-29T12:00:00",
            "source_root": str(tmp_path / "source"),
            "destination_root": str(tmp_path / "dest"),
            "mode": "live_copy",
            "config_signature": {
                "folder_structure": "YYYY/MM",
                "renaming_enabled": False,
                "renaming_pattern": "{date}",
                "folder_tags_enabled": False,
                "on_collision": "check_hash",
            },
            "entries": [],
        }
        (runs / "20241229_120000_apply.json").write_text(json.dumps(record_data))
        return runs
    
    @pytest.fixture
    def verifications_dir(self, verify_config, tmp_path):
        """Create verifications directory with sample data."""
        verifications = Path(verify_config.state_dir) / verify_config.verification_dir
        verifications.mkdir(parents=True)
        
        report_data = {
            "verify_id": "verify_20241229_130000",
            "created_at": "2024-12-29T13:00:00",
            "run_id": "20241229_120000",
            "source_root": str(tmp_path / "source"),
            "destination_root": str(tmp_path / "dest"),
            "input_source": "run_record",
            "summary": {
                "total": 5,
                "ok": 5,
                "mismatch": 0,
                "missing_source": 0,
                "missing_destination": 0,
                "error": 0,
                "skipped": 0,
                "ok_existing_duplicate": 0,
            },
            "entries": [],
        }
        (verifications / "verify_20241229_130000_verify.json").write_text(json.dumps(report_data))
        return verifications
    
    def test_find_run_by_full_id(self, verify_config, runs_dir):
        """Test finding run by full ID."""
        filepath = find_run_by_id(verify_config, "20241229_120000")
        
        assert filepath is not None
        assert filepath.exists()
    
    def test_find_run_not_found(self, verify_config, runs_dir):
        """Test that missing run returns None."""
        filepath = find_run_by_id(verify_config, "nonexistent")
        
        assert filepath is None
    
    def test_find_verification_by_full_id(self, verify_config, verifications_dir):
        """Test finding verification by full ID."""
        filepath = find_verification_by_id(verify_config, "verify_20241229_130000")
        
        assert filepath is not None
        assert filepath.exists()
    
    def test_find_verification_not_found(self, verify_config, verifications_dir):
        """Test that missing verification returns None."""
        filepath = find_verification_by_id(verify_config, "nonexistent")
        
        assert filepath is None


class TestLoadFunctions:
    """Tests for load_run_record and load_verification_report."""
    
    def test_load_run_record(self, tmp_path):
        """Test loading a run record from file."""
        record_data = {
            "run_id": "test_run",
            "created_at": "2024-12-29T12:00:00",
            "source_root": str(tmp_path / "source"),
            "destination_root": str(tmp_path / "dest"),
            "mode": "live_copy",
            "config_signature": {
                "folder_structure": "YYYY/MM",
                "renaming_enabled": False,
                "renaming_pattern": "{date}",
                "folder_tags_enabled": False,
                "on_collision": "check_hash",
            },
            "entries": [],
        }
        
        filepath = tmp_path / "test_run_apply.json"
        filepath.write_text(json.dumps(record_data))
        
        record = load_run_record(filepath)
        
        assert record.run_id == "test_run"
        assert record.mode == RunMode.LIVE_COPY
    
    def test_load_verification_report(self, tmp_path):
        """Test loading a verification report from file."""
        report_data = {
            "verify_id": "test_verify",
            "created_at": "2024-12-29T13:00:00",
            "source_root": str(tmp_path / "source"),
            "destination_root": str(tmp_path / "dest"),
            "input_source": "run_record",
            "hash_algorithm": "sha256",
            "summary": {
                "total": 5,
                "ok": 5,
                "mismatch": 0,
                "missing_source": 0,
                "missing_destination": 0,
                "error": 0,
                "skipped": 0,
                "ok_existing_duplicate": 0,
            },
            "entries": [],
        }
        
        filepath = tmp_path / "test_verify.json"
        filepath.write_text(json.dumps(report_data))
        
        report = load_verification_report(filepath)
        
        assert report.verify_id == "test_verify"
