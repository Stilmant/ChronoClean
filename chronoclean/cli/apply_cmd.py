"""Apply command for ChronoClean CLI."""

from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from chronoclean.config import ConfigLoader
from chronoclean.cli._common import (
    console,
    _default_cfg,
    _cfg_note,
    bool_show_default,
)
from chronoclean.cli.helpers import (
    create_scan_components,
    validate_source_dir,
    validate_destination_dir,
    resolve_bool,
    build_renamer_context,
    compute_destination_for_record,
)
from chronoclean.cli.options import RecursiveOpt, VideosOpt, ConfigOpt
from chronoclean.core.sorter import Sorter
from chronoclean.core.file_operations import FileOperations, BatchOperations, FileOperationError
from chronoclean.core.models import OperationPlan
from chronoclean.core.duplicate_checker import DuplicateChecker
from chronoclean.core.run_record_writer import RunRecordWriter


def register_apply(app: typer.Typer) -> None:
    """Register the apply command with the Typer app."""

    @app.command()
    def apply(
        source: Path = typer.Argument(..., help="Source directory"),
        destination: Path = typer.Argument(..., help="Destination directory"),
        dry_run: Optional[bool] = typer.Option(
            None, "--dry-run/--no-dry-run",
            help="Simulate without changes",
            show_default=bool_show_default(_default_cfg.general.dry_run_default, "dry-run", "no-dry-run"),
        ),
        move: bool = typer.Option(False, "--move", help="Move files instead of copy (default: copy)"),
        rename: Optional[bool] = typer.Option(
            None, "--rename/--no-rename",
            help="Enable file renaming",
            show_default=bool_show_default(_default_cfg.renaming.enabled, "rename", "no-rename"),
        ),
        tag_names: Optional[bool] = typer.Option(
            None, "--tag-names/--no-tag-names",
            help="Add folder tags to filenames (works with or without --rename)",
            show_default=bool_show_default(_default_cfg.folder_tags.enabled, "tag-names", "no-tag-names"),
        ),
        recursive: RecursiveOpt = None,
        videos: VideosOpt = None,
        structure: Optional[str] = typer.Option(
            None, "--structure", "-s",
            help="Folder structure",
            show_default=f"{_default_cfg.sorting.folder_structure}{_cfg_note}",
        ),
        force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
        limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Limit files"),
        config: ConfigOpt = None,
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
        
        renamer, conflict_resolver = build_renamer_context(cfg, use_rename)

        plan = OperationPlan()
        files_with_dates = 0
        files_without_dates = 0

        for record in scan_result.files:
            if not record.detected_date:
                files_without_dates += 1
                plan.add_skip(record.source_path, "No date detected")
                continue

            files_with_dates += 1

            dest_folder, new_filename, renamer = compute_destination_for_record(
                record,
                sorter,
                cfg,
                use_rename=use_rename,
                use_tag_names=use_tag_names,
                renamer=renamer,
                conflict_resolver=conflict_resolver,
            )

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
