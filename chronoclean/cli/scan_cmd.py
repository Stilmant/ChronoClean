"""Scan command for ChronoClean CLI."""

import typer
from rich.table import Table

from chronoclean.config import ConfigLoader
from chronoclean.cli._common import console
from chronoclean.cli.helpers import (
    create_scan_components,
    validate_source_dir,
    resolve_bool,
)
from chronoclean.cli.options import (
    SourceScanArg,
    RecursiveOpt,
    VideosOpt,
    LimitOpt,
    ConfigOpt,
)


def register_scan(app: typer.Typer) -> None:
    """Register the scan command with the Typer app."""

    @app.command()
    def scan(
        source: SourceScanArg,
        recursive: RecursiveOpt = None,
        videos: VideosOpt = None,
        limit: LimitOpt = None,
        config: ConfigOpt = None,
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
