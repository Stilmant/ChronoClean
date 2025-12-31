"""Tests for version CLI command."""

from typer.testing import CliRunner

from chronoclean import __version__
from chronoclean.cli.main import app


runner = CliRunner()


class TestVersionCommand:
    """Tests for 'chronoclean version' command."""
    
    def test_version_shows_version_number(self):
        """version command displays current version."""
        result = runner.invoke(app, ["version"])
        
        assert result.exit_code == 0
        assert __version__ in result.stdout
        assert "ChronoClean" in result.stdout
    
    def test_version_format(self):
        """version output has expected format."""
        result = runner.invoke(app, ["version"])
        
        assert result.exit_code == 0
        # Should be "ChronoClean v0.3.3" format
        assert f"v{__version__}" in result.stdout
