"""Export commands for ChronoClean CLI (v0.3.4: with destination computation support)."""

from pathlib import Path
from typing import Annotated, Callable, Optional

import typer
from rich.console import Console

from chronoclean.config import ConfigLoader
from chronoclean.config.schema import ChronoCleanConfig
from chronoclean.cli._common import console
from chronoclean.cli.helpers import (
    build_renamer_context,
    create_scan_components,
    validate_source_dir,
    resolve_bool,
    get_config,
)
from chronoclean.cli.options import (
    SourceScanArg,
    RecursiveOpt,
    VideosOpt,
    LimitOpt,
    ConfigOpt,
)
from chronoclean.core.exporter import Exporter
from chronoclean.core.sorter import Sorter  # v0.3.4: for destination computation
from chronoclean.core.renamer import Renamer, ConflictResolver  # v0.3.4

OutputOpt = Annotated[
    Optional[Path],
    typer.Option("--output", "-o", help="Output file path (default: stdout)"),
]

# v0.3.4: New options for destination-aware export
DestinationOpt = Annotated[
    Optional[Path],
    typer.Option(
        "--destination",
        "-d",
        help="Compute proposed destinations (enables destination-aware mode)",
    ),
]
SampleOpt = Annotated[
    Optional[int],
    typer.Option(
        "--sample",
        help="Compute destinations for only first N files (for performance)",
    ),
]
RenameOpt = Annotated[
    Optional[bool],
    typer.Option(
        "--rename/--no-rename",
        help="Simulate renaming when computing destinations",
    ),
]
TagNamesOpt = Annotated[
    Optional[bool],
    typer.Option(
        "--tag-names/--no-tag-names",
        help="Simulate tag-name appending when computing destinations",
    ),
]
StructureOpt = Annotated[
    Optional[str],
    typer.Option(
        "--structure",
        help="Folder structure for proposed destinations (YYYY/MM, YYYY/MM/DD, etc.)",
    ),
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


def _compute_proposed_destinations(
    result,
    cfg: ChronoCleanConfig,
    destination: Path,
    use_rename: bool,
    use_tag_names: bool,
    folder_structure: str,
    sample: Optional[int] = None,
    status_console: Console = console,
):
    """Compute proposed destinations for scan results (v0.3.4)."""
    # Create sorter with specified structure
    sorter = Sorter(
        base_path=destination,
        folder_structure=folder_structure,
    )
    
    # Create renamer if needed (uses shared helper)
    renamer, conflict_resolver = build_renamer_context(cfg, use_rename)
    
    # Compute destinations
    count = 0
    with status_console.status("[bold blue]Computing proposed destinations..."):
        for record in result.files:
            if sample and count >= sample:
                break
            
            if not record.detected_date:
                continue
            
            # Compute destination folder
            dest_folder = sorter.compute_destination_folder(record.detected_date)
            record.proposed_destination_folder = dest_folder
            
            # Compute filename
            if use_rename and renamer and conflict_resolver:
                tag = record.folder_tag if use_tag_names and record.folder_tag_usable else None
                new_filename = conflict_resolver.resolve(
                    record.source_path,
                    record.detected_date,
                    tag=tag,
                )
                record.proposed_filename = new_filename
            elif use_tag_names and record.folder_tag_usable and record.folder_tag:
                # Tag-only mode
                if not renamer:
                    renamer = Renamer(lowercase_ext=cfg.renaming.lowercase_extensions)
                base = record.source_path.stem
                ext = record.source_path.suffix
                tag_part = renamer.format_tag_part(record.folder_tag)
                record.proposed_filename = f"{base}{tag_part}{ext}"
            else:
                # Keep original filename
                record.proposed_filename = record.source_path.name
            
            count += 1
    
    if sample and count < len(result.files):
        status_console.print(f"[yellow]Note: Computed destinations for {count}/{len(result.files)} files (--sample limit)[/yellow]")


def _print_plain(output: str) -> None:
    print(output, end="")


def _resolve_export_options(
    config: Optional[Path],
    rename: Optional[bool],
    tag_names: Optional[bool],
    structure: Optional[str],
) -> tuple[ChronoCleanConfig, bool, bool, str]:
    """Resolve export command options from CLI args and config.
    
    Returns:
        Tuple of (config, use_rename, use_tag_names, folder_structure)
    """
    cfg = get_config(config)
    use_rename = resolve_bool(rename, cfg.renaming.enabled)
    use_tag_names = resolve_bool(tag_names, cfg.folder_tags.enabled)
    folder_structure = structure or cfg.sorting.folder_structure
    return cfg, use_rename, use_tag_names, folder_structure


def _run_export(
    *,
    source: Path,
    output: Optional[Path],
    recursive: Optional[bool],
    videos: Optional[bool],
    limit: Optional[int],
    config: Optional[Path],
    destination: Optional[Path],  # v0.3.4
    sample: Optional[int],  # v0.3.4
    use_rename: bool,  # v0.3.4
    use_tag_names: bool,  # v0.3.4
    folder_structure: str,  # v0.3.4
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
    
    # v0.3.4: Compute proposed destinations if requested
    if destination:
        _compute_proposed_destinations(
            result,
            cfg,
            destination,
            use_rename,
            use_tag_names,
            folder_structure,
            sample,
            status_console,
        )
    
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
        destination: DestinationOpt = None,  # v0.3.4
        sample: SampleOpt = None,  # v0.3.4
        rename: RenameOpt = None,  # v0.3.4
        tag_names: TagNamesOpt = None,  # v0.3.4
        structure: StructureOpt = None,  # v0.3.4
        statistics: StatisticsOpt = True,
        pretty: PrettyOpt = True,
        config: ConfigOpt = None,
    ):
        """
        Export scan results to JSON format.
        
        Scans the source directory and exports the results to JSON.
        By default outputs to stdout; use --output to write to a file.
        
        v0.3.4: Use --destination to compute proposed target paths.
        """
        cfg, use_rename, use_tag_names, folder_structure = _resolve_export_options(
            config, rename, tag_names, structure
        )
        
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
            destination=destination,
            sample=sample,
            use_rename=use_rename,
            use_tag_names=use_tag_names,
            folder_structure=folder_structure,
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
        destination: DestinationOpt = None,  # v0.3.4
        sample: SampleOpt = None,  # v0.3.4
        rename: RenameOpt = None,  # v0.3.4
        tag_names: TagNamesOpt = None,  # v0.3.4
        structure: StructureOpt = None,  # v0.3.4
        config: ConfigOpt = None,
    ):
        """
        Export scan results to CSV format.
        
        Scans the source directory and exports the results to CSV.
        By default outputs to stdout; use --output to write to a file.
        
        v0.3.4: Use --destination to compute proposed target paths.
        """
        cfg, use_rename, use_tag_names, folder_structure = _resolve_export_options(
            config, rename, tag_names, structure
        )
        
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
            destination=destination,
            sample=sample,
            use_rename=use_rename,
            use_tag_names=use_tag_names,
            folder_structure=folder_structure,
            status_console=stderr_console,
            export_fn=exporter.to_csv,
            output_writer=_print_plain,
        )

    return export_app
