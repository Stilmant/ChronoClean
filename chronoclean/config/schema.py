"""Configuration schema definitions for ChronoClean."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GeneralConfig:
    """General configuration settings."""

    timezone: str = "local"
    recursive: bool = True
    include_videos: bool = True
    ignore_hidden_files: bool = True
    dry_run_default: bool = True
    output_folder: str = ".chronoclean"


@dataclass
class PathsConfig:
    """Path configuration settings."""

    source: Optional[Path] = None
    destination: Optional[Path] = None
    temp_folder: Optional[Path] = None


@dataclass
class ScanConfig:
    """Scan-specific configuration settings."""

    image_extensions: list[str] = field(
        default_factory=lambda: [
            ".jpg", ".jpeg", ".png", ".tiff", ".tif",
            ".heic", ".heif", ".webp", ".bmp", ".gif"
        ]
    )
    video_extensions: list[str] = field(
        default_factory=lambda: [
            ".mp4", ".mov", ".avi", ".mkv", ".m4v",
            ".3gp", ".wmv", ".webm"
        ]
    )
    raw_extensions: list[str] = field(
        default_factory=lambda: [
            ".cr2", ".nef", ".arw", ".dng", ".orf", ".rw2"
        ]
    )
    skip_exif_errors: bool = True
    limit: Optional[int] = None


@dataclass
class VideoMetadataConfig:
    """Video metadata extraction configuration (v0.3)."""

    enabled: bool = True
    provider: str = "ffprobe"  # ffprobe, hachoir
    ffprobe_path: str = "ffprobe"  # Path to ffprobe binary
    fallback_to_hachoir: bool = True  # Use hachoir if ffprobe unavailable
    skip_errors: bool = True  # Continue on metadata read failures


@dataclass
class SortingConfig:
    """Sorting configuration settings."""

    folder_structure: str = "YYYY/MM"
    # v0.3: Updated default to include video_metadata and filename
    fallback_date_priority: list[str] = field(
        default_factory=lambda: ["exif", "video_metadata", "filename", "filesystem", "folder_name"]
    )
    include_day: bool = False


@dataclass
class HeuristicConfig:
    """Heuristic date inference settings (deferred from v0.3)."""

    enabled: bool = False  # Deferred: cluster-based date inference disabled by default
    max_days_from_cluster: int = 2  # Deferred: max days offset from cluster median
    min_cluster_size: int = 3  # Deferred: minimum files to form a cluster


@dataclass
class FolderTagsConfig:
    """Folder tag configuration settings."""

    enabled: bool = False
    tag_format: str = "{tag}"
    min_length: int = 3
    max_length: int = 40
    ignore_list: list[str] = field(
        default_factory=lambda: [
            "tosort", "unsorted", "misc", "backup", "temp", "tmp",
            "download", "downloads", "dcim", "camera", "pictures",
            "photos", "images", "100apple", "100andro", "camera roll"
        ]
    )
    force_list: list[str] = field(default_factory=list)
    auto_detect: bool = True
    distance_check: bool = True
    distance_threshold: float = 0.75


@dataclass
class RenamingConfig:
    """File renaming configuration settings."""

    enabled: bool = False
    pattern: str = "{date}_{time}"
    date_format: str = "%Y%m%d"
    time_format: str = "%H%M%S"
    tag_part_format: str = "_{tag}"
    lowercase_extensions: bool = True
    keep_original_if_conflict: bool = True


@dataclass
class DuplicatesConfig:
    """Duplicate handling configuration settings."""

    enabled: bool = True
    policy: str = "safe"  # Planned (future): safe, skip, overwrite (currently unused)
    hashing_algorithm: str = "sha256"  # sha256, md5
    on_collision: str = "check_hash"  # check_hash, rename, skip, fail
    cache_hashes: bool = True  # Planned v0.6: persistent hash cache


@dataclass
class FilenameDateConfig:
    """Filename date extraction configuration (v0.2)."""

    enabled: bool = True
    patterns: list[str] = field(
        default_factory=lambda: [
            "YYYYMMDD_HHMMSS",
            "YYYYMMDD",
            "YYMMDD",
            "YYYY-MM-DD",
            "YYYY_MM_DD",
        ]
    )
    year_cutoff: int = 30  # 00-30 = 2000s, 31-99 = 1900s
    priority: str = "after_exif"  # before_exif, after_exif, after_filesystem


@dataclass
class DateMismatchConfig:
    """Date mismatch detection configuration (v0.2)."""

    enabled: bool = True
    threshold_days: int = 1
    warn_on_scan: bool = True  # Planned (future): show warnings during scan
    include_in_export: bool = True  # Planned (future): conditionally include in export


@dataclass
class ExportConfig:
    """Export configuration (v0.2).
    
    Note: These are planned to be used as defaults when CLI options
    are not specified. Currently, CLI options have their own defaults.
    """

    default_format: str = "json"  # json, csv
    include_statistics: bool = True
    include_folder_tags: bool = True
    pretty_print: bool = True
    output_path: str = ".chronoclean/export"


@dataclass
class VerifyConfig:
    """Verification and cleanup configuration (v0.3.1)."""

    enabled: bool = False  # Default off; user opts in when needed
    algorithm: str = "sha256"  # sha256 | quick
    state_dir: str = ".chronoclean"  # Stored in current working directory
    run_record_dir: str = "runs"  # Resolved under state_dir
    verification_dir: str = "verifications"  # Resolved under state_dir
    allow_cleanup_on_quick: bool = False  # Quick mode not eligible for cleanup by default
    content_search_on_reconstruct: bool = False  # Search destination tree by content if expected path missing
    write_run_record: bool = True  # Write run record on apply by default


@dataclass
class DryRunConfig:
    """Dry run display configuration settings."""

    show_moves: bool = True
    show_renames: bool = True
    show_tags: bool = True
    show_duplicates: bool = True
    summary_only: bool = False


@dataclass
class LoggingConfig:
    """Logging configuration settings."""

    level: str = "info"
    color_output: bool = True
    log_to_file: bool = True
    file_path: str = ".chronoclean/chronoclean.log"


@dataclass
class PerformanceConfig:
    """Performance configuration settings (planned v0.6)."""

    multiprocessing: bool = True  # Planned v0.6: parallel scan/inference
    max_workers: int = 0  # Planned v0.6: 0 = auto-detect CPU count
    chunk_size: int = 500  # Planned v0.6: batch processing size
    enable_cache: bool = True  # Planned v0.6: metadata caching
    cache_location: str = ".chronoclean/cache.db"  # Planned v0.6: SQLite cache path


@dataclass
class SynologyConfig:
    """Synology NAS specific configuration settings."""

    safe_fs_mode: bool = True
    use_long_paths: bool = False
    min_free_space_mb: int = 500


@dataclass
class ChronoCleanConfig:
    """Root configuration object for ChronoClean."""

    version: str = "1.0"
    general: GeneralConfig = field(default_factory=GeneralConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    sorting: SortingConfig = field(default_factory=SortingConfig)
    heuristic: HeuristicConfig = field(default_factory=HeuristicConfig)
    folder_tags: FolderTagsConfig = field(default_factory=FolderTagsConfig)
    renaming: RenamingConfig = field(default_factory=RenamingConfig)
    duplicates: DuplicatesConfig = field(default_factory=DuplicatesConfig)
    # v0.2 additions
    filename_date: FilenameDateConfig = field(default_factory=FilenameDateConfig)
    date_mismatch: DateMismatchConfig = field(default_factory=DateMismatchConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    # v0.3 additions
    video_metadata: VideoMetadataConfig = field(default_factory=VideoMetadataConfig)
    # v0.3.1 additions
    verify: VerifyConfig = field(default_factory=VerifyConfig)
    # Display and system
    dry_run: DryRunConfig = field(default_factory=DryRunConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    synology: SynologyConfig = field(default_factory=SynologyConfig)

    @property
    def all_supported_extensions(self) -> set[str]:
        """Get all supported file extensions."""
        return (
            set(self.scan.image_extensions)
            | set(self.scan.video_extensions)
            | set(self.scan.raw_extensions)
        )
