"""Verify command for ChronoClean CLI."""

import time
from pathlib import Path
from typing import Optional
from datetime import datetime

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from chronoclean.config import ConfigLoader
from chronoclean.cli._common import console
from chronoclean.cli.helpers import (
    create_scan_components,
    validate_source_dir,
    resolve_bool,
    build_renamer_context,
    compute_destination_for_record,
)
from chronoclean.core.sorter import Sorter
from chronoclean.core.run_record_writer import ensure_verifications_dir
from chronoclean.core.run_discovery import (
    discover_run_records,
    load_run_record,
    find_run_by_id,
)
from chronoclean.core.verifier import Verifier
from chronoclean.core.verification import (
    InputSource,
    VerificationReport,
    generate_verify_id,
    get_verification_filename,
)


def register_verify(app: typer.Typer) -> None:
    """Register the verify command with the Typer app."""

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
            _verify_reconstruct(source, destination, use_algorithm, cfg)
            return
        
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
                run_record, run_record_path = _select_run_interactive(runs)
        
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
        _display_verification_results(report, use_algorithm, report_path)


def _verify_reconstruct(source: Optional[Path], destination: Optional[Path], algorithm: str, cfg) -> None:
    """Handle --reconstruct mode: verify without a run record."""
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
    console.print(f"[dim]Algorithm:[/dim]   {algorithm}")
    console.print()
    
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
    
    renamer, conflict_resolver = build_renamer_context(cfg, use_rename)
    
    # Build expected mappings: [(source_path, expected_dest_path)]
    expected_mappings: list[tuple[Path, Path]] = []
    skipped_no_date = 0
    
    for record in scan_result.files:
        if not record.detected_date:
            skipped_no_date += 1
            continue
        
        dest_folder, new_filename, renamer = compute_destination_for_record(
            record,
            sorter,
            cfg,
            use_rename=use_rename,
            use_tag_names=use_tag_names,
            renamer=renamer,
            conflict_resolver=conflict_resolver,
        )
        
        expected_dest = dest_folder / new_filename
        expected_mappings.append((record.source_path, expected_dest))
    
    if skipped_no_date > 0:
        console.print(f"[dim]Skipped {skipped_no_date} files without dates[/dim]")
    
    if not expected_mappings:
        console.print("[yellow]No files with dates to verify[/yellow]")
        raise typer.Exit(0)
    
    # Create verifier
    verifier = Verifier(
        algorithm=algorithm,
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
        hash_algorithm=algorithm,
    )
    
    start_time = time.time()
    total_files = len(expected_mappings)
    verify_action = (
        "Hashing (sha256) and comparing..."
        if algorithm == "sha256"
        else "Quick check (size-only)..."
    )
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(verify_action, total=total_files)
        
        for i, (source_path, expected_dest) in enumerate(expected_mappings):
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
    console.print(f"  Algorithm:           {algorithm}")
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
    
    _display_cleanup_eligibility(summary, algorithm)
    
    raise typer.Exit(0)


def _select_run_interactive(runs):
    """Interactive selection of run record."""
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
        return run_record, selected.filepath
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
            return run_record, selected.filepath
        except ValueError:
            console.print("[red]Invalid input[/red]")
            raise typer.Exit(1)


def _display_verification_results(report, algorithm: str, report_path: Path) -> None:
    """Display verification results."""
    console.print()
    console.print("[bold]Verification Results:[/bold]")
    console.print(f"  Algorithm: {algorithm}")
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
    
    _display_cleanup_eligibility(report.summary, algorithm)
    
    cleanup_eligible = report.summary.cleanup_eligible_count
    if cleanup_eligible > 0:
        console.print("Run 'chronoclean cleanup --only ok' to delete verified sources.")


def _display_cleanup_eligibility(summary, algorithm: str) -> None:
    """Display cleanup eligibility message."""
    cleanup_eligible = summary.cleanup_eligible_count
    not_eligible = summary.total - cleanup_eligible
    
    console.print()
    if summary.ok + summary.ok_existing_duplicate == summary.total:
        if algorithm == "sha256":
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
