"""Run discovery for ChronoClean v0.3.1.

Auto-discovers apply run records from .chronoclean/runs/ directory.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from chronoclean.config.schema import VerifyConfig
from chronoclean.core.run_record import ApplyRunRecord, RunMode
from chronoclean.core.run_record_writer import get_runs_dir, get_verifications_dir
from chronoclean.core.verification import VerificationReport

logger = logging.getLogger(__name__)


@dataclass
class RunSummary:
    """Summary of a discovered run record for display."""
    
    run_id: str
    filepath: Path
    created_at: datetime
    source_root: str
    destination_root: str
    mode: RunMode
    total_files: int
    is_dry_run: bool
    
    @property
    def age_description(self) -> str:
        """Human-readable age of the run."""
        delta = datetime.now() - self.created_at
        
        if delta.days > 0:
            return f"{delta.days} day(s) ago"
        
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hour(s) ago"
        
        minutes = delta.seconds // 60
        if minutes > 0:
            return f"{minutes} minute(s) ago"
        
        return "just now"
    
    @property
    def mode_description(self) -> str:
        """Human-readable mode description."""
        if self.mode == RunMode.DRY_RUN:
            return "dry-run"
        elif self.mode == RunMode.LIVE_COPY:
            return "copy"
        elif self.mode == RunMode.LIVE_MOVE:
            return "move"
        return self.mode.value


@dataclass
class VerificationSummary:
    """Summary of a discovered verification report for display."""
    
    verify_id: str
    filepath: Path
    created_at: datetime
    source_root: str
    destination_root: str
    ok_count: int
    ok_duplicate_count: int
    mismatch_count: int
    missing_count: int
    total: int
    
    @property
    def age_description(self) -> str:
        """Human-readable age of the verification."""
        delta = datetime.now() - self.created_at
        
        if delta.days > 0:
            return f"{delta.days} day(s) ago"
        
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours} hour(s) ago"
        
        minutes = delta.seconds // 60
        if minutes > 0:
            return f"{minutes} minute(s) ago"
        
        return "just now"
    
    @property
    def cleanup_eligible_count(self) -> int:
        """Count eligible for cleanup."""
        return self.ok_count + self.ok_duplicate_count


def discover_run_records(
    verify_config: VerifyConfig,
    source_filter: Optional[Path] = None,
    destination_filter: Optional[Path] = None,
    include_dry_runs: bool = False,
    limit: int = 20,
) -> list[RunSummary]:
    """Discover run records from the runs directory.
    
    Args:
        verify_config: Verify configuration.
        source_filter: Only include runs with matching source_root.
        destination_filter: Only include runs with matching destination_root.
        include_dry_runs: Include dry-run records (default: False).
        limit: Maximum number of records to return.
        
    Returns:
        List of RunSummary sorted by created_at descending (newest first).
    """
    runs_dir = get_runs_dir(verify_config)
    
    if not runs_dir.exists():
        return []
    
    summaries = []
    
    for filepath in runs_dir.glob("*_apply*.json"):
        try:
            content = filepath.read_text(encoding="utf-8")
            data = json.loads(content)
            
            mode = RunMode(data.get("mode", "dry_run"))
            is_dry_run = mode == RunMode.DRY_RUN
            
            # Filter dry runs
            if is_dry_run and not include_dry_runs:
                continue
            
            source_root = data.get("source_root", "")
            destination_root = data.get("destination_root", "")
            
            # Apply filters
            if source_filter:
                source_filter_str = str(source_filter.resolve())
                if not source_root.startswith(source_filter_str):
                    continue
            
            if destination_filter:
                dest_filter_str = str(destination_filter.resolve())
                if not destination_root.startswith(dest_filter_str):
                    continue
            
            summary_data = data.get("summary", {})
            
            summary = RunSummary(
                run_id=data.get("run_id", ""),
                filepath=filepath,
                created_at=datetime.fromisoformat(data["created_at"]),
                source_root=source_root,
                destination_root=destination_root,
                mode=mode,
                total_files=summary_data.get("total_files", 0),
                is_dry_run=is_dry_run,
            )
            summaries.append(summary)
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Could not parse run record {filepath}: {e}")
            continue
    
    # Sort by created_at descending (newest first)
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    
    return summaries[:limit]


def discover_verification_reports(
    verify_config: VerifyConfig,
    source_filter: Optional[Path] = None,
    destination_filter: Optional[Path] = None,
    limit: int = 20,
) -> list[VerificationSummary]:
    """Discover verification reports from the verifications directory.
    
    Args:
        verify_config: Verify configuration.
        source_filter: Only include reports with matching source_root.
        destination_filter: Only include reports with matching destination_root.
        limit: Maximum number of reports to return.
        
    Returns:
        List of VerificationSummary sorted by created_at descending (newest first).
    """
    verifications_dir = get_verifications_dir(verify_config)
    
    if not verifications_dir.exists():
        return []
    
    summaries = []
    
    for filepath in verifications_dir.glob("*_verify.json"):
        try:
            content = filepath.read_text(encoding="utf-8")
            data = json.loads(content)
            
            source_root = data.get("source_root", "")
            destination_root = data.get("destination_root", "")
            
            # Apply filters
            if source_filter:
                source_filter_str = str(source_filter.resolve())
                if not source_root.startswith(source_filter_str):
                    continue
            
            if destination_filter:
                dest_filter_str = str(destination_filter.resolve())
                if not destination_root.startswith(dest_filter_str):
                    continue
            
            summary_data = data.get("summary", {})
            
            summary = VerificationSummary(
                verify_id=data.get("verify_id", ""),
                filepath=filepath,
                created_at=datetime.fromisoformat(data["created_at"]),
                source_root=source_root,
                destination_root=destination_root,
                ok_count=summary_data.get("ok", 0),
                ok_duplicate_count=summary_data.get("ok_existing_duplicate", 0),
                mismatch_count=summary_data.get("mismatch", 0),
                missing_count=summary_data.get("missing_destination", 0) + summary_data.get("missing_source", 0),
                total=summary_data.get("total", 0),
            )
            summaries.append(summary)
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Could not parse verification report {filepath}: {e}")
            continue
    
    # Sort by created_at descending (newest first)
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    
    return summaries[:limit]


def load_run_record(filepath: Path) -> ApplyRunRecord:
    """Load a run record from a file.
    
    Args:
        filepath: Path to the run record JSON file.
        
    Returns:
        ApplyRunRecord instance.
        
    Raises:
        FileNotFoundError: If file doesn't exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    content = filepath.read_text(encoding="utf-8")
    return ApplyRunRecord.from_json(content)


def load_verification_report(filepath: Path) -> VerificationReport:
    """Load a verification report from a file.
    
    Args:
        filepath: Path to the verification report JSON file.
        
    Returns:
        VerificationReport instance.
        
    Raises:
        FileNotFoundError: If file doesn't exist.
        json.JSONDecodeError: If file is not valid JSON.
    """
    content = filepath.read_text(encoding="utf-8")
    return VerificationReport.from_json(content)


def find_run_by_id(
    verify_config: VerifyConfig,
    run_id: str,
) -> Optional[Path]:
    """Find a run record by its run_id.
    
    Args:
        verify_config: Verify configuration.
        run_id: The run ID to search for.
        
    Returns:
        Path to the run record file, or None if not found.
    """
    runs_dir = get_runs_dir(verify_config)
    
    if not runs_dir.exists():
        return None
    
    # Try direct filename match first
    for pattern in [f"{run_id}_apply.json", f"{run_id}_apply_dryrun.json"]:
        filepath = runs_dir / pattern
        if filepath.exists():
            return filepath
    
    # Fall back to searching all files
    for filepath in runs_dir.glob("*_apply*.json"):
        try:
            content = filepath.read_text(encoding="utf-8")
            data = json.loads(content)
            if data.get("run_id") == run_id:
                return filepath
        except (json.JSONDecodeError, KeyError):
            continue
    
    return None


def find_verification_by_id(
    verify_config: VerifyConfig,
    verify_id: str,
) -> Optional[Path]:
    """Find a verification report by its verify_id.
    
    Args:
        verify_config: Verify configuration.
        verify_id: The verification ID to search for.
        
    Returns:
        Path to the verification report file, or None if not found.
    """
    verifications_dir = get_verifications_dir(verify_config)
    
    if not verifications_dir.exists():
        return None
    
    # Try direct filename match first
    filepath = verifications_dir / f"{verify_id}_verify.json"
    if filepath.exists():
        return filepath
    
    # Fall back to searching all files
    for filepath in verifications_dir.glob("*_verify.json"):
        try:
            content = filepath.read_text(encoding="utf-8")
            data = json.loads(content)
            if data.get("verify_id") == verify_id:
                return filepath
        except (json.JSONDecodeError, KeyError):
            continue
    
    return None
