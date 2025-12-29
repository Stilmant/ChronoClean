"""Main CLI application for ChronoClean."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from chronoclean import __version__
from chronoclean.config import ConfigLoader
from chronoclean.config.schema import ChronoCleanConfig
from chronoclean.config.templates import get_config_template
from chronoclean.core.scanner import Scanner
from chronoclean.core.sorter import Sorter
from chronoclean.core.renamer import Renamer, ConflictResolver
from chronoclean.core.folder_tagger import FolderTagger
from chronoclean.core.date_inference import DateInferenceEngine
from chronoclean.core.video_metadata import VideoMetadataReader
from chronoclean.core.exif_reader import ExifReader
from chronoclean.core.file_operations import FileOperations, BatchOperations, FileOperationError
from chronoclean.core.models import OperationPlan
from chronoclean.core.exporter import Exporter, export_to_json, export_to_csv
from chronoclean.core.duplicate_checker import DuplicateChecker
from chronoclean.utils.logging import setup_logging

# Initialize console
console = Console()

# Load config at module level to generate dynamic help text
# This allows --help to show actual defaults from config (or built-in if no config)
_default_cfg = ConfigLoader.load(None)
_has_config_file = any(p.exists() for p in ConfigLoader.DEFAULT_CONFIG_PATHS)
_cfg_note = " via config" if _has_config_file else ""


def _bool_show_default(value: bool, true_word: str, false_word: str) -> str:
    """Generate show_default string for boolean flags."""
    return f"{true_word if value else false_word}{_cfg_note}"


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


app = typer.Typer(
    name="chronoclean",
    help="ChronoClean — Restore order to your photo collections.",
    add_completion=False,
    no_args_is_help=True,
)

# Config subcommand group
config_app = typer.Typer(
    name="config",
    help="Configuration management commands.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")

# Export subcommand group
export_app = typer.Typer(
    name="export",
    help="Export scan results to various formats.",
    no_args_is_help=True,
)
app.add_typer(export_app, name="export")


# Sentinel value for detecting if CLI option was explicitly set
UNSET = None


@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """ChronoClean — Restore order to your photo collections."""
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(level=log_level)


def _resolve_bool(cli_value: Optional[bool], config_value: bool) -> bool:
    """Resolve boolean value: CLI overrides config if explicitly set."""
    return config_value if cli_value is None else cli_value


def _show_config_info(cfg: ChronoCleanConfig, config_path: Optional[Path]) -> None:
    """Display config file info if one was loaded."""
    if config_path:
        console.print(f"[dim]Config: {config_path}[/dim]")
    console.print()


@app.command()
def scan(
    source: Path = typer.Argument(..., help="Source directory to scan"),
    recursive: Optional[bool] = typer.Option(
        None, "--recursive/--no-recursive",
        help="Scan subfolders",
        show_default=_bool_show_default(_default_cfg.general.recursive, "recursive", "no-recursive"),
    ),
    videos: Optional[bool] = typer.Option(
        None, "--videos/--no-videos",
        help="Include video files",
        show_default=_bool_show_default(_default_cfg.general.include_videos, "videos", "no-videos"),
    ),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Limit files (for debugging)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
    report: bool = typer.Option(False, "--report", "-r", help="Show detailed per-file report"),
):
    """
    Analyze files in the source directory.

    Scans the directory, reads EXIF metadata, infers dates, and detects folder tags.
    
    Configuration can be provided via --config flag or by placing a chronoclean.yaml
    file in the current directory. CLI arguments override config file values.
    """
    # Load configuration
    cfg = ConfigLoader.load(config)

    # Resolve options: CLI overrides config
    use_recursive = _resolve_bool(recursive, cfg.general.recursive)
    use_videos = _resolve_bool(videos, cfg.general.include_videos)
    use_limit = limit if limit is not None else cfg.scan.limit

    # Validate source
    source = source.resolve()
    if not source.exists():
        console.print(f"[red]Error:[/red] Source path not found: {source}")
        raise typer.Exit(1)

    if not source.is_dir():
        console.print(f"[red]Error:[/red] Source is not a directory: {source}")
        raise typer.Exit(1)

    console.print(f"[blue]Scanning:[/blue] {source}")
    if config:
        console.print(f"[dim]Config: {config}[/dim]")
    console.print()

    # Create components from config
    exif_reader = ExifReader(skip_errors=cfg.scan.skip_exif_errors)
    
    # v0.3: Create video metadata reader with config
    video_reader = VideoMetadataReader(
        provider=cfg.video_metadata.provider,
        ffprobe_path=cfg.video_metadata.ffprobe_path,
        fallback_to_hachoir=cfg.video_metadata.fallback_to_hachoir,
        skip_errors=cfg.video_metadata.skip_errors,
    ) if cfg.video_metadata.enabled else None
    
    folder_tagger = FolderTagger(
        ignore_list=cfg.folder_tags.ignore_list,
        force_list=cfg.folder_tags.force_list,
        min_length=cfg.folder_tags.min_length,
        max_length=cfg.folder_tags.max_length,
        distance_threshold=cfg.folder_tags.distance_threshold,
    )
    
    date_engine = DateInferenceEngine(
        priority=_build_date_priority(cfg),
        exif_reader=exif_reader,
        video_reader=video_reader,
        year_cutoff=cfg.filename_date.year_cutoff,
        filename_date_enabled=cfg.filename_date.enabled,
        video_metadata_enabled=cfg.video_metadata.enabled,
    )

    # Create scanner with config values
    scanner = Scanner(
        date_engine=date_engine,
        folder_tagger=folder_tagger,
        image_extensions=set(cfg.scan.image_extensions),
        video_extensions=set(cfg.scan.video_extensions),
        raw_extensions=set(cfg.scan.raw_extensions),
        recursive=use_recursive,
        include_videos=use_videos,
        ignore_hidden=cfg.general.ignore_hidden_files,
        date_mismatch_enabled=cfg.date_mismatch.enabled,
        date_mismatch_threshold_days=cfg.date_mismatch.threshold_days,
    )

    # Run scan
    with console.status("[bold blue]Scanning files..."):
        result = scanner.scan(source, limit=use_limit)

    # Display results
    console.print()
    console.print("[bold green]Scan Complete[/bold green]")
    console.print()

    # Summary table
    table = Table(title="Scan Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Total files found", str(result.total_files))
    table.add_row("Files processed", str(result.processed_files))
    table.add_row("Files with errors", str(result.error_files))
    table.add_row("Files skipped", str(result.skipped_files))
    table.add_row("Scan duration", f"{result.scan_duration_seconds:.2f}s")

    console.print(table)
    console.print()

    # Date source breakdown
    date_sources: dict[str, int] = {}
    no_date_count = 0
    for record in result.files:
        if record.detected_date:
            source_name = record.date_source.value
            date_sources[source_name] = date_sources.get(source_name, 0) + 1
        else:
            no_date_count += 1

    if date_sources or no_date_count:
        date_table = Table(title="Date Sources")
        date_table.add_column("Source", style="cyan")
        date_table.add_column("Count", style="white")

        for source_name, count in sorted(date_sources.items()):
            date_table.add_row(source_name, str(count))
        if no_date_count:
            date_table.add_row("no date found", str(no_date_count), style="yellow")

        console.print(date_table)
        console.print()

    # Detailed per-file report
    if report:
        console.print()
        console.print("[bold]Detailed File Report:[/bold]")
        report_table = Table(show_header=True)
        report_table.add_column("File", style="cyan", max_width=40)
        report_table.add_column("Date", style="white")
        report_table.add_column("Source", style="yellow")
        report_table.add_column("Folder Tag", style="green")

        for record in result.files:
            filename = record.source_path.name
            if len(filename) > 37:
                filename = filename[:34] + "..."
            
            date_str = record.detected_date.strftime("%Y-%m-%d %H:%M") if record.detected_date else "[red]None[/red]"
            source_str = record.date_source.value if record.date_source else "unknown"
            tag_str = record.folder_tag if record.folder_tag else "-"
            
            report_table.add_row(filename, date_str, source_str, tag_str)

        console.print(report_table)
        console.print()

    # Folder tags detected
    if result.folder_tags_detected:
        console.print(f"[bold]Folder tags detected:[/bold] {len(result.folder_tags_detected)}")
        for tag in result.folder_tags_detected[:10]:
            console.print(f"  • {tag}")
        if len(result.folder_tags_detected) > 10:
            console.print(f"  ... and {len(result.folder_tags_detected) - 10} more")
        console.print()

    # Errors
    if result.errors:
        console.print(f"[yellow]Errors ({len(result.errors)}):[/yellow]")
        for path, error in result.errors[:5]:
            console.print(f"  • {path.name}: {error}")
        if len(result.errors) > 5:
            console.print(f"  ... and {len(result.errors) - 5} more")

    # v0.3: Error categories summary
    if result.errors_by_category:
        console.print()
        console.print("[yellow]Errors by category:[/yellow]")
        for category, count in sorted(result.errors_by_category.items()):
            console.print(f"  • {category}: {count}")


@app.command()
def apply(
    source: Path = typer.Argument(..., help="Source directory"),
    destination: Path = typer.Argument(..., help="Destination directory"),
    dry_run: Optional[bool] = typer.Option(
        None, "--dry-run/--no-dry-run",
        help="Simulate without changes",
        show_default=_bool_show_default(_default_cfg.general.dry_run_default, "dry-run", "no-dry-run"),
    ),
    move: bool = typer.Option(False, "--move", help="Move files instead of copy (default: copy)"),
    rename: Optional[bool] = typer.Option(
        None, "--rename/--no-rename",
        help="Enable file renaming",
        show_default=_bool_show_default(_default_cfg.renaming.enabled, "rename", "no-rename"),
    ),
    tag_names: Optional[bool] = typer.Option(
        None, "--tag-names/--no-tag-names",
        help="Add folder tags to filenames (works with or without --rename)",
        show_default=_bool_show_default(_default_cfg.folder_tags.enabled, "tag-names", "no-tag-names"),
    ),
    recursive: Optional[bool] = typer.Option(
        None, "--recursive/--no-recursive",
        help="Scan subfolders",
        show_default=_bool_show_default(_default_cfg.general.recursive, "recursive", "no-recursive"),
    ),
    videos: Optional[bool] = typer.Option(
        None, "--videos/--no-videos",
        help="Include video files",
        show_default=_bool_show_default(_default_cfg.general.include_videos, "videos", "no-videos"),
    ),
    structure: Optional[str] = typer.Option(
        None, "--structure", "-s",
        help="Folder structure",
        show_default=f"{_default_cfg.sorting.folder_structure}{_cfg_note}",
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Limit files"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Config file path"),
):
    """
    Apply file organization (moves and optional renames).

    Organizes files into a chronological folder structure based on their dates.
    By default runs in dry-run mode. Use --no-dry-run to perform actual changes.
    
    Configuration can be provided via --config flag or by placing a chronoclean.yaml
    file in the current directory. CLI arguments override config file values.
    """
    # Load configuration
    cfg = ConfigLoader.load(config)

    # Resolve options: CLI overrides config
    use_dry_run = _resolve_bool(dry_run, cfg.general.dry_run_default)
    use_rename = _resolve_bool(rename, cfg.renaming.enabled)
    use_tag_names = _resolve_bool(tag_names, cfg.folder_tags.enabled)
    use_recursive = _resolve_bool(recursive, cfg.general.recursive)
    use_videos = _resolve_bool(videos, cfg.general.include_videos)
    use_structure = structure if structure is not None else cfg.sorting.folder_structure
    use_limit = limit if limit is not None else cfg.scan.limit

    # Validate paths
    source = source.resolve()
    destination = destination.resolve()

    if not source.exists():
        console.print(f"[red]Error:[/red] Source path not found: {source}")
        raise typer.Exit(1)

    if not source.is_dir():
        console.print(f"[red]Error:[/red] Source is not a directory: {source}")
        raise typer.Exit(1)

    # Show mode
    mode_text = "[yellow]DRY RUN[/yellow]" if use_dry_run else "[red]LIVE MODE[/red]"
    operation_text = "[red]MOVE[/red]" if move else "[green]COPY[/green]"
    console.print(f"Mode: {mode_text}")
    console.print(f"Operation: {operation_text}")
    console.print(f"Source: {source}")
    console.print(f"Destination: {destination}")
    console.print(f"Structure: {use_structure}")
    console.print(f"Renaming: {'enabled' if use_rename else 'disabled'}")
    console.print(f"Folder tags: {'enabled' if use_tag_names else 'disabled'}")
    if config:
        console.print(f"[dim]Config: {config}[/dim]")
    console.print()

    # Confirmation for live mode
    if not use_dry_run and not force:
        action = "move" if move else "copy"
        confirm = typer.confirm(f"This will {action} files. Continue?")
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit(0)

    # Create components from config
    folder_tagger = FolderTagger(
        ignore_list=cfg.folder_tags.ignore_list,
        force_list=cfg.folder_tags.force_list,
        min_length=cfg.folder_tags.min_length,
        max_length=cfg.folder_tags.max_length,
        distance_threshold=cfg.folder_tags.distance_threshold,
    )
    
    exif_reader = ExifReader(skip_errors=cfg.scan.skip_exif_errors)
    
    # v0.3: Create video metadata reader with config
    video_reader = VideoMetadataReader(
        provider=cfg.video_metadata.provider,
        ffprobe_path=cfg.video_metadata.ffprobe_path,
        fallback_to_hachoir=cfg.video_metadata.fallback_to_hachoir,
        skip_errors=cfg.video_metadata.skip_errors,
    ) if cfg.video_metadata.enabled else None
    
    date_engine = DateInferenceEngine(
        priority=_build_date_priority(cfg),
        year_cutoff=cfg.filename_date.year_cutoff,
        filename_date_enabled=cfg.filename_date.enabled,
        exif_reader=exif_reader,
        video_reader=video_reader,
        video_metadata_enabled=cfg.video_metadata.enabled,
    )

    # Scan files
    console.print("[blue]Scanning files...[/blue]")
    scanner = Scanner(
        date_engine=date_engine,
        folder_tagger=folder_tagger,
        image_extensions=set(cfg.scan.image_extensions),
        video_extensions=set(cfg.scan.video_extensions),
        raw_extensions=set(cfg.scan.raw_extensions),
        recursive=use_recursive,
        include_videos=use_videos,
        ignore_hidden=cfg.general.ignore_hidden_files,
        date_mismatch_enabled=cfg.date_mismatch.enabled,
        date_mismatch_threshold_days=cfg.date_mismatch.threshold_days,
    )
    scan_result = scanner.scan(source, limit=use_limit)

    if not scan_result.files:
        console.print("[yellow]No files found to process.[/yellow]")
        raise typer.Exit(0)

    console.print(f"Found {len(scan_result.files)} files")
    console.print()

    # Build operation plan
    console.print("[blue]Building operation plan...[/blue]")
    sorter = Sorter(destination, folder_structure=use_structure)
    
    # Configure renamer from config
    renamer = None
    conflict_resolver = None
    if use_rename:
        renamer = Renamer(
            pattern=cfg.renaming.pattern,
            date_format=cfg.renaming.date_format,
            time_format=cfg.renaming.time_format,
            tag_format=cfg.renaming.tag_part_format,
            lowercase_ext=cfg.renaming.lowercase_extensions,
        )
        conflict_resolver = ConflictResolver(renamer)

    plan = OperationPlan()
    files_with_dates = 0
    files_without_dates = 0

    for record in scan_result.files:
        if not record.detected_date:
            files_without_dates += 1
            plan.add_skip(record.source_path, "No date detected")
            continue

        files_with_dates += 1

        # Compute destination
        dest_folder = sorter.compute_destination_folder(record.detected_date)

        # Determine filename
        new_filename = None
        if use_rename and renamer and conflict_resolver:
            # Full rename mode: use date pattern with optional tag
            tag = record.folder_tag if use_tag_names and record.folder_tag_usable else None
            new_filename = conflict_resolver.resolve(
                record.source_path,
                record.detected_date,
                tag=tag,
            )
        elif use_tag_names and record.folder_tag_usable and record.folder_tag:
            # v0.3: Tag-only mode - preserve original filename, append tag
            # Need a renamer instance for tag formatting
            if not renamer:
                renamer = Renamer(lowercase_ext=cfg.renaming.lowercase_extensions)
            new_filename = renamer.generate_filename_tag_only(
                record.source_path,
                record.folder_tag,
            )
        else:
            # No rename, no tag - keep original filename
            new_filename = record.source_path.name

        # Add to plan
        plan.add_move(
            source=record.source_path,
            destination=dest_folder,
            new_filename=new_filename,
        )

    # Display plan summary
    console.print()
    console.print("[bold]Operation Plan:[/bold]")
    console.print(f"  Files to move: {len(plan.moves)}")
    console.print(f"  Files skipped: {len(plan.skipped)}")
    if files_without_dates:
        console.print(f"  [yellow]Files without dates: {files_without_dates}[/yellow]")
    console.print()

    # Show sample operations
    if plan.moves and len(plan.moves) <= 20:
        table = Table(title="Planned Operations")
        table.add_column("Source", style="cyan", no_wrap=True)
        table.add_column("Destination", style="green")

        for op in plan.moves[:20]:
            src_name = op.source.name
            dest_rel = str(op.destination_path.relative_to(destination))
            table.add_row(src_name, dest_rel)

        console.print(table)
        console.print()
    elif plan.moves:
        console.print(f"[dim](Showing first 10 of {len(plan.moves)} operations)[/dim]")
        for op in plan.moves[:10]:
            src_name = op.source.name
            dest_rel = str(op.destination_path.relative_to(destination))
            console.print(f"  {src_name} → {dest_rel}")
        console.print()

    # Execute operations
    if use_dry_run:
        console.print("[yellow]Dry run complete. No files were modified.[/yellow]")
        console.print("Run with --no-dry-run to apply changes.")
    else:
        console.print("[blue]Executing operations...[/blue]")
        
        # Initialize duplicate checker if enabled
        duplicate_checker = None
        if cfg.duplicates.enabled:
            duplicate_checker = DuplicateChecker(
                algorithm=cfg.duplicates.hashing_algorithm,
                cache_enabled=cfg.duplicates.cache_hashes,
            )
        
        file_ops = FileOperations(dry_run=False)
        batch = BatchOperations(file_ops, dry_run=False)

        # Process operations with collision detection
        # Track reserved destinations AND their source files for content comparison
        operations_to_execute = []
        reserved_destinations: set[Path] = set()
        reserved_sources: dict[Path, Path] = {}  # dest_path -> source_path
        duplicates_skipped = 0
        collisions_renamed = 0
        
        try:
            for op in plan.moves:
                dest_path = op.destination_path
                
                # Check if destination already exists on disk OR is reserved by another operation
                if dest_path.exists() or dest_path in reserved_destinations:
                    if duplicate_checker and cfg.duplicates.on_collision == "check_hash":
                        # Check if files are duplicates
                        if dest_path.exists():
                            # Compare against existing file on disk
                            if duplicate_checker.are_duplicates(op.source, dest_path):
                                duplicates_skipped += 1
                                continue
                        elif dest_path in reserved_sources:
                            # Compare against the source file that reserved this destination
                            if duplicate_checker.are_duplicates(op.source, reserved_sources[dest_path]):
                                duplicates_skipped += 1
                                continue
                        # Files have same name but different content - rename
                        dest_path = file_ops.ensure_unique_path(dest_path, reserved_destinations)
                        collisions_renamed += 1
                    elif cfg.duplicates.on_collision == "rename":
                        # Always rename on collision
                        dest_path = file_ops.ensure_unique_path(dest_path, reserved_destinations)
                        collisions_renamed += 1
                    elif cfg.duplicates.on_collision == "skip":
                        # Skip if destination exists or reserved
                        duplicates_skipped += 1
                        continue
                    elif cfg.duplicates.on_collision == "fail":
                        console.print(f"[red]Error:[/red] Destination exists or reserved: {dest_path}")
                        raise typer.Exit(1)
                    else:
                        # Default: check_hash behavior
                        if duplicate_checker:
                            if dest_path.exists():
                                if duplicate_checker.are_duplicates(op.source, dest_path):
                                    duplicates_skipped += 1
                                    continue
                            elif dest_path in reserved_sources:
                                if duplicate_checker.are_duplicates(op.source, reserved_sources[dest_path]):
                                    duplicates_skipped += 1
                                    continue
                        dest_path = file_ops.ensure_unique_path(dest_path, reserved_destinations)
                        collisions_renamed += 1
                
                reserved_destinations.add(dest_path)
                reserved_sources[dest_path] = op.source
                operations_to_execute.append((op.source, dest_path))
        except FileOperationError as e:
            console.print(f"[red]Error:[/red] {e}", stderr=True)
            raise typer.Exit(1)
        
        if move:
            success, failed = batch.execute_moves(operations_to_execute)
            action_word = "moved"
        else:
            success, failed = batch.execute_copies(operations_to_execute)
            action_word = "copied"

        console.print()
        console.print("[bold green]Complete![/bold green]")
        console.print(f"  Successfully {action_word}: {success}")
        if duplicates_skipped:
            console.print(f"  [yellow]Duplicates skipped: {duplicates_skipped}[/yellow]")
        if collisions_renamed:
            console.print(f"  [yellow]Collisions renamed: {collisions_renamed}[/yellow]")
        if failed:
            console.print(f"  [red]Failed: {failed}[/red]")


# ============================================================================
# CONFIG COMMANDS
# ============================================================================


@config_app.command("init")
def config_init(
    output: Path = typer.Option(
        Path("chronoclean.yaml"),
        "--output", "-o",
        help="Output file path",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Generate full config with all options (default: minimal)",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Overwrite existing config file",
    ),
):
    """
    Initialize a new configuration file.
    
    Creates a chronoclean.yaml file in the current directory (or specified path).
    Use --full to generate a complete config with all options documented.
    """
    output = output.resolve()
    
    # Check if file exists
    if output.exists() and not force:
        console.print(f"[yellow]Config file already exists:[/yellow] {output}")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)
    
    # Get template
    template = get_config_template(full=full)
    
    # Write file
    try:
        output.write_text(template, encoding="utf-8")
        console.print(f"[green]Created config file:[/green] {output}")
        
        if full:
            console.print("[dim]Full configuration with all options documented.[/dim]")
        else:
            console.print("[dim]Minimal configuration. Edit to customize.[/dim]")
        
        console.print()
        console.print("Next steps:")
        console.print(f"  1. Edit {output.name} to customize settings")
        console.print("  2. Run: chronoclean scan <source>")
        
    except OSError as e:
        console.print(f"[red]Error writing config file:[/red] {e}")
        raise typer.Exit(1)


@config_app.command("show")
def config_show(
    config: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Config file path (default: auto-detect)",
    ),
    section: Optional[str] = typer.Option(
        None,
        "--section", "-s",
        help="Show only specific section (e.g., 'sorting', 'folder_tags')",
    ),
):
    """
    Show current configuration.
    
    Displays the effective configuration from config file merged with defaults.
    """
    import yaml
    from dataclasses import asdict
    
    # Load config
    cfg = ConfigLoader.load(config)
    
    # Convert to dict for display
    config_dict = asdict(cfg)
    
    # Filter to section if specified
    if section:
        if section not in config_dict:
            console.print(f"[red]Unknown section:[/red] {section}")
            console.print(f"Available sections: {', '.join(config_dict.keys())}")
            raise typer.Exit(1)
        config_dict = {section: config_dict[section]}
    
    # Display
    console.print("[bold]ChronoClean Configuration[/bold]")
    console.print()
    
    if config:
        console.print(f"[dim]Source: {config}[/dim]")
    else:
        # Check which file was found
        for search_path in ConfigLoader.DEFAULT_CONFIG_PATHS:
            if search_path.exists():
                console.print(f"[dim]Source: {search_path}[/dim]")
                break
        else:
            console.print("[dim]Source: built-in defaults[/dim]")
    
    console.print()
    
    # Pretty print as YAML
    yaml_output = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
    console.print(yaml_output)


@config_app.command("path")
def config_path():
    """
    Show where ChronoClean looks for config files.
    """
    console.print("[bold]Config file search paths:[/bold]")
    console.print()
    
    found = False
    for i, search_path in enumerate(ConfigLoader.DEFAULT_CONFIG_PATHS, 1):
        exists = search_path.exists()
        if exists and not found:
            status = "[green]✓ ACTIVE[/green]"
            found = True
        elif exists:
            status = "[yellow]exists (not used)[/yellow]"
        else:
            status = "[dim]not found[/dim]"
        
        console.print(f"  {i}. {search_path} {status}")
    
    if not found:
        console.print()
        console.print("[dim]No config file found. Using built-in defaults.[/dim]")
        console.print("Run 'chronoclean config init' to create one.")


def _perform_scan(
    source: Path,
    cfg: ChronoCleanConfig,
    recursive: Optional[bool] = None,
    videos: Optional[bool] = None,
    limit: Optional[int] = None,
):
    """Perform a scan and return the result. Used by export commands."""
    from chronoclean.core.models import ScanResult
    
    # Resolve options: CLI overrides config
    use_recursive = _resolve_bool(recursive, cfg.general.recursive)
    use_videos = _resolve_bool(videos, cfg.general.include_videos)
    use_limit = limit if limit is not None else cfg.scan.limit

    # Validate source
    source = source.resolve()
    if not source.exists():
        console.print(f"[red]Error:[/red] Source path not found: {source}")
        raise typer.Exit(1)

    if not source.is_dir():
        console.print(f"[red]Error:[/red] Source is not a directory: {source}")
        raise typer.Exit(1)

    # Create components from config
    folder_tagger = FolderTagger(
        ignore_list=cfg.folder_tags.ignore_list,
        force_list=cfg.folder_tags.force_list,
        min_length=cfg.folder_tags.min_length,
        max_length=cfg.folder_tags.max_length,
        distance_threshold=cfg.folder_tags.distance_threshold,
    )
    
    exif_reader = ExifReader(skip_errors=cfg.scan.skip_exif_errors)
    
    # v0.3: Create video metadata reader with config
    video_reader = VideoMetadataReader(
        provider=cfg.video_metadata.provider,
        ffprobe_path=cfg.video_metadata.ffprobe_path,
        fallback_to_hachoir=cfg.video_metadata.fallback_to_hachoir,
        skip_errors=cfg.video_metadata.skip_errors,
    ) if cfg.video_metadata.enabled else None
    
    date_engine = DateInferenceEngine(
        priority=_build_date_priority(cfg),
        year_cutoff=cfg.filename_date.year_cutoff,
        filename_date_enabled=cfg.filename_date.enabled,
        exif_reader=exif_reader,
        video_reader=video_reader,
        video_metadata_enabled=cfg.video_metadata.enabled,
    )

    # Create scanner with config values
    scanner = Scanner(
        date_engine=date_engine,
        folder_tagger=folder_tagger,
        image_extensions=set(cfg.scan.image_extensions),
        video_extensions=set(cfg.scan.video_extensions),
        raw_extensions=set(cfg.scan.raw_extensions),
        recursive=use_recursive,
        include_videos=use_videos,
        ignore_hidden=cfg.general.ignore_hidden_files,
        date_mismatch_enabled=cfg.date_mismatch.enabled,
        date_mismatch_threshold_days=cfg.date_mismatch.threshold_days,
    )

    # Run scan
    with console.status("[bold blue]Scanning files..."):
        result = scanner.scan(source, limit=use_limit)
    
    return result


@export_app.command("json")
def export_json(
    source: Path = typer.Argument(..., help="Source directory to scan"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path (default: stdout)",
    ),
    recursive: Optional[bool] = typer.Option(
        None, "--recursive/--no-recursive",
        help="Scan subfolders",
        show_default=_bool_show_default(_default_cfg.general.recursive, "recursive", "no-recursive"),
    ),
    videos: Optional[bool] = typer.Option(
        None, "--videos/--no-videos",
        help="Include video files",
        show_default=_bool_show_default(_default_cfg.general.include_videos, "videos", "no-videos"),
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l",
        help="Limit files (for debugging)",
    ),
    statistics: bool = typer.Option(
        True, "--statistics/--no-statistics",
        help="Include summary statistics",
    ),
    pretty: bool = typer.Option(
        True, "--pretty/--compact",
        help="Pretty print JSON output",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Config file path",
    ),
):
    """
    Export scan results to JSON format.
    
    Scans the source directory and exports the results to JSON.
    By default outputs to stdout; use --output to write to a file.
    """
    # Load configuration
    cfg = ConfigLoader.load(config)
    
    console.print(f"[blue]Scanning:[/blue] {source}")
    if config:
        console.print(f"[dim]Config: {config}[/dim]")
    console.print()
    
    # Perform scan
    result = _perform_scan(source, cfg, recursive, videos, limit)
    
    # Create exporter
    exporter = Exporter(
        include_statistics=statistics,
        pretty_print=pretty,
    )
    
    # Export
    json_str = exporter.to_json(result, output)
    
    if output:
        console.print(f"[green]Exported to:[/green] {output}")
        console.print(f"[dim]Files: {len(result.files)}[/dim]")
    else:
        # Output to stdout
        console.print(json_str)


@export_app.command("csv")
def export_csv(
    source: Path = typer.Argument(..., help="Source directory to scan"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path (default: stdout)",
    ),
    recursive: Optional[bool] = typer.Option(
        None, "--recursive/--no-recursive",
        help="Scan subfolders",
        show_default=_bool_show_default(_default_cfg.general.recursive, "recursive", "no-recursive"),
    ),
    videos: Optional[bool] = typer.Option(
        None, "--videos/--no-videos",
        help="Include video files",
        show_default=_bool_show_default(_default_cfg.general.include_videos, "videos", "no-videos"),
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l",
        help="Limit files (for debugging)",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Config file path",
    ),
):
    """
    Export scan results to CSV format.
    
    Scans the source directory and exports the results to CSV.
    By default outputs to stdout; use --output to write to a file.
    """
    # Load configuration
    cfg = ConfigLoader.load(config)
    
    console.print(f"[blue]Scanning:[/blue] {source}", stderr=True)
    if config:
        console.print(f"[dim]Config: {config}[/dim]", stderr=True)
    console.print(stderr=True)
    
    # Perform scan
    result = _perform_scan(source, cfg, recursive, videos, limit)
    
    # Create exporter
    exporter = Exporter()
    
    # Export
    csv_str = exporter.to_csv(result, output)
    
    if output:
        console.print(f"[green]Exported to:[/green] {output}", stderr=True)
        console.print(f"[dim]Files: {len(result.files)}[/dim]", stderr=True)
    else:
        # Output to stdout (without rich formatting)
        print(csv_str, end="")


@app.command()
def version():
    """Show ChronoClean version."""
    console.print(f"ChronoClean v{__version__}")


if __name__ == "__main__":
    app()
