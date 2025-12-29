"""Tests for the run_record_writer module."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.config.schema import (
    ChronoCleanConfig,
    SortingConfig,
    RenamingConfig,
    FolderTagsConfig,
    DuplicatesConfig,
    VerifyConfig,
)
from chronoclean.core.run_record import OperationType, RunMode
from chronoclean.core.run_record_writer import (
    RunRecordWriter,
    create_config_signature,
    create_run_record,
    ensure_runs_dir,
    get_runs_dir,
    get_state_dir,
    write_run_record,
)


class TestGetStateDir:
    """Tests for get_state_dir function."""
    
    def test_default_state_dir(self, tmp_path):
        """Test default state directory."""
        verify_config = VerifyConfig(state_dir=str(tmp_path / ".chronoclean"))
        state_dir = get_state_dir(verify_config)
        
        # Returns CWD + state_dir, but we configured absolute path
        # So it's CWD + absolute path (odd but that's the design)
        assert ".chronoclean" in str(state_dir)
    
    def test_custom_state_dir(self, tmp_path):
        """Test custom state directory."""
        custom = tmp_path / "custom_state"
        verify_config = VerifyConfig(state_dir=str(custom))
        state_dir = get_state_dir(verify_config)
        
        assert "custom_state" in str(state_dir)


class TestGetRunsDir:
    """Tests for get_runs_dir function."""
    
    def test_runs_dir_path(self, tmp_path):
        """Test runs directory is under state dir."""
        verify_config = VerifyConfig(state_dir=str(tmp_path / ".chronoclean"))
        runs_dir = get_runs_dir(verify_config)
        
        assert "runs" in str(runs_dir)


class TestEnsureRunsDir:
    """Tests for ensure_runs_dir function."""
    
    def test_creates_runs_directory(self, tmp_path, monkeypatch):
        """Test that runs directory is created."""
        # Change to tmp_path so state_dir resolution works
        monkeypatch.chdir(tmp_path)
        
        verify_config = VerifyConfig(state_dir=".chronoclean")
        runs_dir = ensure_runs_dir(verify_config)
        
        assert runs_dir.exists()
        assert runs_dir.name == "runs"
    
    def test_idempotent_creation(self, tmp_path, monkeypatch):
        """Test that calling multiple times is safe."""
        monkeypatch.chdir(tmp_path)
        
        verify_config = VerifyConfig(state_dir=".chronoclean")
        runs_dir1 = ensure_runs_dir(verify_config)
        runs_dir2 = ensure_runs_dir(verify_config)
        
        assert runs_dir1 == runs_dir2
        assert runs_dir1.exists()


class TestCreateConfigSignature:
    """Tests for create_config_signature function."""
    
    def test_extracts_relevant_config(self):
        """Test that signature extracts relevant config values."""
        config = ChronoCleanConfig(
            sorting=SortingConfig(folder_structure="YYYY/MM"),
            renaming=RenamingConfig(enabled=True, pattern="{date}_{original}"),
            folder_tags=FolderTagsConfig(enabled=True),
            duplicates=DuplicatesConfig(on_collision="check_hash"),
        )
        
        signature = create_config_signature(config)
        
        assert signature.folder_structure == "YYYY/MM"
        assert signature.renaming_enabled is True
        assert signature.renaming_pattern == "{date}_{original}"
        assert signature.folder_tags_enabled is True
        assert signature.on_collision == "check_hash"


class TestCreateRunRecord:
    """Tests for create_run_record function."""
    
    def test_creates_live_copy_record(self, tmp_path):
        """Test creating a live copy run record."""
        config = ChronoCleanConfig()
        
        record = create_run_record(
            source_root=tmp_path / "source",
            destination_root=tmp_path / "dest",
            config=config,
            dry_run=False,
            move_mode=False,
        )
        
        assert record.mode == RunMode.LIVE_COPY
        assert str(tmp_path / "source") in record.source_root
    
    def test_creates_live_move_record(self, tmp_path):
        """Test creating a live move run record."""
        config = ChronoCleanConfig()
        
        record = create_run_record(
            source_root=tmp_path / "source",
            destination_root=tmp_path / "dest",
            config=config,
            dry_run=False,
            move_mode=True,
        )
        
        assert record.mode == RunMode.LIVE_MOVE
    
    def test_creates_dry_run_record(self, tmp_path):
        """Test creating a dry run record."""
        config = ChronoCleanConfig()
        
        record = create_run_record(
            source_root=tmp_path / "source",
            destination_root=tmp_path / "dest",
            config=config,
            dry_run=True,
            move_mode=False,
        )
        
        assert record.mode == RunMode.DRY_RUN
    
    def test_run_id_format(self, tmp_path):
        """Test run_id format includes timestamp."""
        config = ChronoCleanConfig()
        ts = datetime(2024, 12, 29, 12, 0, 0)
        
        record = create_run_record(
            source_root=tmp_path / "source",
            destination_root=tmp_path / "dest",
            config=config,
            dry_run=False,
            move_mode=False,
            timestamp=ts,
        )
        
        assert "20241229" in record.run_id
        assert "120000" in record.run_id


class TestWriteRunRecord:
    """Tests for write_run_record function."""
    
    def test_writes_json_file(self, tmp_path, monkeypatch):
        """Test that run record is written as JSON."""
        monkeypatch.chdir(tmp_path)
        
        config = ChronoCleanConfig()
        verify_config = VerifyConfig(state_dir=".chronoclean")
        
        record = create_run_record(
            source_root=tmp_path / "source",
            destination_root=tmp_path / "dest",
            config=config,
            dry_run=False,
            move_mode=False,
        )
        
        filepath = write_run_record(record, verify_config)
        
        assert filepath.exists()
        assert filepath.suffix == ".json"
        
        # Verify JSON is valid
        data = json.loads(filepath.read_text())
        assert data["run_id"] == record.run_id


class TestRunRecordWriter:
    """Tests for RunRecordWriter context manager."""
    
    def test_context_manager_creates_file(self, tmp_path, monkeypatch):
        """Test that context manager creates run record file on exit."""
        monkeypatch.chdir(tmp_path)
        
        config = ChronoCleanConfig(
            verify=VerifyConfig(state_dir=".chronoclean"),
        )
        source_root = tmp_path / "source"
        dest_root = tmp_path / "dest"
        source_root.mkdir()
        dest_root.mkdir()
        
        with RunRecordWriter(
            source_root=source_root,
            destination_root=dest_root,
            config=config,
            dry_run=False,
            move_mode=False,
        ) as writer:
            writer.add_copy(
                source_root / "test.jpg",
                dest_root / "test.jpg",
            )
        
        runs_dir = tmp_path / ".chronoclean" / "runs"
        assert runs_dir.exists()
        
        run_files = list(runs_dir.glob("*.json"))
        assert len(run_files) == 1
    
    def test_disabled_writer_no_file(self, tmp_path, monkeypatch):
        """Test that disabled writer doesn't create file."""
        monkeypatch.chdir(tmp_path)
        
        config = ChronoCleanConfig(
            verify=VerifyConfig(state_dir=".chronoclean"),
        )
        source_root = tmp_path / "source"
        dest_root = tmp_path / "dest"
        source_root.mkdir()
        dest_root.mkdir()
        
        with RunRecordWriter(
            source_root=source_root,
            destination_root=dest_root,
            config=config,
            dry_run=False,
            move_mode=False,
            enabled=False,
        ) as writer:
            writer.add_copy(
                source_root / "test.jpg",
                dest_root / "test.jpg",
            )
        
        runs_dir = tmp_path / ".chronoclean" / "runs"
        if runs_dir.exists():
            assert len(list(runs_dir.glob("*.json"))) == 0
    
    def test_run_record_content(self, tmp_path, monkeypatch):
        """Test the content of the run record."""
        monkeypatch.chdir(tmp_path)
        
        config = ChronoCleanConfig(
            verify=VerifyConfig(state_dir=".chronoclean"),
        )
        source_root = tmp_path / "source"
        dest_root = tmp_path / "dest"
        source_root.mkdir()
        dest_root.mkdir()
        
        with RunRecordWriter(
            source_root=source_root,
            destination_root=dest_root,
            config=config,
            dry_run=False,
            move_mode=False,
        ) as writer:
            writer.add_copy(
                source_root / "photo.jpg",
                dest_root / "2024" / "photo.jpg",
            )
            writer.add_copy(
                source_root / "video.mp4",
                dest_root / "2024" / "video.mp4",
            )
        
        runs_dir = tmp_path / ".chronoclean" / "runs"
        run_file = list(runs_dir.glob("*.json"))[0]
        
        data = json.loads(run_file.read_text())
        
        assert "run_id" in data
        assert "created_at" in data
        assert data["mode"] == "live_copy"
        assert len(data["entries"]) == 2


class TestRunRecordWriterModes:
    """Tests for different run modes."""
    
    def test_dry_run_mode(self, tmp_path, monkeypatch):
        """Test dry run mode is recorded."""
        monkeypatch.chdir(tmp_path)
        
        config = ChronoCleanConfig(
            verify=VerifyConfig(state_dir=".chronoclean"),
        )
        source_root = tmp_path / "source"
        dest_root = tmp_path / "dest"
        source_root.mkdir()
        dest_root.mkdir()
        
        with RunRecordWriter(
            source_root=source_root,
            destination_root=dest_root,
            config=config,
            dry_run=True,
            move_mode=False,
        ) as writer:
            pass
        
        runs_dir = tmp_path / ".chronoclean" / "runs"
        data = json.loads(list(runs_dir.glob("*.json"))[0].read_text())
        
        assert data["mode"] == "dry_run"
