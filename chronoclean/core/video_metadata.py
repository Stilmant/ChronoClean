"""Video metadata extraction for ChronoClean.

This module provides video metadata extraction using either ffprobe (preferred)
or hachoir (pure Python fallback). The primary use case is extracting the
creation/recording date from video files.

v0.3 feature.
"""

import json
import logging
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Common date formats found in video metadata
VIDEO_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ",      # 2024-03-15T14:30:00.000000Z (ISO with microseconds)
    "%Y-%m-%dT%H:%M:%SZ",         # 2024-03-15T14:30:00Z (ISO)
    "%Y-%m-%dT%H:%M:%S%z",        # 2024-03-15T14:30:00+00:00 (ISO with timezone)
    "%Y-%m-%dT%H:%M:%S.%f%z",     # 2024-03-15T14:30:00.000000+00:00
    "%Y-%m-%d %H:%M:%S",          # 2024-03-15 14:30:00 (common)
    "%Y:%m:%d %H:%M:%S",          # 2024:03:15 14:30:00 (EXIF-like)
    "%Y/%m/%d %H:%M:%S",          # 2024/03/15 14:30:00
    "%d/%m/%Y %H:%M:%S",          # 15/03/2024 14:30:00
    "%Y-%m-%d",                   # 2024-03-15 (date only)
]


def parse_video_date(value: Optional[str]) -> Optional[datetime]:
    """Parse a date string using known video date formats.
    
    Standalone function for testing and external use.
    
    Args:
        value: Date string to parse
        
    Returns:
        datetime if successfully parsed, None otherwise
    """
    if not value or not isinstance(value, str):
        return None
    
    value = value.strip()
    
    # Handle timezone offset format differences
    # Convert +0000 to +00:00 for Python's %z
    value = re.sub(r'([+-])(\d{2})(\d{2})$', r'\1\2:\3', value)
    
    for fmt in VIDEO_DATE_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            # Return naive datetime (strip timezone for consistency)
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    
    logger.debug(f"Could not parse date string: {value}")
    return None


class VideoMetadataReader:
    """Extract metadata from video files.
    
    Supports two providers:
    - ffprobe (preferred): Fast, accurate, handles all formats
    - hachoir (fallback): Pure Python, no external dependencies
    
    Example:
        reader = VideoMetadataReader(provider="ffprobe")
        date = reader.get_creation_date(Path("video.mp4"))
    """

    def __init__(
        self,
        provider: str = "ffprobe",
        ffprobe_path: str = "ffprobe",
        fallback_to_hachoir: bool = True,
        skip_errors: bool = True,
    ):
        """Initialize the video metadata reader.
        
        Args:
            provider: Metadata provider ("ffprobe" or "hachoir")
            ffprobe_path: Path to ffprobe binary (default: "ffprobe" from PATH)
            fallback_to_hachoir: If ffprobe fails/unavailable, try hachoir
            skip_errors: If True, return None on errors instead of raising
        """
        self.provider = provider
        self.ffprobe_path = ffprobe_path
        self.fallback_to_hachoir = fallback_to_hachoir
        self.skip_errors = skip_errors
        
        # Check ffprobe availability
        self._ffprobe_available: Optional[bool] = None
        self._hachoir_available: Optional[bool] = None

    def _check_ffprobe(self) -> bool:
        """Check if ffprobe is available."""
        if self._ffprobe_available is not None:
            return self._ffprobe_available
        
        self._ffprobe_available = shutil.which(self.ffprobe_path) is not None
        if not self._ffprobe_available:
            logger.debug(f"ffprobe not found at '{self.ffprobe_path}'")
        return self._ffprobe_available

    def _check_hachoir(self) -> bool:
        """Check if hachoir is available."""
        if self._hachoir_available is not None:
            return self._hachoir_available
        
        try:
            import hachoir  # noqa: F401
            self._hachoir_available = True
        except ImportError:
            self._hachoir_available = False
            logger.debug("hachoir package not installed")
        return self._hachoir_available

    def get_creation_date(self, path: Path) -> Optional[datetime]:
        """Extract creation/recording date from video metadata.
        
        Args:
            path: Path to the video file
            
        Returns:
            datetime if found, None otherwise
        """
        if not path.exists():
            logger.warning(f"Video file not found: {path}")
            return None

        # Try primary provider
        if self.provider == "ffprobe":
            date = self._ffprobe_date(path)
            if date:
                return date
            # Fallback to hachoir if enabled
            if self.fallback_to_hachoir and self._check_hachoir():
                logger.debug(f"ffprobe failed for {path.name}, trying hachoir")
                return self._hachoir_date(path)
        elif self.provider == "hachoir":
            date = self._hachoir_date(path)
            if date:
                return date
            # Fallback to ffprobe if enabled
            if self.fallback_to_hachoir and self._check_ffprobe():
                logger.debug(f"hachoir failed for {path.name}, trying ffprobe")
                return self._ffprobe_date(path)
        else:
            logger.warning(f"Unknown video metadata provider: {self.provider}")
        
        return None

    def _ffprobe_date(self, path: Path) -> Optional[datetime]:
        """Extract creation date using ffprobe.
        
        Checks these metadata fields in order:
        1. creation_time (QuickTime/MP4)
        2. com.apple.quicktime.creationdate (Apple devices)
        3. date / DATE tags
        """
        if not self._check_ffprobe():
            if not self.skip_errors:
                logger.warning(f"ffprobe not available for {path.name}")
            return None
        
        try:
            # Run ffprobe to get format and stream metadata as JSON
            cmd = [
                self.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(path),
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                if not self.skip_errors:
                    logger.warning(f"ffprobe returned non-zero for {path.name}: {result.stderr}")
                else:
                    logger.debug(f"ffprobe returned non-zero for {path.name}: {result.stderr}")
                return None
            
            data = json.loads(result.stdout)
            
            # Look for creation_time in format tags (most common location)
            format_tags = data.get("format", {}).get("tags", {})
            
            # Fields to check, in priority order
            date_fields = [
                "creation_time",
                "com.apple.quicktime.creationdate",
                "date",
                "DATE",
                "DateTimeOriginal",
            ]
            
            for field in date_fields:
                # Check format tags (case-insensitive)
                for key, value in format_tags.items():
                    if key.lower() == field.lower():
                        date = self._parse_date(value)
                        if date:
                            logger.debug(f"Found date in format.tags.{key}: {value}")
                            return date
            
            # Also check stream tags
            for stream in data.get("streams", []):
                stream_tags = stream.get("tags", {})
                for field in date_fields:
                    for key, value in stream_tags.items():
                        if key.lower() == field.lower():
                            date = self._parse_date(value)
                            if date:
                                logger.debug(f"Found date in stream.tags.{key}: {value}")
                                return date
            
            logger.debug(f"No creation date found in ffprobe output for {path.name}")
            return None
            
        except subprocess.TimeoutExpired:
            if self.skip_errors:
                logger.debug(f"ffprobe timed out for {path.name}")
            else:
                logger.warning(f"ffprobe timed out for {path.name}")
            return None
        except json.JSONDecodeError as e:
            if self.skip_errors:
                logger.debug(f"Failed to parse ffprobe JSON output for {path.name}: {e}")
            else:
                logger.warning(f"Failed to parse ffprobe JSON output for {path.name}: {e}")
            return None
        except Exception as e:
            if self.skip_errors:
                logger.debug(f"ffprobe error for {path.name}: {e}")
                return None
            raise

    def _hachoir_date(self, path: Path) -> Optional[datetime]:
        """Extract creation date using hachoir library."""
        if not self._check_hachoir():
            if not self.skip_errors:
                logger.warning(f"hachoir not available for {path.name}")
            return None
        
        try:
            from hachoir.metadata import extractMetadata
            from hachoir.parser import createParser
            
            parser = createParser(str(path))
            if not parser:
                logger.debug(f"hachoir could not parse {path.name}")
                return None
            
            with parser:
                metadata = extractMetadata(parser)
                if not metadata:
                    logger.debug(f"hachoir found no metadata in {path.name}")
                    return None
                
                # Try to get creation date
                # hachoir returns metadata as a list of items
                for item in metadata.exportPlaintext():
                    # Look for date-related fields
                    if "creation date" in item.lower() or "date" in item.lower():
                        # Extract the value part after the colon
                        if ":" in item:
                            value = item.split(":", 1)[1].strip()
                            date = self._parse_date(value)
                            if date:
                                logger.debug(f"Found date via hachoir: {value}")
                                return date
                
                # Alternative: Try direct attribute access
                if hasattr(metadata, 'get'):
                    for attr in ['creation_date', 'date_time_original', 'last_modification']:
                        value = metadata.get(attr)
                        if value:
                            if isinstance(value, datetime):
                                return value
                            date = self._parse_date(str(value))
                            if date:
                                return date
            
            return None
            
        except Exception as e:
            if self.skip_errors:
                logger.debug(f"hachoir error for {path.name}: {e}")
                return None
            raise

    def _parse_date(self, value: str) -> Optional[datetime]:
        """Parse a date string using known video date formats.
        
        Args:
            value: Date string to parse
            
        Returns:
            datetime if successfully parsed, None otherwise
        """
        return parse_video_date(value)

    def get_all_metadata(self, path: Path) -> dict:
        """Get all available metadata from a video file.
        
        Useful for debugging and inspection.
        
        Args:
            path: Path to the video file
            
        Returns:
            Dictionary of metadata fields
        """
        if not path.exists():
            return {}
        
        if self.provider == "ffprobe" and self._check_ffprobe():
            return self._ffprobe_all_metadata(path)
        elif self._check_hachoir():
            return self._hachoir_all_metadata(path)
        
        return {}

    def _ffprobe_all_metadata(self, path: Path) -> dict:
        """Get all metadata via ffprobe."""
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(path),
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as e:
            logger.debug(f"Failed to get all metadata: {e}")
        
        return {}

    def _hachoir_all_metadata(self, path: Path) -> dict:
        """Get all metadata via hachoir."""
        try:
            from hachoir.metadata import extractMetadata
            from hachoir.parser import createParser
            
            parser = createParser(str(path))
            if parser:
                with parser:
                    metadata = extractMetadata(parser)
                    if metadata:
                        return {"hachoir": metadata.exportPlaintext()}
        except Exception as e:
            logger.debug(f"Failed to get all metadata: {e}")
        
        return {}


def is_ffprobe_available(ffprobe_path: str = "ffprobe") -> bool:
    """Check if ffprobe is available on the system.
    
    Args:
        ffprobe_path: Path to ffprobe binary
        
    Returns:
        True if ffprobe is found and executable
    """
    return shutil.which(ffprobe_path) is not None


def find_ffprobe_path() -> Optional[str]:
    """Find ffprobe in common locations.
    
    Searches the following locations in order:
    1. System PATH (default 'ffprobe')
    2. /opt/bin/ffprobe (Synology DSM)
    3. /usr/local/bin/ffprobe (macOS Homebrew)
    4. /usr/bin/ffprobe (Linux system)
    5. C:\\ffmpeg\\bin\\ffprobe.exe (Windows common)
    
    Returns:
        Path to ffprobe if found, None otherwise
    """
    # Common ffprobe locations to probe
    common_paths = [
        "ffprobe",  # System PATH
        "/opt/bin/ffprobe",  # Synology DSM
        "/usr/local/bin/ffprobe",  # macOS Homebrew
        "/usr/bin/ffprobe",  # Linux system
        "C:\\ffmpeg\\bin\\ffprobe.exe",  # Windows
        "C:\\Program Files\\ffmpeg\\bin\\ffprobe.exe",
    ]
    
    for path in common_paths:
        if shutil.which(path) is not None:
            return path
    
    return None


def get_ffprobe_version(ffprobe_path: str = "ffprobe") -> Optional[str]:
    """Get the ffprobe version string.
    
    Args:
        ffprobe_path: Path to ffprobe binary
        
    Returns:
        Version string or None if not available
    """
    if not is_ffprobe_available(ffprobe_path):
        return None
    
    try:
        result = subprocess.run(
            [ffprobe_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # First line usually contains version: "ffprobe version N.N.N ..."
            first_line = result.stdout.split("\n")[0]
            return first_line
        return None
    except Exception:
        return None


def is_hachoir_available() -> bool:
    """Check if hachoir package is installed.
    
    Returns:
        True if hachoir is importable
    """
    try:
        import hachoir  # noqa: F401
        return True
    except ImportError:
        return False


def get_hachoir_version() -> Optional[str]:
    """Get the installed hachoir package version.
    
    Returns:
        Version string or None if not installed
    """
    try:
        import hachoir
        return getattr(hachoir, "__version__", "unknown")
    except ImportError:
        return None

