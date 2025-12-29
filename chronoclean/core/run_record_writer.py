"""Run record writer for ChronoClean v0.3.1.

Handles writing apply run records to the .chronoclean/runs/ directory.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from chronoclean.config.schema import ChronoCleanConfig, VerifyConfig
from chronoclean.core.run_record import (
    ApplyRunRecord,
    ConfigSignature,
    OperationType,
    RunMode,
    generate_run_id,
    get_run_filename,
)

logger = logging.getLogger(__name__)


def get_state_dir(verify_config: VerifyConfig) -> Path:
    """Get the state directory path (resolved from CWD).
    
    Args:
        verify_config: Verify configuration.
        
    Returns:
        Absolute path to state directory.
    """
    return Path.cwd() / verify_config.state_dir


def get_runs_dir(verify_config: VerifyConfig) -> Path:
    """Get the runs directory path.
    
    Args:
        verify_config: Verify configuration.
        
    Returns:
        Absolute path to runs directory.
    """
    return get_state_dir(verify_config) / verify_config.run_record_dir


def get_verifications_dir(verify_config: VerifyConfig) -> Path:
    """Get the verifications directory path.
    
    Args:
        verify_config: Verify configuration.
        
    Returns:
        Absolute path to verifications directory.
    """
    return get_state_dir(verify_config) / verify_config.verification_dir


def ensure_runs_dir(verify_config: VerifyConfig) -> Path:
    """Ensure the runs directory exists.
    
    Args:
        verify_config: Verify configuration.
        
    Returns:
        Path to runs directory.
    """
    runs_dir = get_runs_dir(verify_config)
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


def ensure_verifications_dir(verify_config: VerifyConfig) -> Path:
    """Ensure the verifications directory exists.
    
    Args:
        verify_config: Verify configuration.
        
    Returns:
        Path to verifications directory.
    """
    verifications_dir = get_verifications_dir(verify_config)
    verifications_dir.mkdir(parents=True, exist_ok=True)
    return verifications_dir


def create_config_signature(config: ChronoCleanConfig) -> ConfigSignature:
    """Extract config signature from full config.
    
    Captures the config values that affect file mapping.
    
    Args:
        config: Full ChronoClean configuration.
        
    Returns:
        ConfigSignature with relevant values.
    """
    return ConfigSignature(
        folder_structure=config.sorting.folder_structure,
        renaming_enabled=config.renaming.enabled,
        renaming_pattern=config.renaming.pattern,
        folder_tags_enabled=config.folder_tags.enabled,
        on_collision=config.duplicates.on_collision,
    )


def create_run_record(
    source_root: Path,
    destination_root: Path,
    config: ChronoCleanConfig,
    dry_run: bool,
    move_mode: bool,
    timestamp: Optional[datetime] = None,
) -> ApplyRunRecord:
    """Create a new apply run record.
    
    Args:
        source_root: Source directory path.
        destination_root: Destination directory path.
        config: ChronoClean configuration.
        dry_run: Whether this is a dry run.
        move_mode: Whether move mode is enabled (vs copy).
        timestamp: Optional timestamp for run ID.
        
    Returns:
        New ApplyRunRecord ready for entries.
    """
    ts = timestamp or datetime.now()
    run_id = generate_run_id(ts)
    
    if dry_run:
        mode = RunMode.DRY_RUN
    elif move_mode:
        mode = RunMode.LIVE_MOVE
    else:
        mode = RunMode.LIVE_COPY
    
    return ApplyRunRecord(
        run_id=run_id,
        created_at=ts,
        source_root=str(source_root.resolve()),
        destination_root=str(destination_root.resolve()),
        mode=mode,
        config_signature=create_config_signature(config),
    )


def write_run_record(
    run_record: ApplyRunRecord,
    verify_config: VerifyConfig,
) -> Path:
    """Write a run record to disk.
    
    Args:
        run_record: The run record to write.
        verify_config: Verify configuration.
        
    Returns:
        Path to the written file.
    """
    runs_dir = ensure_runs_dir(verify_config)
    filename = get_run_filename(run_record.run_id, run_record.mode)
    filepath = runs_dir / filename
    
    json_content = run_record.to_json(pretty=True)
    filepath.write_text(json_content, encoding="utf-8")
    
    logger.info(f"Run record written to: {filepath}")
    return filepath


def load_run_record(filepath: Path) -> ApplyRunRecord:
    """Load a run record from disk.
    
    Args:
        filepath: Path to the run record file.
        
    Returns:
        Loaded ApplyRunRecord.
        
    Raises:
        FileNotFoundError: If file doesn't exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    content = filepath.read_text(encoding="utf-8")
    return ApplyRunRecord.from_json(content)


class RunRecordWriter:
    """Context manager for writing run records during apply.
    
    Usage:
        with RunRecordWriter(source, dest, config, dry_run, move) as writer:
            writer.add_copy(source_path, dest_path)
            writer.add_skip(source_path, reason)
        # Record is automatically written on exit
    """
    
    def __init__(
        self,
        source_root: Path,
        destination_root: Path,
        config: ChronoCleanConfig,
        dry_run: bool,
        move_mode: bool,
        enabled: bool = True,
    ):
        """Initialize the writer.
        
        Args:
            source_root: Source directory path.
            destination_root: Destination directory path.
            config: ChronoClean configuration.
            dry_run: Whether this is a dry run.
            move_mode: Whether move mode is enabled.
            enabled: Whether to actually write the record.
        """
        self.config = config
        self.enabled = enabled
        self.start_time = datetime.now()
        
        self.run_record = create_run_record(
            source_root=source_root,
            destination_root=destination_root,
            config=config,
            dry_run=dry_run,
            move_mode=move_mode,
            timestamp=self.start_time,
        )
        
        self.output_path: Optional[Path] = None
    
    def __enter__(self) -> "RunRecordWriter":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Write the record on exit (unless disabled or exception occurred)."""
        if exc_type is not None:
            # Don't write on exception
            logger.debug("Run record not written due to exception")
            return
        
        if not self.enabled:
            logger.debug("Run record writing disabled")
            return
        
        # Calculate duration
        end_time = datetime.now()
        self.run_record.duration_seconds = (end_time - self.start_time).total_seconds()
        
        self.output_path = write_run_record(
            self.run_record,
            self.config.verify,
        )
    
    def add_copy(
        self,
        source: Path,
        destination: Path,
        reason: Optional[str] = None,
    ) -> None:
        """Record a copy operation."""
        self.run_record.add_entry(source, destination, OperationType.COPY, reason)
    
    def add_move(
        self,
        source: Path,
        destination: Path,
        reason: Optional[str] = None,
    ) -> None:
        """Record a move operation."""
        self.run_record.add_entry(source, destination, OperationType.MOVE, reason)
    
    def add_skip(
        self,
        source: Path,
        reason: str,
    ) -> None:
        """Record a skipped file."""
        self.run_record.add_entry(source, None, OperationType.SKIP, reason)
    
    def add_error(self) -> None:
        """Increment error count."""
        self.run_record.error_files += 1
