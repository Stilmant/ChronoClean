"""Config commands for ChronoClean CLI."""

from pathlib import Path
from typing import Optional

import typer
import yaml
from dataclasses import asdict

from chronoclean.config import ConfigLoader
from chronoclean.config.templates import get_config_template
from chronoclean.cli._common import console


def create_config_app() -> typer.Typer:
    """Create and return the config sub-app with all commands registered."""
    
    config_app = typer.Typer(
        name="config",
        help="Configuration management commands.",
        no_args_is_help=True,
    )

    @config_app.command("init")
    def config_init(
        output: Path = typer.Option(
            Path("chronoclean.yaml"),
            "--output", "-o",
            help="Output file path",
        ),
        full: bool = typer.Option(
            False,
            "--full",
            help="Generate full config with all options (default: minimal)",
        ),
        force: bool = typer.Option(
            False,
            "--force", "-f",
            help="Overwrite existing config file",
        ),
    ):
        """
        Initialize a new configuration file.
        
        Creates a chronoclean.yaml file in the current directory (or specified path).
        Use --full to generate a complete config with all options documented.
        """
        output = output.resolve()
        
        # Check if file exists
        if output.exists() and not force:
            console.print(f"[yellow]Config file already exists:[/yellow] {output}")
            console.print("Use --force to overwrite.")
            raise typer.Exit(1)
        
        # Get template
        template = get_config_template(full=full)
        
        # Write file
        try:
            output.write_text(template, encoding="utf-8")
            console.print(f"[green]Created config file:[/green] {output}")
            
            if full:
                console.print("[dim]Full configuration with all options documented.[/dim]")
            else:
                console.print("[dim]Minimal configuration. Edit to customize.[/dim]")
            
            console.print()
            console.print("Next steps:")
            console.print(f"  1. Edit {output.name} to customize settings")
            console.print("  2. Run: chronoclean scan <source>")
            
        except OSError as e:
            console.print(f"[red]Error writing config file:[/red] {e}")
            raise typer.Exit(1)

    @config_app.command("show")
    def config_show(
        config: Optional[Path] = typer.Option(
            None,
            "--config", "-c",
            help="Config file path (default: auto-detect)",
        ),
        section: Optional[str] = typer.Option(
            None,
            "--section", "-s",
            help="Show only specific section (e.g., 'sorting', 'folder_tags')",
        ),
    ):
        """
        Show current configuration.
        
        Displays the effective configuration from config file merged with defaults.
        """
        # Load config
        cfg = ConfigLoader.load(config)
        
        # Convert to dict for display
        config_dict = asdict(cfg)
        
        # Filter to section if specified
        if section:
            if section not in config_dict:
                console.print(f"[red]Unknown section:[/red] {section}")
                console.print(f"Available sections: {', '.join(config_dict.keys())}")
                raise typer.Exit(1)
            config_dict = {section: config_dict[section]}
        
        # Display
        console.print("[bold]ChronoClean Configuration[/bold]")
        console.print()
        
        if config:
            console.print(f"[dim]Source: {config}[/dim]")
        else:
            # Check which file was found
            for search_path in ConfigLoader.DEFAULT_CONFIG_PATHS:
                if search_path.exists():
                    console.print(f"[dim]Source: {search_path}[/dim]")
                    break
            else:
                console.print("[dim]Source: built-in defaults[/dim]")
        
        console.print()
        
        # Pretty print as YAML
        yaml_output = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
        console.print(yaml_output)

    @config_app.command("path")
    def config_path():
        """
        Show where ChronoClean looks for config files.
        """
        console.print("[bold]Config file search paths:[/bold]")
        console.print()
        
        found = False
        for i, search_path in enumerate(ConfigLoader.DEFAULT_CONFIG_PATHS, 1):
            exists = search_path.exists()
            if exists and not found:
                status = "[green]✓ ACTIVE[/green]"
                found = True
            elif exists:
                status = "[yellow]exists (not used)[/yellow]"
            else:
                status = "[dim]not found[/dim]"
            
            console.print(f"  {i}. {search_path} {status}")
        
        if not found:
            console.print()
            console.print("[dim]No config file found. Using built-in defaults.[/dim]")
            console.print("Run 'chronoclean config init' to create one.")

    return config_app
