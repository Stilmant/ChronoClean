"""CLI commands for folder tag management (v0.3.4)."""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from chronoclean.cli.helpers import (
    create_scan_components,
    get_config,
    validate_source_dir,
)
from chronoclean.cli._common import console as default_console
from chronoclean.core.tag_rules_store import TagRulesStore

console = Console()
err_console = Console(stderr=True)


def create_tags_app() -> typer.Typer:
    """Create the tags command group."""
    tags_app = typer.Typer(
        name="tags",
        help="Folder tag management commands.",
        no_args_is_help=True,
    )

    @tags_app.command("list")
    def tags_list(
        source: Path = typer.Argument(
            ...,
            help="Source directory to scan",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
        recursive: bool = typer.Option(
            True,
            "--recursive/--no-recursive",
            help="Scan subdirectories recursively",
        ),
        videos: bool = typer.Option(
            True,
            "--videos/--no-videos",
            help="Include video files",
        ),
        limit: Optional[int] = typer.Option(
            None,
            "--limit",
            help="Limit number of files to scan (for testing)",
        ),
        samples: int = typer.Option(
            3,
            "--samples",
            help="Number of sample file paths to show per tag",
        ),
        show_ignored: bool = typer.Option(
            True,
            "--show-ignored/--no-show-ignored",
            help="Show ignored folder names",
        ),
        output_format: str = typer.Option(
            "text",
            "--format",
            help="Output format: text or json",
        ),
        output_file: Optional[Path] = typer.Option(
            None,
            "--output",
            "-o",
            help="Output file path (default: stdout)",
        ),
        config_path: Optional[Path] = typer.Option(
            None,
            "--config",
            "-c",
            help="Path to config file",
        ),
    ):
        """
        List folder tag classifications from a scan.
        
        Shows which folder names will be used as tags and which will be ignored,
        with reasons and sample file paths.
        """
        try:
            # Validate and load config
            source = validate_source_dir(source, err_console)
            cfg = get_config(config_path)
            
            # Create scanner with tag rules store
            components = create_scan_components(cfg)
            scanner = components.create_scanner(recursive, videos)
            
            # Scan directory
            err_console.print(f"[blue]Scanning {source}...[/blue]")
            result = scanner.scan(source, limit=limit)
            err_console.print(f"[green]✓ Scanned {result.processed_files} files[/green]")
            
            # Aggregate tag candidates and ignored folders
            tag_candidates = defaultdict(lambda: {"count": 0, "samples": []})
            ignored_folders = defaultdict(lambda: {"count": 0, "reason": None, "samples": []})
            
            for record in result.files:
                # Collect tags that were applied
                if record.folder_tags:
                    for tag in record.folder_tags:
                        tag_candidates[tag]["count"] += 1
                        if len(tag_candidates[tag]["samples"]) < samples:
                            tag_candidates[tag]["samples"].append(str(record.source_path))
                
                # Collect folders that were checked but ignored
                if record.source_folder_name and not record.folder_tags:
                    folder = record.source_folder_name
                    # Get the reason from folder_tagger
                    usable, reason = scanner.folder_tagger.classify_folder(folder)
                    if not usable:
                        ignored_folders[folder]["count"] += 1
                        ignored_folders[folder]["reason"] = reason
                        if len(ignored_folders[folder]["samples"]) < samples:
                            ignored_folders[folder]["samples"].append(str(record.source_path))
            
            # Output results
            if output_format == "json":
                output_data = {
                    "tag_candidates": [
                        {
                            "tag": tag,
                            "count": data["count"],
                            "samples": data["samples"],
                        }
                        for tag, data in sorted(tag_candidates.items())
                    ],
                    "ignored_folders": [
                        {
                            "folder_name": folder,
                            "reason": data["reason"],
                            "count": data["count"],
                            "samples": data["samples"],
                        }
                        for folder, data in sorted(ignored_folders.items())
                    ] if show_ignored else [],
                }
                
                json_str = json.dumps(output_data, indent=2)
                
                if output_file:
                    output_file.write_text(json_str, encoding="utf-8")
                    console.print(f"[green]✓ Exported to {output_file}[/green]")
                else:
                    print(json_str)
            
            else:  # text format
                # Will tag section
                if tag_candidates:
                    table = Table(title="[bold green]Will Tag[/bold green]", show_lines=True)
                    table.add_column("Tag", style="cyan", no_wrap=True)
                    table.add_column("Count", justify="right", style="magenta")
                    table.add_column("Sample Files", style="dim")
                    
                    for tag, data in sorted(tag_candidates.items()):
                        sample_str = "\n".join(data["samples"][:samples])
                        table.add_row(tag, str(data["count"]), sample_str)
                    
                    console.print(table)
                    console.print()
                else:
                    console.print("[yellow]No tags detected[/yellow]\n")
                
                # Ignored section
                if show_ignored and ignored_folders:
                    table = Table(title="[bold red]Ignored[/bold red]", show_lines=True)
                    table.add_column("Folder Name", style="cyan", no_wrap=True)
                    table.add_column("Reason", style="yellow")
                    table.add_column("Count", justify="right", style="magenta")
                    table.add_column("Sample Files", style="dim")
                    
                    for folder, data in sorted(ignored_folders.items()):
                        sample_str = "\n".join(data["samples"][:samples])
                        table.add_row(
                            folder,
                            data["reason"] or "unknown",
                            str(data["count"]),
                            sample_str,
                        )
                    
                    console.print(table)
                
                if output_file:
                    console.print(f"\n[yellow]Note: Text format written to stdout. Use --format json for file output.[/yellow]")
        
        except Exception as e:
            err_console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)

    @tags_app.command("classify")
    def tags_classify(
        folder_name: str = typer.Argument(
            ...,
            help="Folder name to classify",
        ),
        action: str = typer.Argument(
            ...,
            help="Action: use, ignore, or clear",
        ),
        tag: Optional[str] = typer.Option(
            None,
            "--tag",
            help="Custom tag text (alias) - only valid with 'use' action",
        ),
        rules_path: Optional[Path] = typer.Option(
            None,
            "--rules-path",
            help="Path to tag_rules.yaml (default: .chronoclean/tag_rules.yaml)",
        ),
    ):
        """
        Classify a folder name for tagging.
        
        Actions:
        - use: Mark folder name as always usable (with optional alias)
        - ignore: Mark folder name as always ignored
        - clear: Remove any classification (return to heuristics)
        
        Examples:
          chronoclean tags classify "Paris 2022" use
          chronoclean tags classify "Paris 2022" use --tag "ParisTrip"
          chronoclean tags classify "tosort" ignore
          chronoclean tags classify "Paris 2022" clear
        """
        action = action.lower()
        
        if action not in ("use", "ignore", "clear"):
            err_console.print(f"[red]Error: Invalid action '{action}'. Must be: use, ignore, or clear[/red]")
            raise typer.Exit(code=1)
        
        if tag and action != "use":
            err_console.print(f"[red]Error: --tag option is only valid with 'use' action[/red]")
            raise typer.Exit(code=1)
        
        try:
            # Load tag rules store
            store = TagRulesStore(rules_path)
            
            # Apply action
            if action == "use":
                store.add_use(folder_name, alias=tag)
                if tag:
                    console.print(f"[green]✓ Marked '{folder_name}' as usable with alias '{tag}'[/green]")
                else:
                    console.print(f"[green]✓ Marked '{folder_name}' as usable[/green]")
            
            elif action == "ignore":
                store.add_ignore(folder_name)
                console.print(f"[green]✓ Marked '{folder_name}' as ignored[/green]")
            
            elif action == "clear":
                store.clear(folder_name)
                console.print(f"[green]✓ Cleared classification for '{folder_name}'[/green]")
            
            console.print(f"[dim]Saved to: {store.rules_path}[/dim]")
        
        except Exception as e:
            err_console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(code=1)

    return tags_app
