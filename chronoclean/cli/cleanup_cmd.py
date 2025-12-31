"""Cleanup command for ChronoClean CLI."""

from pathlib import Path
from typing import Optional

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from chronoclean.config import ConfigLoader
from chronoclean.cli._common import (
    console,
    _default_cfg,
    bool_show_default,
)
from chronoclean.cli.helpers import resolve_bool
from chronoclean.core.run_discovery import (
    discover_verification_reports,
    load_verification_report,
    find_verification_by_id,
)
from chronoclean.core.cleaner import Cleaner, format_bytes


def register_cleanup(app: typer.Typer) -> None:
    """Register the cleanup command with the Typer app."""

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
            show_default=bool_show_default(_default_cfg.general.dry_run_default, "dry-run", "no-dry-run"),
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
        # Validate --only filter
        if only != "ok":
            console.print(f"[red]Error:[/red] Only 'ok' filter is supported for cleanup")
            console.print("Other statuses are for reporting/inspection, not deletion.")
            raise typer.Exit(1)
        
        # Load configuration
        cfg = ConfigLoader.load(config)
        
        # Resolve dry_run
        use_dry_run = resolve_bool(dry_run, cfg.general.dry_run_default)
        
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
                report, report_path = _select_verification_interactive(verifications)
        
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


def _select_verification_interactive(verifications):
    """Interactive selection of verification report."""
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
        return report, selected.filepath
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
            return report, selected.filepath
        except ValueError:
            console.print("[red]Invalid input[/red]")
            raise typer.Exit(1)
