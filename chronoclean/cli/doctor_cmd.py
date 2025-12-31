"""Doctor command for ChronoClean CLI."""

import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.table import Table

from chronoclean import __version__
from chronoclean.config import ConfigLoader
from chronoclean.cli._common import console
from chronoclean.core.video_metadata import (
    is_ffprobe_available,
    is_hachoir_available,
    find_ffprobe_path,
    get_ffprobe_version,
    get_hachoir_version,
)
from chronoclean.core.exif_reader import is_exiftool_available, get_exifread_version


def register_doctor(app: typer.Typer) -> None:
    """Register the doctor command with the Typer app."""

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
    console,
) -> None:
    """Apply configuration fixes by creating/updating config file.
    
    Args:
        fixes: List of (component, key, value) tuples
        console: Rich console for output
    """
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
