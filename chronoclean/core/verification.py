"""Verification models for ChronoClean v0.3.1.

Defines the Verification Report schema for tracking verification results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from chronoclean.utils.json_utils import JsonSerializable


class VerificationStatus(Enum):
    """Status of a verification entry."""
    
    OK = "ok"  # Hash match at expected path
    OK_EXISTING_DUPLICATE = "ok_existing_duplicate"  # Hash match found via content search
    MISMATCH = "mismatch"  # Hash does not match
    MISSING_DESTINATION = "missing_destination"  # Destination file not found
    MISSING_SOURCE = "missing_source"  # Source file no longer exists (e.g., after move)
    ERROR = "error"  # Error during verification (permission, I/O, etc.)
    SKIPPED = "skipped"  # Entry was skipped (e.g., quick mode not eligible)


class MatchType(Enum):
    """How the destination was matched."""
    
    EXPECTED_PATH = "expected_path"  # Matched at the expected destination path
    CONTENT_SEARCH = "content_search"  # Found via content hash search
    UNKNOWN = "unknown"  # Match type not determined


class InputSource(Enum):
    """Source of the verification mapping."""
    
    RUN_RECORD = "run_record"  # From an apply run record
    RECONSTRUCTED = "reconstructed"  # Reconstructed from rules


@dataclass
class VerifyEntry:
    """A single entry in the verification report.
    
    Represents the verification result for one file.
    """
    
    source_path: str  # Absolute path as string
    expected_destination_path: Optional[str]  # Original expected destination
    actual_destination_path: Optional[str]  # Actual verified destination (may differ for content search)
    status: VerificationStatus
    match_type: MatchType = MatchType.UNKNOWN
    hash_algorithm: str = "sha256"
    source_hash: Optional[str] = None
    destination_hash: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_path": self.source_path,
            "expected_destination_path": self.expected_destination_path,
            "actual_destination_path": self.actual_destination_path,
            "status": self.status.value,
            "match_type": self.match_type.value,
            "hash_algorithm": self.hash_algorithm,
            "source_hash": self.source_hash,
            "destination_hash": self.destination_hash,
            "error": self.error,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerifyEntry":
        """Create from dictionary."""
        return cls(
            source_path=data["source_path"],
            expected_destination_path=data.get("expected_destination_path"),
            actual_destination_path=data.get("actual_destination_path"),
            status=VerificationStatus(data["status"]),
            match_type=MatchType(data.get("match_type", "unknown")),
            hash_algorithm=data.get("hash_algorithm", "sha256"),
            source_hash=data.get("source_hash"),
            destination_hash=data.get("destination_hash"),
            error=data.get("error"),
        )
    
    @property
    def is_cleanup_eligible(self) -> bool:
        """Check if this entry is eligible for cleanup.
        
        Only OK and OK_EXISTING_DUPLICATE statuses with sha256 are eligible.
        """
        return (
            self.status in (VerificationStatus.OK, VerificationStatus.OK_EXISTING_DUPLICATE)
            and self.hash_algorithm == "sha256"
        )


@dataclass
class VerificationSummary:
    """Summary counts for a verification report."""
    
    total: int = 0
    ok: int = 0
    ok_existing_duplicate: int = 0
    mismatch: int = 0
    missing_destination: int = 0
    missing_source: int = 0
    error: int = 0
    skipped: int = 0
    
    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "ok": self.ok,
            "ok_existing_duplicate": self.ok_existing_duplicate,
            "mismatch": self.mismatch,
            "missing_destination": self.missing_destination,
            "missing_source": self.missing_source,
            "error": self.error,
            "skipped": self.skipped,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "VerificationSummary":
        """Create from dictionary."""
        return cls(
            total=data.get("total", 0),
            ok=data.get("ok", 0),
            ok_existing_duplicate=data.get("ok_existing_duplicate", 0),
            mismatch=data.get("mismatch", 0),
            missing_destination=data.get("missing_destination", 0),
            missing_source=data.get("missing_source", 0),
            error=data.get("error", 0),
            skipped=data.get("skipped", 0),
        )
    
    @property
    def cleanup_eligible_count(self) -> int:
        """Count of entries eligible for cleanup."""
        return self.ok + self.ok_existing_duplicate


@dataclass
class VerificationReport(JsonSerializable):
    """Complete verification report.
    
    Contains all verification results for a set of files.
    """
    
    verify_id: str
    created_at: datetime
    source_root: str  # Absolute path as string
    destination_root: str  # Absolute path as string
    input_source: InputSource
    run_id: Optional[str]  # When input_source is RUN_RECORD
    hash_algorithm: str = "sha256"
    entries: list[VerifyEntry] = field(default_factory=list)
    summary: VerificationSummary = field(default_factory=VerificationSummary)
    duration_seconds: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "verify_id": self.verify_id,
            "created_at": self.created_at.isoformat(),
            "source_root": self.source_root,
            "destination_root": self.destination_root,
            "input_source": self.input_source.value,
            "run_id": self.run_id,
            "hash_algorithm": self.hash_algorithm,
            "entries": [e.to_dict() for e in self.entries],
            "summary": self.summary.to_dict(),
            "duration_seconds": self.duration_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerificationReport":
        """Create from dictionary."""
        return cls(
            verify_id=data["verify_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            source_root=data["source_root"],
            destination_root=data["destination_root"],
            input_source=InputSource(data["input_source"]),
            run_id=data.get("run_id"),
            hash_algorithm=data.get("hash_algorithm", "sha256"),
            entries=[VerifyEntry.from_dict(e) for e in data.get("entries", [])],
            summary=VerificationSummary.from_dict(data.get("summary", {})),
            duration_seconds=data.get("duration_seconds", 0.0),
        )
    
    def add_entry(self, entry: VerifyEntry) -> None:
        """Add an entry and update summary counts."""
        self.entries.append(entry)
        self.summary.total += 1
        
        # Update status-specific counts
        if entry.status == VerificationStatus.OK:
            self.summary.ok += 1
        elif entry.status == VerificationStatus.OK_EXISTING_DUPLICATE:
            self.summary.ok_existing_duplicate += 1
        elif entry.status == VerificationStatus.MISMATCH:
            self.summary.mismatch += 1
        elif entry.status == VerificationStatus.MISSING_DESTINATION:
            self.summary.missing_destination += 1
        elif entry.status == VerificationStatus.MISSING_SOURCE:
            self.summary.missing_source += 1
        elif entry.status == VerificationStatus.ERROR:
            self.summary.error += 1
        elif entry.status == VerificationStatus.SKIPPED:
            self.summary.skipped += 1
    
    @property
    def cleanup_eligible_entries(self) -> list[VerifyEntry]:
        """Get entries eligible for cleanup."""
        return [e for e in self.entries if e.is_cleanup_eligible]
    
    @property
    def ok_entries(self) -> list[VerifyEntry]:
        """Get all OK entries (both ok and ok_existing_duplicate)."""
        return [
            e for e in self.entries
            if e.status in (VerificationStatus.OK, VerificationStatus.OK_EXISTING_DUPLICATE)
        ]


def generate_verify_id(timestamp: Optional[datetime] = None) -> str:
    """Generate a verification ID from timestamp with random suffix.
    
    Format: YYYYMMDD_HHMMSS_<4-char-hex>
    The suffix prevents collisions when multiple verifications happen in the same second.
    """
    import secrets
    ts = timestamp or datetime.now()
    suffix = secrets.token_hex(2)  # 4 hex chars
    return f"{ts.strftime('%Y%m%d_%H%M%S')}_{suffix}"


def get_verification_filename(verify_id: str) -> str:
    """Generate the filename for a verification report.
    
    Format: {verify_id}_verify.json
    """
    return f"{verify_id}_verify.json"
