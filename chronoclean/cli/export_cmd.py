"""Export commands for ChronoClean CLI."""

from pathlib import Path
from typing import Optional

import typer

from chronoclean.config import ConfigLoader
from chronoclean.config.schema import ChronoCleanConfig
from chronoclean.cli._common import (
    console,
    _default_cfg,
    bool_show_default,
)
from chronoclean.cli.helpers import (
    create_scan_components,
    validate_source_dir,
    resolve_bool,
)
from chronoclean.core.exporter import Exporter


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


def create_export_app() -> typer.Typer:
    """Create and return the export sub-app with all commands registered."""
    
    export_app = typer.Typer(
        name="export",
        help="Export scan results to various formats.",
        no_args_is_help=True,
    )

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
            show_default=bool_show_default(_default_cfg.general.recursive, "recursive", "no-recursive"),
        ),
        videos: Optional[bool] = typer.Option(
            None, "--videos/--no-videos",
            help="Include video files",
            show_default=bool_show_default(_default_cfg.general.include_videos, "videos", "no-videos"),
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
            show_default=bool_show_default(_default_cfg.general.recursive, "recursive", "no-recursive"),
        ),
        videos: Optional[bool] = typer.Option(
            None, "--videos/--no-videos",
            help="Include video files",
            show_default=bool_show_default(_default_cfg.general.include_videos, "videos", "no-videos"),
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

    return export_app
