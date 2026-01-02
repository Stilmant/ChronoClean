"""Export commands for ChronoClean CLI."""

from pathlib import Path
from typing import Annotated, Callable, Optional

import typer
from rich.console import Console

from chronoclean.config import ConfigLoader
from chronoclean.config.schema import ChronoCleanConfig
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
from chronoclean.core.exporter import Exporter

OutputOpt = Annotated[
    Optional[Path],
    typer.Option("--output", "-o", help="Output file path (default: stdout)"),
]
StatisticsOpt = Annotated[
    bool,
    typer.Option(
        "--statistics/--no-statistics",
        help="Include summary statistics",
    ),
]
PrettyOpt = Annotated[
    bool,
    typer.Option(
        "--pretty/--compact",
        help="Pretty print JSON output",
    ),
]


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


def _print_plain(output: str) -> None:
    print(output, end="")


def _run_export(
    *,
    source: Path,
    output: Optional[Path],
    recursive: Optional[bool],
    videos: Optional[bool],
    limit: Optional[int],
    config: Optional[Path],
    status_console: Console,
    export_fn: Callable[[object, Optional[Path]], str],
    output_writer: Callable[[str], None],
) -> None:
    cfg = ConfigLoader.load(config)
    
    status_console.print(f"[blue]Scanning:[/blue] {source}")
    if config:
        status_console.print(f"[dim]Config: {config}[/dim]")
    status_console.print()
    
    result = _perform_scan(source, cfg, recursive, videos, limit)
    output_str = export_fn(result, output)
    
    if output:
        status_console.print(f"[green]Exported to:[/green] {output}")
        status_console.print(f"[dim]Files: {len(result.files)}[/dim]")
    else:
        output_writer(output_str)


def create_export_app() -> typer.Typer:
    """Create and return the export sub-app with all commands registered."""
    
    export_app = typer.Typer(
        name="export",
        help="Export scan results to various formats.",
        no_args_is_help=True,
    )

    @export_app.command("json")
    def export_json(
        source: SourceScanArg,
        output: OutputOpt = None,
        recursive: RecursiveOpt = None,
        videos: VideosOpt = None,
        limit: LimitOpt = None,
        statistics: StatisticsOpt = True,
        pretty: PrettyOpt = True,
        config: ConfigOpt = None,
    ):
        """
        Export scan results to JSON format.
        
        Scans the source directory and exports the results to JSON.
        By default outputs to stdout; use --output to write to a file.
        """
        exporter = Exporter(
            include_statistics=statistics,
            pretty_print=pretty,
        )
        _run_export(
            source=source,
            output=output,
            recursive=recursive,
            videos=videos,
            limit=limit,
            config=config,
            status_console=console,
            export_fn=exporter.to_json,
            output_writer=console.print,
        )

    @export_app.command("csv")
    def export_csv(
        source: SourceScanArg,
        output: OutputOpt = None,
        recursive: RecursiveOpt = None,
        videos: VideosOpt = None,
        limit: LimitOpt = None,
        config: ConfigOpt = None,
    ):
        """
        Export scan results to CSV format.
        
        Scans the source directory and exports the results to CSV.
        By default outputs to stdout; use --output to write to a file.
        """
        # Use stderr console for status messages when outputting to stdout
        stderr_console = Console(stderr=True)
        exporter = Exporter()
        _run_export(
            source=source,
            output=output,
            recursive=recursive,
            videos=videos,
            limit=limit,
            config=config,
            status_console=stderr_console,
            export_fn=exporter.to_csv,
            output_writer=_print_plain,
        )

    return export_app
