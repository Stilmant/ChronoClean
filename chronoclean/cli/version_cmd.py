"""Version command for ChronoClean CLI."""

import typer

from chronoclean import __version__
from chronoclean.cli._common import console


def register_version(app: typer.Typer) -> None:
    """Register the version command with the Typer app."""

    @app.command()
    def version():
        """Show ChronoClean version."""
        console.print(f"ChronoClean v{__version__}")
