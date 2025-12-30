"""Main CLI application for ChronoClean."""

import time
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

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
from chronoclean.core.run_record_writer import RunRecordWriter, ensure_verifications_dir
from chronoclean.core.run_discovery import (
    discover_run_records,
    discover_verification_reports,
    load_run_record,
    load_verification_report,
    find_run_by_id,
    find_verification_by_id,
)
from chronoclean.core.verifier import Verifier, create_verifier_from_config
from chronoclean.core.verification import get_verification_filename
from chronoclean.core.cleaner import Cleaner, format_bytes
from chronoclean.utils.logging import setup_logging
from chronoclean.cli.helpers import (
    create_scan_components,
    validate_source_dir,
    validate_destination_dir,
    error_exit,
    resolve_bool,
    _build_date_priority,
)

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


# Note: _build_date_priority and resolve_bool are imported from cli.helpers


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
    use_recursive = resolve_bool(recursive, cfg.general.recursive)
    use_videos = resolve_bool(videos, cfg.general.include_videos)
    use_limit = limit if limit is not None else cfg.scan.limit

    # Validate source using helper
    source = validate_source_dir(source, console)

    console.print(f"[blue]Scanning:[/blue] {source}")
    if config:
        console.print(f"[dim]Config: {config}[/dim]")
    console.print()

    # Create components from config using factory
    components = create_scan_components(cfg)
    scanner = components.create_scanner(use_recursive, use_videos)

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
    no_run_record: bool = typer.Option(
        False, "--no-run-record",
        help="Disable writing apply run record (v0.3.1)",
    ),
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
    use_dry_run = resolve_bool(dry_run, cfg.general.dry_run_default)
    use_rename = resolve_bool(rename, cfg.renaming.enabled)
    use_tag_names = resolve_bool(tag_names, cfg.folder_tags.enabled)
    use_recursive = resolve_bool(recursive, cfg.general.recursive)
    use_videos = resolve_bool(videos, cfg.general.include_videos)
    use_structure = structure if structure is not None else cfg.sorting.folder_structure
    use_limit = limit if limit is not None else cfg.scan.limit

    # Validate paths using helpers
    source = validate_source_dir(source, console)
    destination = validate_destination_dir(destination, console)

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

    # Create components from config using factory
    components = create_scan_components(cfg)

    # Scan files
    console.print("[blue]Scanning files...[/blue]")
    scanner = components.create_scanner(use_recursive, use_videos)
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
    # v0.3.1: Initialize run record writer (writes on exit)
    write_record = cfg.verify.write_run_record and not no_run_record
    
    if use_dry_run:
        # For dry-run, we still write a run record if enabled (mode: dry_run)
        if write_record:
            with RunRecordWriter(
                source_root=source,
                destination_root=destination,
                config=cfg,
                dry_run=True,
                move_mode=move,
                enabled=True,
            ) as writer:
                # Record what would have been done
                for op in plan.moves:
                    writer.add_copy(op.source, op.destination_path)
                for skip_path, skip_reason in plan.skipped:
                    writer.add_skip(skip_path, skip_reason)
            
            console.print(f"[dim]Run record: {writer.output_path}[/dim]")
        
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
        skipped_operations = []  # v0.3.1: Track skipped for run record
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
                                skipped_operations.append((op.source, "duplicate of existing file"))
                                continue
                        elif dest_path in reserved_sources:
                            # Compare against the source file that reserved this destination
                            if duplicate_checker.are_duplicates(op.source, reserved_sources[dest_path]):
                                duplicates_skipped += 1
                                skipped_operations.append((op.source, "duplicate in batch"))
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
                        skipped_operations.append((op.source, "collision skipped"))
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
                                    skipped_operations.append((op.source, "duplicate of existing file"))
                                    continue
                            elif dest_path in reserved_sources:
                                if duplicate_checker.are_duplicates(op.source, reserved_sources[dest_path]):
                                    duplicates_skipped += 1
                                    skipped_operations.append((op.source, "duplicate in batch"))
                                    continue
                        dest_path = file_ops.ensure_unique_path(dest_path, reserved_destinations)
                        collisions_renamed += 1
                
                reserved_destinations.add(dest_path)
                reserved_sources[dest_path] = op.source
                operations_to_execute.append((op.source, dest_path))
        except FileOperationError as e:
            console.print(f"[red]Error:[/red] {e}", stderr=True)
            raise typer.Exit(1)
        
        # v0.3.1: Write run record with actual executed operations
        run_record_path = None
        if write_record:
            with RunRecordWriter(
                source_root=source,
                destination_root=destination,
                config=cfg,
                dry_run=False,
                move_mode=move,
                enabled=True,
            ) as writer:
                # Record operations that will be executed
                for src, dest in operations_to_execute:
                    if move:
                        writer.add_move(src, dest)
                    else:
                        writer.add_copy(src, dest)
                
                # Record skipped files (from plan.skipped + collision skips)
                for skip_path, skip_reason in plan.skipped:
                    writer.add_skip(skip_path, skip_reason)
                for skip_path, skip_reason in skipped_operations:
                    writer.add_skip(skip_path, skip_reason)
                
                # Execute the actual operations
                if move:
                    success, failed = batch.execute_moves(operations_to_execute)
                    action_word = "moved"
                else:
                    success, failed = batch.execute_copies(operations_to_execute)
                    action_word = "copied"
                
                # Track failures
                for _ in range(failed):
                    writer.add_error()
                
                run_record_path = writer.output_path
        else:
            # Execute without recording
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
        if run_record_path:
            console.print(f"  [dim]Run record: {run_record_path}[/dim]")


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
    # Resolve options: CLI overrides config
    use_recursive = resolve_bool(recursive, cfg.general.recursive)
    use_videos = resolve_bool(videos, cfg.general.include_videos)
    use_limit = limit if limit is not None else cfg.scan.limit

    # Validate source using helper
    source = validate_source_dir(source, console)

    # Create components from config using factory
    components = create_scan_components(cfg)
    scanner = components.create_scanner(use_recursive, use_videos)

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


# ============================================================================
# VERIFY COMMAND (v0.3.1)
# ============================================================================


@app.command()
def verify(
    run_file: Optional[Path] = typer.Option(
        None, "--run-file", "-r",
        help="Path to a specific run record file",
    ),
    run_id: Optional[str] = typer.Option(
        None, "--run-id",
        help="Run ID to verify",
    ),
    last: bool = typer.Option(
        False, "--last",
        help="Use the most recent matching run (no prompt)",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Auto-accept best match (fail if ambiguous)",
    ),
    source: Optional[Path] = typer.Option(
        None, "--source", "-s",
        help="Filter runs by source directory (or source for --reconstruct)",
    ),
    destination: Optional[Path] = typer.Option(
        None, "--destination", "-d",
        help="Filter runs by destination directory (or destination for --reconstruct)",
    ),
    reconstruct: bool = typer.Option(
        False, "--reconstruct",
        help="Reconstruct mapping from source/destination without run record",
    ),
    algorithm: Optional[str] = typer.Option(
        None, "--algorithm", "-a",
        help="Hash algorithm: sha256 (default) or quick",
    ),
    include_dry_runs: bool = typer.Option(
        False, "--include-dry-runs",
        help="Include dry-run records in discovery",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Config file path",
    ),
):
    """
    Verify copy integrity using hash comparison.
    
    Compares source and destination files from a previous apply run.
    By default, auto-discovers the most recent live copy run from .chronoclean/runs/.
    
    Use --reconstruct when you forgot to keep a run record: it rebuilds the
    expected mapping by re-scanning source and applying the same rules.
    
    Examples:
        chronoclean verify                    # Auto-discover and prompt
        chronoclean verify --last             # Use most recent run
        chronoclean verify --run-file run.json  # Use specific file
        chronoclean verify --source /src --destination /dest --reconstruct
    """
    import time
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    # Load configuration
    cfg = ConfigLoader.load(config)
    
    # Determine algorithm
    use_algorithm = algorithm if algorithm else cfg.verify.algorithm
    if use_algorithm not in ("sha256", "quick"):
        console.print(f"[red]Error:[/red] Invalid algorithm: {use_algorithm}")
        console.print("Use 'sha256' or 'quick'.")
        raise typer.Exit(1)
    
    # Handle --reconstruct mode: verify without a run record
    if reconstruct:
        if not source or not destination:
            console.print("[red]Error:[/red] --reconstruct requires both --source and --destination")
            raise typer.Exit(1)
        
        # Validate paths using helpers
        source = validate_source_dir(source, console)
        destination = validate_source_dir(destination, console)  # Destination must exist for reconstruct
        
        console.print("[bold blue]Verification (reconstruct mode)[/bold blue]")
        console.print()
        console.print(f"[dim]Source:[/dim]      {source}")
        console.print(f"[dim]Destination:[/dim] {destination}")
        console.print(f"[dim]Algorithm:[/dim]   {use_algorithm}")
        console.print()
        
        # Import verification models
        from datetime import datetime
        from chronoclean.core.verification import (
            InputSource,
            VerificationReport,
            generate_verify_id,
        )
        
        # Build expected mappings using the SAME pipeline as apply:
        # 1. Create components from config (FolderTagger, ExifReader, VideoReader, DateEngine)
        # 2. Use Scanner to scan files with date inference and folder tag extraction
        # 3. Use Sorter to compute destination folders
        # 4. Use Renamer/ConflictResolver if renaming/tagging enabled
        
        console.print("[dim]Scanning source directory...[/dim]")
        
        # Create components from config using factory
        components = create_scan_components(cfg)
        scanner = components.create_scanner(cfg.general.recursive, cfg.general.include_videos)
        
        scan_result = scanner.scan(source, limit=cfg.scan.limit)
        
        if not scan_result.files:
            console.print("[yellow]No files found in source directory[/yellow]")
            raise typer.Exit(0)
        
        console.print(f"[dim]Found {len(scan_result.files)} files[/dim]")
        
        # Build sorter and renamer (same as apply)
        sorter = Sorter(destination, folder_structure=cfg.sorting.folder_structure)
        
        use_rename = cfg.renaming.enabled
        use_tag_names = cfg.folder_tags.enabled
        
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
        
        # Build expected mappings: [(source_path, expected_dest_path)]
        # Skip files without dates (same as apply - they were never copied)
        expected_mappings: list[tuple[Path, Path]] = []
        skipped_no_date = 0
        
        for record in scan_result.files:
            if not record.detected_date:
                # No date detected - skip (same as apply behavior)
                skipped_no_date += 1
                continue
            
            # Compute destination folder (same as apply)
            dest_folder = sorter.compute_destination_folder(record.detected_date)
            
            # Determine filename (same logic as apply)
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
            
            expected_dest = dest_folder / new_filename
            expected_mappings.append((record.source_path, expected_dest))
        
        if skipped_no_date > 0:
            console.print(f"[dim]Skipped {skipped_no_date} files without dates[/dim]")
        
        if not expected_mappings:
            console.print("[yellow]No files with dates to verify[/yellow]")
            raise typer.Exit(0)
        
        # Create verifier
        verifier = Verifier(
            algorithm=use_algorithm,
            content_search_on_reconstruct=cfg.verify.content_search_on_reconstruct,
        )
        
        # Create verification report
        verify_id = generate_verify_id()
        report = VerificationReport(
            verify_id=verify_id,
            created_at=datetime.now(),
            source_root=str(source),
            destination_root=str(destination),
            input_source=InputSource.RECONSTRUCTED,
            run_id=None,
            hash_algorithm=use_algorithm,
        )
        
        start_time = time.time()
        total_files = len(expected_mappings)
        verify_action = (
            "Hashing (sha256) and comparing..."
            if use_algorithm == "sha256"
            else "Quick check (size-only)..."
        )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(verify_action, total=total_files)
            
            for i, (source_path, expected_dest) in enumerate(expected_mappings):
                # Verify using content search if enabled
                entry = verifier.verify_with_content_search(
                    source_path,
                    expected_dest,
                    destination,
                )
                report.add_entry(entry)
                
                progress.update(
                    task,
                    advance=1,
                    description=f"{verify_action} ({i+1}/{total_files})",
                )
        
        duration = time.time() - start_time
        report.duration_seconds = duration
        
        # Save verification report
        verifications_dir = ensure_verifications_dir(cfg.verify)
        report_filename = get_verification_filename(verify_id)
        report_path = verifications_dir / report_filename
        report_path.write_text(report.to_json(), encoding="utf-8")
        
        # Display results
        console.print()
        console.print("[bold]Verification Results (reconstructed)[/bold]")
        console.print()
        
        summary = report.summary
        console.print(f"  Algorithm:           {use_algorithm}")
        console.print(f"  Total files:         {summary.total}")
        console.print(f"  [green]OK:[/green]                  {summary.ok}")
        console.print(f"  [green]OK (duplicate):[/green]      {summary.ok_existing_duplicate}")
        console.print(f"  [red]Mismatch:[/red]             {summary.mismatch}")
        console.print(f"  [yellow]Missing dest:[/yellow]       {summary.missing_destination}")
        console.print(f"  [yellow]Missing source:[/yellow]     {summary.missing_source}")
        console.print(f"  [red]Errors:[/red]               {summary.error}")
        
        console.print()
        console.print(f"[dim]Duration: {duration:.1f}s[/dim]")
        console.print(f"[dim]Report saved to: {report_path}[/dim]")
        
        console.print()
        cleanup_eligible = summary.cleanup_eligible_count
        not_eligible = summary.total - cleanup_eligible
        if summary.ok + summary.ok_existing_duplicate == summary.total:
            if use_algorithm == "sha256":
                console.print("[green]All files verified (sha256). All entries eligible for cleanup.[/green]")
            else:
                console.print("[yellow]All files passed quick check (size-only). Not eligible for cleanup by default.[/yellow]")
        else:
            if cleanup_eligible > 0:
                console.print(
                    f"[yellow]Partial verification:[/yellow] {cleanup_eligible} files eligible for cleanup; "
                    f"{not_eligible} not eligible (missing/mismatch/error)."
                )
            else:
                console.print("[yellow]No files eligible for cleanup (missing/mismatch/error or quick verification).[/yellow]")
        
        raise typer.Exit(0)
    
    # Find the run record (non-reconstruct mode)
    run_record = None
    run_record_path = None
    
    if run_file:
        # Explicit file path
        run_file = run_file.resolve()
        if not run_file.exists():
            console.print(f"[red]Error:[/red] Run file not found: {run_file}")
            raise typer.Exit(1)
        
        try:
            run_record = load_run_record(run_file)
            run_record_path = run_file
        except Exception as e:
            console.print(f"[red]Error:[/red] Could not load run file: {e}")
            raise typer.Exit(1)
    
    elif run_id:
        # Find by run ID
        found_path = find_run_by_id(cfg.verify, run_id)
        if not found_path:
            console.print(f"[red]Error:[/red] Run ID not found: {run_id}")
            raise typer.Exit(1)
        
        run_record = load_run_record(found_path)
        run_record_path = found_path
    
    else:
        # Auto-discover
        runs = discover_run_records(
            cfg.verify,
            source_filter=source,
            destination_filter=destination,
            include_dry_runs=include_dry_runs,
        )
        
        if not runs:
            console.print("[yellow]No apply runs found in .chronoclean/runs/[/yellow]")
            console.print()
            console.print("Options:")
            console.print("  • Run 'apply' to create a run record")
            console.print("  • Use --run-file to specify a run record directly")
            console.print("  • Use --reconstruct with --source and --destination")
            console.print("  • Use --include-dry-runs to include dry-run records")
            raise typer.Exit(1)
        
        if last or yes:
            # Use most recent
            selected = runs[0]
            if yes and len(runs) > 1:
                # Check for ambiguity when using --yes
                console.print(f"[yellow]Warning:[/yellow] {len(runs)} runs found, using most recent")
            run_record = load_run_record(selected.filepath)
            run_record_path = selected.filepath
        else:
            # Interactive selection
            if len(runs) == 1:
                selected = runs[0]
                console.print(f"Last apply run: [cyan]{selected.age_description}[/cyan], "
                            f"{selected.total_files} files {selected.mode_description}d")
                console.print(f"  Source: {selected.source_root}")
                console.print(f"  Destination: {selected.destination_root}")
                console.print()
                
                confirm = typer.confirm("Use this run?", default=True)
                if not confirm:
                    raise typer.Exit(0)
                
                run_record = load_run_record(selected.filepath)
                run_record_path = selected.filepath
            else:
                # Show list and ask to select
                console.print(f"[blue]Found {len(runs)} apply runs:[/blue]")
                console.print()
                
                for i, run in enumerate(runs[:10], 1):
                    dry_marker = " [dim](dry-run)[/dim]" if run.is_dry_run else ""
                    console.print(f"  {i}. {run.age_description}, {run.total_files} files {run.mode_description}d{dry_marker}")
                    console.print(f"     {run.source_root} → {run.destination_root}")
                
                if len(runs) > 10:
                    console.print(f"  ... and {len(runs) - 10} more")
                
                console.print()
                choice = typer.prompt("Select run number (or 0 to cancel)", default="1")
                
                try:
                    choice_num = int(choice)
                    if choice_num == 0:
                        raise typer.Exit(0)
                    if choice_num < 1 or choice_num > len(runs):
                        console.print("[red]Invalid selection[/red]")
                        raise typer.Exit(1)
                    
                    selected = runs[choice_num - 1]
                    run_record = load_run_record(selected.filepath)
                    run_record_path = selected.filepath
                except ValueError:
                    console.print("[red]Invalid input[/red]")
                    raise typer.Exit(1)
    
    # Display verification info
    console.print()
    console.print(f"[blue]Verifying run:[/blue] {run_record.run_id}")
    console.print(f"  Source: {run_record.source_root}")
    console.print(f"  Destination: {run_record.destination_root}")
    console.print(f"  Algorithm: {use_algorithm}")
    console.print()
    
    verifiable = run_record.verifiable_entries
    if not verifiable:
        console.print("[yellow]No verifiable entries found (no copy operations)[/yellow]")
        if run_record.move_entries:
            console.print(f"[dim]({len(run_record.move_entries)} move operations - sources no longer exist)[/dim]")
        raise typer.Exit(0)
    
    console.print(f"Files to verify: {len(verifiable)}")
    console.print()
    
    # Create verifier
    verifier = Verifier(
        algorithm=use_algorithm,
        content_search_on_reconstruct=cfg.verify.content_search_on_reconstruct,
    )
    
    # Run verification with progress
    verify_action = (
        "Hashing (sha256) and comparing..."
        if use_algorithm == "sha256"
        else "Quick check (size-only)..."
    )
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(verify_action, total=len(verifiable))
        
        def update_progress(current, total):
            progress.update(
                task,
                completed=current,
                description=f"{verify_action} ({current}/{total})",
            )
        
        report = verifier.verify_from_run_record(run_record, progress_callback=update_progress)
    
    # Save verification report
    verifications_dir = ensure_verifications_dir(cfg.verify)
    report_filename = get_verification_filename(report.verify_id)
    report_path = verifications_dir / report_filename
    report_path.write_text(report.to_json(pretty=True), encoding="utf-8")
    
    # Display results
    console.print()
    console.print("[bold]Verification Results:[/bold]")
    console.print(f"  Algorithm: {use_algorithm}")
    console.print(f"  Total files: {report.summary.total}")
    console.print(f"  ✅ OK: {report.summary.ok}")
    console.print(f"  ✅ OK (existing duplicate): {report.summary.ok_existing_duplicate}")
    console.print(f"  ❌ Mismatch: {report.summary.mismatch}")
    console.print(f"  ⚠️  Missing destination: {report.summary.missing_destination}")
    console.print(f"  ⚠️  Missing source: {report.summary.missing_source}")
    console.print(f"  ❗ Errors: {report.summary.error}")
    console.print(f"  ⏭️  Skipped: {report.summary.skipped}")
    
    console.print()
    console.print(f"Duration: {report.duration_seconds:.1f}s")
    console.print(f"Report: {report_path}")
    
    cleanup_eligible = report.summary.cleanup_eligible_count
    not_eligible = report.summary.total - cleanup_eligible
    console.print()
    if report.summary.ok + report.summary.ok_existing_duplicate == report.summary.total:
        if use_algorithm == "sha256":
            console.print("[green]All files verified (sha256). All entries eligible for cleanup.[/green]")
        else:
            console.print("[yellow]All files passed quick check (size-only). Not eligible for cleanup by default.[/yellow]")
    else:
        if cleanup_eligible > 0:
            console.print(
                f"[yellow]Partial verification:[/yellow] {cleanup_eligible} files eligible for cleanup; "
                f"{not_eligible} not eligible (missing/mismatch/error)."
            )
        else:
            console.print("[yellow]No files eligible for cleanup (missing/mismatch/error or quick verification).[/yellow]")
    if cleanup_eligible > 0:
        console.print("Run 'chronoclean cleanup --only ok' to delete verified sources.")


# ============================================================================
# CLEANUP COMMAND (v0.3.1)
# ============================================================================


@app.command()
def cleanup(
    verify_file: Optional[Path] = typer.Option(
        None, "--verify-file", "-v",
        help="Path to a specific verification report file",
    ),
    verify_id: Optional[str] = typer.Option(
        None, "--verify-id",
        help="Verification ID to use",
    ),
    last: bool = typer.Option(
        False, "--last",
        help="Use the most recent matching verification (no prompt)",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Auto-accept best match (fail if ambiguous)",
    ),
    only: str = typer.Option(
        "ok", "--only",
        help="Filter: 'ok' (verified files only)",
    ),
    dry_run: Optional[bool] = typer.Option(
        None, "--dry-run/--no-dry-run",
        help="Simulate without deleting",
        show_default=_bool_show_default(_default_cfg.general.dry_run_default, "dry-run", "no-dry-run"),
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Skip confirmation prompt",
    ),
    source: Optional[Path] = typer.Option(
        None, "--source", "-s",
        help="Filter reports by source directory",
    ),
    destination: Optional[Path] = typer.Option(
        None, "--destination", "-d",
        help="Filter reports by destination directory",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Config file path",
    ),
):
    """
    Delete verified source files (safe cleanup).
    
    Deletes source files from a previous verification where status is OK.
    Only files verified with SHA-256 are eligible for cleanup by default.
    
    Examples:
        chronoclean cleanup --only ok --dry-run     # Preview what would be deleted
        chronoclean cleanup --only ok --no-dry-run  # Actually delete files
        chronoclean cleanup --last --no-dry-run -f  # Delete without prompts
    """
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    # Validate --only filter
    if only != "ok":
        console.print(f"[red]Error:[/red] Only 'ok' filter is supported for cleanup")
        console.print("Other statuses are for reporting/inspection, not deletion.")
        raise typer.Exit(1)
    
    # Load configuration
    cfg = ConfigLoader.load(config)
    
    # Resolve dry_run
    use_dry_run = _resolve_bool(dry_run, cfg.general.dry_run_default)
    
    # Find the verification report
    report = None
    report_path = None
    
    if verify_file:
        # Explicit file path
        verify_file = verify_file.resolve()
        if not verify_file.exists():
            console.print(f"[red]Error:[/red] Verification file not found: {verify_file}")
            raise typer.Exit(1)
        
        try:
            report = load_verification_report(verify_file)
            report_path = verify_file
        except Exception as e:
            console.print(f"[red]Error:[/red] Could not load verification file: {e}")
            raise typer.Exit(1)
    
    elif verify_id:
        # Find by verification ID
        found_path = find_verification_by_id(cfg.verify, verify_id)
        if not found_path:
            console.print(f"[red]Error:[/red] Verification ID not found: {verify_id}")
            raise typer.Exit(1)
        
        report = load_verification_report(found_path)
        report_path = found_path
    
    else:
        # Auto-discover
        verifications = discover_verification_reports(
            cfg.verify,
            source_filter=source,
            destination_filter=destination,
        )
        
        if not verifications:
            console.print("[yellow]No verification reports found in .chronoclean/verifications/[/yellow]")
            console.print()
            console.print("Run 'chronoclean verify' first to verify copy operations.")
            raise typer.Exit(1)
        
        if last or yes:
            # Use most recent
            selected = verifications[0]
            if yes and len(verifications) > 1:
                console.print(f"[yellow]Warning:[/yellow] {len(verifications)} reports found, using most recent")
            report = load_verification_report(selected.filepath)
            report_path = selected.filepath
        else:
            # Interactive selection
            if len(verifications) == 1:
                selected = verifications[0]
                console.print(f"Last verification: [cyan]{selected.age_description}[/cyan]")
                console.print(f"  ✅ OK: {selected.ok_count + selected.ok_duplicate_count}, "
                            f"❌ Issues: {selected.mismatch_count + selected.missing_count}")
                console.print(f"  Source: {selected.source_root}")
                console.print(f"  Destination: {selected.destination_root}")
                console.print()
                
                confirm = typer.confirm("Use this verification?", default=True)
                if not confirm:
                    raise typer.Exit(0)
                
                report = load_verification_report(selected.filepath)
                report_path = selected.filepath
            else:
                # Show list and ask to select
                console.print(f"[blue]Found {len(verifications)} verification reports:[/blue]")
                console.print()
                
                for i, v in enumerate(verifications[:10], 1):
                    console.print(f"  {i}. {v.age_description}, ✅ {v.cleanup_eligible_count} OK / {v.total} total")
                    console.print(f"     {v.source_root}")
                
                if len(verifications) > 10:
                    console.print(f"  ... and {len(verifications) - 10} more")
                
                console.print()
                choice = typer.prompt("Select verification number (or 0 to cancel)", default="1")
                
                try:
                    choice_num = int(choice)
                    if choice_num == 0:
                        raise typer.Exit(0)
                    if choice_num < 1 or choice_num > len(verifications):
                        console.print("[red]Invalid selection[/red]")
                        raise typer.Exit(1)
                    
                    selected = verifications[choice_num - 1]
                    report = load_verification_report(selected.filepath)
                    report_path = selected.filepath
                except ValueError:
                    console.print("[red]Invalid input[/red]")
                    raise typer.Exit(1)
    
    # Create cleaner
    cleaner = Cleaner(
        dry_run=use_dry_run,
        require_sha256=not cfg.verify.allow_cleanup_on_quick,
    )
    
    # Get eligible files
    eligible = cleaner.get_cleanup_eligible(report)
    
    if not eligible:
        console.print("[yellow]No files eligible for cleanup.[/yellow]")
        console.print()
        console.print("Reasons:")
        console.print(f"  • OK entries: {report.summary.ok + report.summary.ok_existing_duplicate}")
        console.print(f"  • Mismatch/missing: {report.summary.mismatch + report.summary.missing_destination + report.summary.missing_source}")
        if report.hash_algorithm != "sha256":
            console.print(f"  • Algorithm: {report.hash_algorithm} (sha256 required for cleanup)")
        raise typer.Exit(0)
    
    # Display cleanup info
    mode_text = "[yellow]DRY RUN[/yellow]" if use_dry_run else "[red]LIVE DELETE[/red]"
    console.print()
    console.print(f"[blue]Cleanup from verification:[/blue] {report.verify_id}")
    console.print(f"Mode: {mode_text}")
    console.print(f"Files eligible for deletion: {len(eligible)}")
    console.print()
    
    # Confirmation for live mode
    if not use_dry_run and not force:
        console.print("[bold red]WARNING: This will permanently delete source files![/bold red]")
        console.print("These files have been verified as successfully copied to the destination.")
        console.print()
        
        confirm = typer.confirm(f"Delete {len(eligible)} source files?", default=False)
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit(0)
    
    # Execute cleanup with progress
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Cleaning up...", total=len(eligible))
        
        def update_progress(current, total):
            progress.update(task, completed=current, description=f"Deleting files ({current}/{total})...")
        
        result = cleaner.cleanup(report, progress_callback=update_progress)
    
    # Display results
    console.print()
    if use_dry_run:
        console.print("[bold yellow]Dry Run Results:[/bold yellow]")
        console.print(f"  Would delete: {result.deleted} files")
        console.print(f"  Would free: {format_bytes(result.bytes_freed)}")
        console.print()
        console.print("Run with --no-dry-run to actually delete files.")
    else:
        console.print("[bold green]Cleanup Complete![/bold green]")
        console.print(f"  Deleted: {result.deleted} files")
        console.print(f"  Freed: {format_bytes(result.bytes_freed)}")
        if result.skipped:
            console.print(f"  [yellow]Skipped: {result.skipped}[/yellow]")
        if result.failed:
            console.print(f"  [red]Failed: {result.failed}[/red]")
            for path, error in result.failed_paths[:5]:
                console.print(f"    • {path.name}: {error}")


# ============================================================================
# DOCTOR COMMAND
# ============================================================================


@app.command()
def doctor(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Config file path",
    ),
    fix: bool = typer.Option(
        False, "--fix",
        help="Interactively fix issues found",
    ),
):
    """
    Check system dependencies and configuration.
    
    Diagnoses the environment for potential issues with ffprobe, hachoir,
    exiftool, and Python package dependencies. Shows which features may
    be affected by missing dependencies.
    
    Use --fix to interactively update configuration for found issues.
    
    Examples:
        chronoclean doctor              # Check all dependencies
        chronoclean doctor --fix        # Check and offer to fix issues
    """
    import shutil
    import sys
    
    from chronoclean.core.video_metadata import (
        is_ffprobe_available,
        is_hachoir_available,
        find_ffprobe_path,
        get_ffprobe_version,
        get_hachoir_version,
    )
    from chronoclean.core.exif_reader import is_exiftool_available, get_exifread_version
    
    # Load configuration
    cfg = ConfigLoader.load(config)
    
    console.print()
    console.print("[bold blue]ChronoClean Doctor[/bold blue]")
    console.print(f"[dim]Checking system dependencies...[/dim]")
    console.print()
    
    # Track issues found
    issues: list[tuple[str, str, str]] = []  # (component, issue, suggestion)
    fixes_available: list[tuple[str, str, str]] = []  # (component, key, value)
    
    # -------------------------------------------------------------------------
    # External Dependencies Table
    # -------------------------------------------------------------------------
    dep_table = Table(title="External Dependencies")
    dep_table.add_column("Component", style="cyan")
    dep_table.add_column("Status", style="white")
    dep_table.add_column("Path / Version", style="dim")
    dep_table.add_column("Affects", style="yellow")
    
    # Check ffprobe
    configured_ffprobe = cfg.video_metadata.ffprobe_path
    ffprobe_available = is_ffprobe_available(configured_ffprobe)
    
    if ffprobe_available:
        ffprobe_version = get_ffprobe_version(configured_ffprobe) or "version unknown"
        ffprobe_path = shutil.which(configured_ffprobe) or configured_ffprobe
        dep_table.add_row(
            "ffprobe",
            "[green]✓ found[/green]",
            f"{ffprobe_path}\n{ffprobe_version[:60]}..." if len(ffprobe_version) > 60 else f"{ffprobe_path}\n{ffprobe_version}",
            "video dates",
        )
    else:
        # Try to find ffprobe elsewhere
        found_path = find_ffprobe_path()
        if found_path and found_path != configured_ffprobe:
            dep_table.add_row(
                "ffprobe",
                "[yellow]⚠ not at configured path[/yellow]",
                f"configured: {configured_ffprobe}\nfound at: {found_path}",
                "video dates",
            )
            issues.append((
                "ffprobe",
                f"Not found at configured path '{configured_ffprobe}'",
                f"Found at '{found_path}'. Update config to use this path.",
            ))
            fixes_available.append(("ffprobe", "video_metadata.ffprobe_path", found_path))
        else:
            dep_table.add_row(
                "ffprobe",
                "[red]✗ not found[/red]",
                f"configured: {configured_ffprobe}",
                "video dates (will use hachoir fallback)",
            )
            issues.append((
                "ffprobe",
                "Not found on system",
                "Install ffmpeg/ffprobe or set video_metadata.ffprobe_path in config.",
            ))
    
    # Check hachoir
    hachoir_available = is_hachoir_available()
    if hachoir_available:
        hachoir_version = get_hachoir_version() or "unknown"
        dep_table.add_row(
            "hachoir",
            "[green]✓ installed[/green]",
            f"version {hachoir_version}",
            "video dates (fallback)",
        )
    else:
        fallback_note = "video dates (no fallback)" if not ffprobe_available else "video dates (fallback disabled)"
        dep_table.add_row(
            "hachoir",
            "[yellow]⚠ not installed[/yellow]",
            "pip install hachoir",
            fallback_note,
        )
        if not ffprobe_available:
            issues.append((
                "hachoir",
                "Not installed (and ffprobe not available)",
                "Install with: pip install hachoir",
            ))
    
    # Check exiftool (optional)
    exiftool_available = is_exiftool_available()
    if exiftool_available:
        dep_table.add_row(
            "exiftool",
            "[green]✓ installed[/green]",
            "pyexiftool package",
            "advanced EXIF (optional)",
        )
    else:
        dep_table.add_row(
            "exiftool",
            "[dim]○ not installed[/dim]",
            "pip install pyexiftool",
            "optional (exifread used)",
        )
    
    console.print(dep_table)
    console.print()
    
    # -------------------------------------------------------------------------
    # Python Packages Table
    # -------------------------------------------------------------------------
    pkg_table = Table(title="Python Packages")
    pkg_table.add_column("Package", style="cyan")
    pkg_table.add_column("Status", style="white")
    pkg_table.add_column("Version", style="dim")
    pkg_table.add_column("Purpose", style="yellow")
    
    # Core packages
    packages = [
        ("exifread", "EXIF metadata reading"),
        ("rich", "Terminal output formatting"),
        ("typer", "CLI framework"),
        ("pyyaml", "Configuration parsing"),
    ]
    
    for pkg_name, purpose in packages:
        try:
            if pkg_name == "pyyaml":
                import yaml
                version = getattr(yaml, "__version__", "unknown")
            elif pkg_name == "exifread":
                version = get_exifread_version()
            else:
                pkg = __import__(pkg_name)
                version = getattr(pkg, "__version__", "unknown")
            pkg_table.add_row(
                pkg_name,
                "[green]✓ installed[/green]",
                version,
                purpose,
            )
        except ImportError:
            pkg_table.add_row(
                pkg_name,
                "[red]✗ missing[/red]",
                "-",
                purpose,
            )
            issues.append((
                pkg_name,
                "Required package not installed",
                f"Install with: pip install {pkg_name}",
            ))
    
    console.print(pkg_table)
    console.print()
    
    # -------------------------------------------------------------------------
    # Configuration Status
    # -------------------------------------------------------------------------
    config_table = Table(title="Configuration")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="white")
    config_table.add_column("Status", style="dim")
    
    # Show active config file
    active_config = None
    for search_path in ConfigLoader.DEFAULT_CONFIG_PATHS:
        if search_path.exists():
            active_config = search_path
            break
    
    if config:
        config_table.add_row("Config file", str(config), "[green]specified via --config[/green]")
    elif active_config:
        config_table.add_row("Config file", str(active_config), "[green]found[/green]")
    else:
        config_table.add_row("Config file", "(none)", "[dim]using defaults[/dim]")
    
    # Video metadata settings
    if cfg.video_metadata.enabled:
        config_table.add_row("Video metadata", "enabled", "[green]✓[/green]")
        config_table.add_row("  Provider", cfg.video_metadata.provider, "")
        config_table.add_row("  ffprobe path", cfg.video_metadata.ffprobe_path, "")
        config_table.add_row("  Fallback to hachoir", str(cfg.video_metadata.fallback_to_hachoir), "")
    else:
        config_table.add_row("Video metadata", "disabled", "[yellow]video dates won't be read[/yellow]")
    
    console.print(config_table)
    console.print()
    
    # -------------------------------------------------------------------------
    # Summary and Issues
    # -------------------------------------------------------------------------
    if issues:
        console.print("[bold yellow]Issues Found:[/bold yellow]")
        for component, issue, suggestion in issues:
            console.print(f"  [yellow]•[/yellow] [bold]{component}:[/bold] {issue}")
            console.print(f"    [dim]→ {suggestion}[/dim]")
        console.print()
        
        # Offer to fix if --fix flag or interactive
        if fix and fixes_available:
            console.print("[bold blue]Available Fixes:[/bold blue]")
            for component, key, value in fixes_available:
                console.print(f"  • Set [cyan]{key}[/cyan] = [green]{value}[/green]")
            console.print()
            
            if typer.confirm("Apply these fixes to configuration?", default=True):
                _apply_config_fixes(fixes_available, console)
        elif fixes_available:
            console.print("[dim]Run with --fix to interactively apply fixes.[/dim]")
            console.print()
    else:
        console.print("[bold green]✓ All dependencies OK![/bold green]")
        console.print()
    
    # Final status
    if not ffprobe_available and not hachoir_available:
        console.print("[red]Warning:[/red] No video metadata provider available.")
        console.print("Video files will use filesystem dates only.")
    elif not ffprobe_available and hachoir_available:
        console.print("[yellow]Note:[/yellow] Using hachoir for video metadata (ffprobe not available).")
    
    console.print()
    console.print(f"[dim]Python {sys.version.split()[0]} | ChronoClean v{__version__}[/dim]")


def _apply_config_fixes(
    fixes: list[tuple[str, str, str]],
    console: Console,
) -> None:
    """Apply configuration fixes by creating/updating config file.
    
    Args:
        fixes: List of (component, key, value) tuples
        console: Rich console for output
    """
    import yaml
    
    # Determine config file location
    config_paths = [
        Path("chronoclean.yaml"),
        Path(".chronoclean/config.yaml"),
    ]
    
    existing_config = None
    for path in config_paths:
        if path.exists():
            existing_config = path
            break
    
    if existing_config:
        console.print(f"[dim]Updating existing config: {existing_config}[/dim]")
        config_path = existing_config
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        except Exception as e:
            console.print(f"[red]Error reading config:[/red] {e}")
            return
    else:
        # Ask where to create
        console.print("No config file found. Where to create?")
        console.print("  1. chronoclean.yaml (current directory)")
        console.print("  2. .chronoclean/config.yaml")
        
        choice = typer.prompt("Choose", default="1")
        if choice == "2":
            config_path = Path(".chronoclean/config.yaml")
            config_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            config_path = Path("chronoclean.yaml")
        
        config_data = {}
    
    # Apply fixes
    for component, key, value in fixes:
        # Parse key like "video_metadata.ffprobe_path" into nested dict
        parts = key.split(".")
        current = config_data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
        console.print(f"  [green]✓[/green] Set {key} = {value}")
    
    # Write config
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        console.print()
        console.print(f"[green]Config saved to:[/green] {config_path}")
    except Exception as e:
        console.print(f"[red]Error writing config:[/red] {e}")


@app.command()
def version():

    """Show ChronoClean version."""
    console.print(f"ChronoClean v{__version__}")


if __name__ == "__main__":
    app()
