"""Run record models for ChronoClean v0.3.1.

Defines the Apply Run Record schema for tracking copy/move operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import json


class RunMode(Enum):
    """Mode of the apply run."""
    
    DRY_RUN = "dry_run"
    LIVE_COPY = "live_copy"
    LIVE_MOVE = "live_move"


class OperationType(Enum):
    """Type of operation performed on a file."""
    
    COPY = "copy"
    MOVE = "move"
    SKIP = "skip"


@dataclass
class RunEntry:
    """A single entry in the apply run record.
    
    Represents one file operation (copy, move, or skip).
    """
    
    source_path: str  # Absolute path as string for JSON serialization
    destination_path: Optional[str]  # Nullable for skipped files
    operation: OperationType
    reason: Optional[str] = None  # Reason for skip, or rename reason
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_path": self.source_path,
            "destination_path": self.destination_path,
            "operation": self.operation.value,
            "reason": self.reason,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunEntry":
        """Create from dictionary."""
        return cls(
            source_path=data["source_path"],
            destination_path=data.get("destination_path"),
            operation=OperationType(data["operation"]),
            reason=data.get("reason"),
        )


@dataclass
class ConfigSignature:
    """Subset of config values affecting file mapping.
    
    Stored in the run record to help identify compatible runs.
    """
    
    folder_structure: str
    renaming_enabled: bool
    renaming_pattern: str
    folder_tags_enabled: bool
    on_collision: str
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "folder_structure": self.folder_structure,
            "renaming_enabled": self.renaming_enabled,
            "renaming_pattern": self.renaming_pattern,
            "folder_tags_enabled": self.folder_tags_enabled,
            "on_collision": self.on_collision,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfigSignature":
        """Create from dictionary."""
        return cls(
            folder_structure=data["folder_structure"],
            renaming_enabled=data["renaming_enabled"],
            renaming_pattern=data["renaming_pattern"],
            folder_tags_enabled=data["folder_tags_enabled"],
            on_collision=data["on_collision"],
        )


@dataclass
class ApplyRunRecord:
    """Complete record of an apply run.
    
    Contains all file operations performed during a single apply command.
    """
    
    run_id: str
    created_at: datetime
    source_root: str  # Absolute path as string
    destination_root: str  # Absolute path as string
    mode: RunMode
    config_signature: ConfigSignature
    entries: list[RunEntry] = field(default_factory=list)
    
    # Summary statistics
    total_files: int = 0
    copied_files: int = 0
    moved_files: int = 0
    skipped_files: int = 0
    error_files: int = 0
    duration_seconds: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "source_root": self.source_root,
            "destination_root": self.destination_root,
            "mode": self.mode.value,
            "config_signature": self.config_signature.to_dict(),
            "entries": [e.to_dict() for e in self.entries],
            "summary": {
                "total_files": self.total_files,
                "copied_files": self.copied_files,
                "moved_files": self.moved_files,
                "skipped_files": self.skipped_files,
                "error_files": self.error_files,
                "duration_seconds": self.duration_seconds,
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApplyRunRecord":
        """Create from dictionary."""
        summary = data.get("summary", {})
        return cls(
            run_id=data["run_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            source_root=data["source_root"],
            destination_root=data["destination_root"],
            mode=RunMode(data["mode"]),
            config_signature=ConfigSignature.from_dict(data["config_signature"]),
            entries=[RunEntry.from_dict(e) for e in data.get("entries", [])],
            total_files=summary.get("total_files", 0),
            copied_files=summary.get("copied_files", 0),
            moved_files=summary.get("moved_files", 0),
            skipped_files=summary.get("skipped_files", 0),
            error_files=summary.get("error_files", 0),
            duration_seconds=summary.get("duration_seconds", 0.0),
        )
    
    def to_json(self, pretty: bool = True) -> str:
        """Convert to JSON string."""
        return json.dumps(
            self.to_dict(),
            indent=2 if pretty else None,
            ensure_ascii=False,
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "ApplyRunRecord":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def add_entry(
        self,
        source: Path,
        destination: Optional[Path],
        operation: OperationType,
        reason: Optional[str] = None,
    ) -> None:
        """Add an entry to the run record."""
        self.entries.append(
            RunEntry(
                source_path=str(source.resolve()),
                destination_path=str(destination.resolve()) if destination else None,
                operation=operation,
                reason=reason,
            )
        )
        
        # Update summary counts
        if operation == OperationType.COPY:
            self.copied_files += 1
        elif operation == OperationType.MOVE:
            self.moved_files += 1
        elif operation == OperationType.SKIP:
            self.skipped_files += 1
        
        self.total_files += 1
    
    @property
    def copy_entries(self) -> list[RunEntry]:
        """Get all copy operation entries."""
        return [e for e in self.entries if e.operation == OperationType.COPY]
    
    @property
    def move_entries(self) -> list[RunEntry]:
        """Get all move operation entries."""
        return [e for e in self.entries if e.operation == OperationType.MOVE]
    
    @property
    def verifiable_entries(self) -> list[RunEntry]:
        """Get entries that can be verified (copy operations with destinations)."""
        return [
            e for e in self.entries
            if e.operation == OperationType.COPY and e.destination_path is not None
        ]


def generate_run_id(timestamp: Optional[datetime] = None) -> str:
    """Generate a run ID from timestamp with random suffix.
    
    Format: YYYYMMDD_HHMMSS_<4-char-hex>
    The suffix prevents collisions when multiple runs happen in the same second.
    """
    import secrets
    ts = timestamp or datetime.now()
    suffix = secrets.token_hex(2)  # 4 hex chars
    return f"{ts.strftime('%Y%m%d_%H%M%S')}_{suffix}"


def get_run_filename(run_id: str, mode: RunMode) -> str:
    """Generate the filename for a run record.
    
    Format: {run_id}_apply.json or {run_id}_apply_dryrun.json
    """
    if mode == RunMode.DRY_RUN:
        return f"{run_id}_apply_dryrun.json"
    return f"{run_id}_apply.json"
