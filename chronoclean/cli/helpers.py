"""CLI helper functions and component factories for ChronoClean.

This module provides shared utilities to reduce code duplication across CLI commands.
"""
# pylint: disable=too-many-branches
# Helper dispatch functions have inherent branching complexity

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from chronoclean.config.schema import ChronoCleanConfig
from chronoclean.core.date_inference import DateInferenceEngine
from chronoclean.core.exif_reader import ExifReader
from chronoclean.core.folder_tagger import FolderTagger
from chronoclean.core.models import FileRecord
from chronoclean.core.renamer import ConflictResolver, Renamer
from chronoclean.core.scanner import Scanner
from chronoclean.core.sorter import Sorter
from chronoclean.core.video_metadata import VideoMetadataReader


def _build_date_priority(cfg: ChronoCleanConfig) -> list[str]:
    """
    Build date inference priority list including filename based on config.
    
    The filename_date.priority setting determines where "filename" is inserted:
    - "before_exif": filename checked first
    - "after_exif": filename checked after exif but before filesystem
    - "after_filesystem": filename checked after filesystem but before folder_name
    
    Args:
        cfg: ChronoClean configuration
        
    Returns:
        Priority list for DateInferenceEngine
    """
    base_priority = list(cfg.sorting.fallback_date_priority)
    
    # v0.3: Strip video_metadata if disabled
    if not cfg.video_metadata.enabled:
        base_priority = [p for p in base_priority if p != "video_metadata"]
    
    # Only add filename to priority if enabled
    if not cfg.filename_date.enabled:
        # Strip "filename" if user had it in fallback_date_priority but disabled the feature
        return [p for p in base_priority if p != "filename"]
    
    # Don't add if already present
    if "filename" in base_priority:
        return base_priority
    
    priority_setting = cfg.filename_date.priority
    
    if priority_setting == "before_exif":
        # Insert at the beginning
        return ["filename"] + base_priority
    elif priority_setting == "after_exif":
        # Insert after exif if present, otherwise at position 1
        if "exif" in base_priority:
            idx = base_priority.index("exif") + 1
            return base_priority[:idx] + ["filename"] + base_priority[idx:]
        else:
            return ["filename"] + base_priority
    elif priority_setting == "after_filesystem":
        # Insert after filesystem if present
        if "filesystem" in base_priority:
            idx = base_priority.index("filesystem") + 1
            return base_priority[:idx] + ["filename"] + base_priority[idx:]
        elif "exif" in base_priority:
            idx = base_priority.index("exif") + 1
            return base_priority[:idx] + ["filename"] + base_priority[idx:]
        else:
            return base_priority + ["filename"]
    else:
        # Default: after_exif behavior
        if "exif" in base_priority:
            idx = base_priority.index("exif") + 1
            return base_priority[:idx] + ["filename"] + base_priority[idx:]
        else:
            return ["filename"] + base_priority


@dataclass
class ScanComponents:
    """Container for scan-related components created from config."""
    
    exif_reader: ExifReader
    video_reader: Optional[VideoMetadataReader]
    folder_tagger: FolderTagger
    date_engine: DateInferenceEngine
    cfg: ChronoCleanConfig
    
    def create_scanner(
        self,
        recursive: bool,
        include_videos: bool,
    ) -> Scanner:
        """Create a Scanner instance with the stored components.
        
        Args:
            recursive: Whether to scan recursively
            include_videos: Whether to include video files
            
        Returns:
            Configured Scanner instance
        """
        return Scanner(
            date_engine=self.date_engine,
            folder_tagger=self.folder_tagger,
            image_extensions=set(self.cfg.scan.image_extensions),
            video_extensions=set(self.cfg.scan.video_extensions),
            raw_extensions=set(self.cfg.scan.raw_extensions),
            recursive=recursive,
            include_videos=include_videos,
            ignore_hidden=self.cfg.general.ignore_hidden_files,
            date_mismatch_enabled=self.cfg.date_mismatch.enabled,
            date_mismatch_threshold_days=self.cfg.date_mismatch.threshold_days,
        )


def create_scan_components(cfg: ChronoCleanConfig) -> ScanComponents:
    """Create all scan-related components from configuration.
    
    This factory function centralizes the creation of ExifReader, VideoMetadataReader,
    FolderTagger, and DateInferenceEngine to eliminate code duplication across
    scan, apply, export, and verify commands.
    
    Args:
        cfg: ChronoClean configuration
        
    Returns:
        ScanComponents dataclass containing all configured components
    """
    # Create EXIF reader
    exif_reader = ExifReader(skip_errors=cfg.scan.skip_exif_errors)
    
    # Create video metadata reader (if enabled)
    video_reader = None
    if cfg.video_metadata.enabled:
        video_reader = VideoMetadataReader(
            provider=cfg.video_metadata.provider,
            ffprobe_path=cfg.video_metadata.ffprobe_path,
            fallback_to_hachoir=cfg.video_metadata.fallback_to_hachoir,
            skip_errors=cfg.video_metadata.skip_errors,
        )
    
    # Create folder tagger
    folder_tagger = FolderTagger(
        ignore_list=cfg.folder_tags.ignore_list,
        force_list=cfg.folder_tags.force_list,
        min_length=cfg.folder_tags.min_length,
        max_length=cfg.folder_tags.max_length,
        distance_threshold=cfg.folder_tags.distance_threshold,
    )
    
    # Create date inference engine
    date_engine = DateInferenceEngine(
        priority=_build_date_priority(cfg),
        exif_reader=exif_reader,
        video_reader=video_reader,
        year_cutoff=cfg.filename_date.year_cutoff,
        filename_date_enabled=cfg.filename_date.enabled,
        video_metadata_enabled=cfg.video_metadata.enabled,
    )
    
    return ScanComponents(
        exif_reader=exif_reader,
        video_reader=video_reader,
        folder_tagger=folder_tagger,
        date_engine=date_engine,
        cfg=cfg,
    )


def validate_source_dir(path: Path, console: Console) -> Path:
    """Validate and resolve a source directory path.
    
    Args:
        path: Path to validate
        console: Rich console for error output
        
    Returns:
        Resolved Path if valid
        
    Raises:
        typer.Exit: If path doesn't exist or is not a directory
    """
    resolved = path.resolve()
    
    if not resolved.exists():
        console.print(f"[red]Error:[/red] Source path not found: {resolved}")
        raise typer.Exit(1)
    
    if not resolved.is_dir():
        console.print(f"[red]Error:[/red] Source is not a directory: {resolved}")
        raise typer.Exit(1)
    
    return resolved


def validate_destination_dir(path: Path, console: Console) -> Path:
    """Validate and resolve a destination directory path.
    
    Unlike source validation, destination doesn't need to exist yet.
    
    Args:
        path: Path to validate
        console: Rich console for error output
        
    Returns:
        Resolved Path
    """
    return path.resolve()


def error_exit(console: Console, message: str, code: int = 1) -> None:
    """Print an error message and exit.
    
    Args:
        console: Rich console for output
        message: Error message to display
        code: Exit code (default: 1)
        
    Raises:
        typer.Exit: Always raises with the given code
    """
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code)


def resolve_bool(cli_value: Optional[bool], config_value: bool) -> bool:
    """Resolve boolean value: CLI overrides config if explicitly set.
    
    Args:
        cli_value: Value from CLI (None if not provided)
        config_value: Default value from config
        
    Returns:
        CLI value if provided, otherwise config value
    """
    return config_value if cli_value is None else cli_value


def build_renamer_context(
    cfg: ChronoCleanConfig,
    use_rename: bool,
) -> tuple[Optional[Renamer], Optional[ConflictResolver]]:
    """Create renamer and conflict resolver based on config and flags."""
    if not use_rename:
        return None, None

    renamer = Renamer(
        pattern=cfg.renaming.pattern,
        date_format=cfg.renaming.date_format,
        time_format=cfg.renaming.time_format,
        tag_format=cfg.renaming.tag_part_format,
        lowercase_ext=cfg.renaming.lowercase_extensions,
    )
    conflict_resolver = ConflictResolver(renamer)
    return renamer, conflict_resolver


def compute_destination_for_record(
    record: FileRecord,
    sorter: Sorter,
    cfg: ChronoCleanConfig,
    *,
    use_rename: bool,
    use_tag_names: bool,
    renamer: Optional[Renamer],
    conflict_resolver: Optional[ConflictResolver],
) -> tuple[Path, str, Optional[Renamer]]:
    """Compute destination folder and filename for a file record."""
    dest_folder = sorter.compute_destination_folder(record.detected_date)

    new_filename = None
    if use_rename and renamer and conflict_resolver:
        tag = record.folder_tag if use_tag_names and record.folder_tag_usable else None
        new_filename = conflict_resolver.resolve(
            record.source_path,
            record.detected_date,
            tag=tag,
        )
    elif use_tag_names and record.folder_tag_usable and record.folder_tag:
        if not renamer:
            renamer = Renamer(lowercase_ext=cfg.renaming.lowercase_extensions)
        new_filename = renamer.generate_filename_tag_only(
            record.source_path,
            record.folder_tag,
        )
    else:
        new_filename = record.source_path.name

    return dest_folder, new_filename, renamer
