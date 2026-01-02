"""Shared CLI option definitions."""

from pathlib import Path
from typing import Annotated, Optional

import typer

from chronoclean.cli._common import _default_cfg, bool_show_default

SourceScanArg = Annotated[Path, typer.Argument(help="Source directory to scan")]
RecursiveOpt = Annotated[
    Optional[bool],
    typer.Option(
        "--recursive/--no-recursive",
        help="Scan subfolders",
        show_default=bool_show_default(_default_cfg.general.recursive, "recursive", "no-recursive"),
    ),
]
VideosOpt = Annotated[
    Optional[bool],
    typer.Option(
        "--videos/--no-videos",
        help="Include video files",
        show_default=bool_show_default(_default_cfg.general.include_videos, "videos", "no-videos"),
    ),
]
LimitOpt = Annotated[
    Optional[int],
    typer.Option("--limit", "-l", help="Limit files (for debugging)"),
]
ConfigOpt = Annotated[
    Optional[Path],
    typer.Option("--config", "-c", help="Config file path"),
]
