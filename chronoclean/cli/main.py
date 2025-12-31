"""Main CLI application for ChronoClean.

This module serves as the orchestrator that registers all CLI commands.
Individual commands are implemented in separate modules for maintainability.
"""

import typer

from chronoclean.utils.logging import setup_logging

# Import command registration functions
from chronoclean.cli.scan_cmd import register_scan
from chronoclean.cli.apply_cmd import register_apply
from chronoclean.cli.verify_cmd import register_verify
from chronoclean.cli.cleanup_cmd import register_cleanup
from chronoclean.cli.doctor_cmd import register_doctor
from chronoclean.cli.version_cmd import register_version
from chronoclean.cli.config_cmd import create_config_app
from chronoclean.cli.export_cmd import create_export_app


# Create main app
app = typer.Typer(
    name="chronoclean",
    help="ChronoClean — Restore order to your photo collections.",
    add_completion=False,
    no_args_is_help=True,
)


@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """ChronoClean — Restore order to your photo collections."""
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(level=log_level)


# Register top-level commands
register_scan(app)
register_apply(app)
register_verify(app)
register_cleanup(app)
register_doctor(app)
register_version(app)

# Add sub-apps
app.add_typer(create_config_app(), name="config")
app.add_typer(create_export_app(), name="export")


if __name__ == "__main__":
    app()
