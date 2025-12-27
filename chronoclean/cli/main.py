"""Main CLI application for ChronoClean."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from chronoclean import __version__
from chronoclean.config import ConfigLoader
from chronoclean.config.schema import ChronoCleanConfig
from chronoclean.core.scanner import Scanner
from chronoclean.core.sorter import Sorter
from chronoclean.core.renamer import Renamer, ConflictResolver
from chronoclean.core.folder_tagger import FolderTagger
from chronoclean.core.date_inference import DateInferenceEngine
from chronoclean.core.file_operations import FileOperations, BatchOperations
from chronoclean.core.models import OperationPlan
from chronoclean.utils.logging import setup_logging

app = typer.Typer(
    name="chronoclean",
    help="ChronoClean — Restore order to your photo collections.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()


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
    recursive: Optional[bool] = typer.Option(None, "--recursive/--no-recursive", help="Scan subfolders"),
    videos: Optional[bool] = typer.Option(None, "--videos/--no-videos", help="Include video files"),
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
    folder_tagger = FolderTagger(
        ignore_list=cfg.folder_tags.ignore_list,
        force_list=cfg.folder_tags.force_list,
        min_length=cfg.folder_tags.min_length,
        max_length=cfg.folder_tags.max_length,
        distance_threshold=cfg.folder_tags.distance_threshold,
    )
    
    date_engine = DateInferenceEngine(
        priority=cfg.sorting.fallback_date_priority,
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


@app.command()
def apply(
    source: Path = typer.Argument(..., help="Source directory"),
    destination: Path = typer.Argument(..., help="Destination directory"),
    dry_run: Optional[bool] = typer.Option(None, "--dry-run/--no-dry-run", help="Simulate without changes"),
    move: bool = typer.Option(False, "--move", help="Move files instead of copy (default: copy)"),
    rename: Optional[bool] = typer.Option(None, "--rename/--no-rename", help="Enable file renaming"),
    tag_names: Optional[bool] = typer.Option(None, "--tag-names/--no-tag-names", help="Add folder tags"),
    recursive: Optional[bool] = typer.Option(None, "--recursive/--no-recursive", help="Scan subfolders"),
    videos: Optional[bool] = typer.Option(None, "--videos/--no-videos", help="Include video files"),
    structure: Optional[str] = typer.Option(None, "--structure", "-s", help="Folder structure"),
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
    
    date_engine = DateInferenceEngine(
        priority=cfg.sorting.fallback_date_priority,
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
            tag = record.folder_tag if use_tag_names and record.folder_tag_usable else None
            new_filename = conflict_resolver.resolve(
                record.source_path,
                record.detected_date,
                tag=tag,
            )
        else:
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
        file_ops = FileOperations(dry_run=False)
        batch = BatchOperations(file_ops, dry_run=False)

        operations = [(op.source, op.destination_path) for op in plan.moves]
        
        if move:
            success, failed = batch.execute_moves(operations)
            action_word = "moved"
        else:
            success, failed = batch.execute_copies(operations)
            action_word = "copied"

        console.print()
        console.print("[bold green]Complete![/bold green]")
        console.print(f"  Successfully {action_word}: {success}")
        if failed:
            console.print(f"  [red]Failed: {failed}[/red]")


@app.command()
def version():
    """Show ChronoClean version."""
    console.print(f"ChronoClean v{__version__}")


if __name__ == "__main__":
    app()
