# ChronoClean v0.1 — Implementation Specification

**Version:** 0.1 (Prototype)  
**Status:** Draft  
**Last Updated:** 2024-12-27

---

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Module Specifications](#module-specifications)
4. [Data Models](#data-models)
5. [Configuration Schema](#configuration-schema)
6. [CLI Interface](#cli-interface)
7. [Testing Strategy](#testing-strategy)
8. [Dependencies](#dependencies)
9. [Out of Scope for v0.1](#out-of-scope-for-v01)

---

## Overview

### Goals for v0.1

The v0.1 prototype establishes the core foundation of ChronoClean:

| Feature | Priority | Description |
|---------|----------|-------------|
| EXIF extraction | P0 | Read date/time from image EXIF metadata |
| Date parsing | P0 | Parse EXIF dates into Python datetime objects |
| Chronological sorting | P0 | Organize files into YYYY/MM (optionally /DD) folders |
| Fallback date logic | P0 | Use filesystem timestamps when EXIF is missing |
| Basic renaming | P1 | Optional rename to `YYYYMMDD_HHMMSS.ext` pattern |
| Folder tag detection | P1 | Simple heuristics to identify meaningful folder names |
| Minimal CLI | P0 | `scan` and `apply` commands |

### Design Principles

1. **Safety first**: Never modify files without explicit user consent
2. **Predictable output**: Same input always produces same output
3. **Testable**: Every module has clear inputs/outputs for unit testing
4. **Configurable**: Behavior controlled via YAML config
5. **Logging**: All operations are logged for debugging

---

## Project Structure

```
chronoclean/
├── __init__.py
├── __main__.py              # Entry point: python -m chronoclean
├── cli/
│   ├── __init__.py
│   ├── main.py              # Typer app definition
│   ├── scan_cmd.py          # scan command
│   └── apply_cmd.py         # apply command (v0.1 minimal)
├── core/
│   ├── __init__.py
│   ├── models.py            # Data classes (FileRecord, ScanResult, etc.)
│   ├── scanner.py           # Directory scanning logic
│   ├── exif_reader.py       # EXIF extraction
│   ├── date_inference.py    # Date parsing and fallback logic
│   ├── sorter.py            # Sorting logic (destination path computation)
│   ├── renamer.py           # File renaming logic
│   ├── folder_tagger.py     # Folder tag detection
│   └── file_operations.py   # Safe file move/copy operations
├── config/
│   ├── __init__.py
│   ├── loader.py            # Config file loading
│   └── schema.py            # Config dataclass definitions
├── utils/
│   ├── __init__.py
│   ├── logging.py           # Logging setup
│   ├── path_utils.py        # Path manipulation helpers
│   └── constants.py         # File extensions, patterns, etc.
└── tests/
    ├── __init__.py
    ├── conftest.py          # Pytest fixtures
    ├── unit/
    │   ├── test_exif_reader.py
    │   ├── test_date_inference.py
    │   ├── test_sorter.py
    │   ├── test_renamer.py
    │   ├── test_folder_tagger.py
    │   └── test_scanner.py
    ├── integration/
    │   └── test_scan_workflow.py
    └── fixtures/
        ├── images/          # Sample images with known EXIF
        └── configs/         # Test config files
```

---

## Module Specifications

### 1. `core/models.py` — Data Models

```python
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional, List

class DateSource(Enum):
    """Origin of the detected date."""
    EXIF = "exif"
    FILESYSTEM_CREATED = "filesystem_created"
    FILESYSTEM_MODIFIED = "filesystem_modified"
    FOLDER_NAME = "folder_name"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"

class FileType(Enum):
    """Supported file types."""
    IMAGE = "image"
    VIDEO = "video"
    UNKNOWN = "unknown"

@dataclass
class FileRecord:
    """Represents a single file in the scan."""
    source_path: Path
    file_type: FileType
    size_bytes: int
    
    # Date information
    detected_date: Optional[datetime] = None
    date_source: DateSource = DateSource.UNKNOWN
    
    # Computed destinations (filled by sorter)
    destination_folder: Optional[Path] = None
    destination_filename: Optional[str] = None
    
    # Folder tag info
    source_folder_name: Optional[str] = None
    folder_tag: Optional[str] = None
    folder_tag_usable: bool = False
    
    # Status flags
    needs_rename: bool = False
    has_exif: bool = False
    exif_error: Optional[str] = None

@dataclass
class ScanResult:
    """Result of scanning a directory."""
    source_root: Path
    total_files: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    error_files: int = 0
    
    files: List[FileRecord] = field(default_factory=list)
    folder_tags_detected: List[str] = field(default_factory=list)
    
    scan_duration_seconds: float = 0.0
    scan_timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class OperationPlan:
    """Plan for file operations (for dry-run and apply)."""
    moves: List[tuple[Path, Path]] = field(default_factory=list)
    renames: List[tuple[Path, str]] = field(default_factory=list)
    skipped: List[tuple[Path, str]] = field(default_factory=list)  # path, reason
```

---

### 2. `core/exif_reader.py` — EXIF Extraction

**Responsibility:** Extract EXIF metadata from image files.

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

@dataclass
class ExifData:
    """Extracted EXIF information."""
    date_taken: Optional[datetime] = None
    date_original: Optional[datetime] = None
    date_digitized: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    orientation: Optional[int] = None
    raw_tags: dict = field(default_factory=dict)

class ExifReader:
    """Reads EXIF data from image files."""
    
    # EXIF date tags to check, in priority order
    DATE_TAGS = [
        "EXIF DateTimeOriginal",
        "EXIF DateTimeDigitized", 
        "Image DateTime",
    ]
    
    # Common EXIF date formats
    DATE_FORMATS = [
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]
    
    def read(self, file_path: Path) -> ExifData:
        """
        Read EXIF data from an image file.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            ExifData object with extracted metadata
            
        Raises:
            ExifReadError: If the file cannot be read
        """
        ...
    
    def get_date(self, file_path: Path) -> Optional[datetime]:
        """
        Convenience method to get just the date.
        
        Returns the first valid date found in priority order:
        1. DateTimeOriginal
        2. DateTimeDigitized
        3. DateTime
        """
        ...
```

**Implementation notes:**
- Use `exifread` library (read-only, robust)
- Handle corrupted EXIF gracefully (return None, log warning)
- Support JPEG, TIFF, PNG (limited EXIF), HEIC

---

### 3. `core/date_inference.py` — Date Inference

**Responsibility:** Determine the best date for a file using fallback logic.

```python
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

from .models import DateSource

class DateInferenceEngine:
    """Infers dates from multiple sources with configurable priority."""
    
    def __init__(self, 
                 priority: List[str] = None,
                 exif_reader: ExifReader = None):
        """
        Args:
            priority: Ordered list of sources to try.
                      Default: ["exif", "filesystem", "folder_name"]
            exif_reader: ExifReader instance (optional, created if not provided)
        """
        self.priority = priority or ["exif", "filesystem", "folder_name"]
        self.exif_reader = exif_reader or ExifReader()
    
    def infer_date(self, file_path: Path) -> Tuple[Optional[datetime], DateSource]:
        """
        Infer the date for a file using configured priority.
        
        Returns:
            Tuple of (datetime or None, DateSource indicating origin)
        """
        ...
    
    def _get_exif_date(self, file_path: Path) -> Optional[datetime]:
        """Extract date from EXIF metadata."""
        ...
    
    def _get_filesystem_date(self, file_path: Path) -> Optional[datetime]:
        """
        Get date from filesystem.
        Prefers creation date, falls back to modification date.
        """
        ...
    
    def _get_folder_date(self, file_path: Path) -> Optional[datetime]:
        """
        Try to parse date from parent folder name.
        
        Recognizes patterns like:
        - "2024-03-15"
        - "2024_03_15" 
        - "20240315"
        - "March 2024"
        - "2024-03 Paris Trip"
        """
        ...
```

**Folder name date patterns to recognize:**
```python
FOLDER_DATE_PATTERNS = [
    r"^(\d{4})-(\d{2})-(\d{2})",           # 2024-03-15
    r"^(\d{4})_(\d{2})_(\d{2})",           # 2024_03_15
    r"^(\d{4})(\d{2})(\d{2})",             # 20240315
    r"^(\d{4})-(\d{2})\b",                 # 2024-03
    r"^(\d{4})_(\d{2})\b",                 # 2024_03
    r"(?:^|\s)(\d{4})(?:\s|$)",            # Just year: "Photos 2024"
]
```

---

### 4. `core/sorter.py` — Sorting Logic

**Responsibility:** Compute destination paths based on dates.

```python
from pathlib import Path
from datetime import datetime
from typing import Optional

class Sorter:
    """Computes destination paths for files based on their dates."""
    
    def __init__(self,
                 destination_root: Path,
                 folder_structure: str = "YYYY/MM",
                 include_day: bool = False):
        """
        Args:
            destination_root: Root folder for sorted files
            folder_structure: Pattern like "YYYY/MM" or "YYYY/MM/DD"
            include_day: Whether to include day subfolder
        """
        self.destination_root = destination_root
        self.folder_structure = folder_structure
        self.include_day = include_day
    
    def compute_destination_folder(self, 
                                    date: datetime) -> Path:
        """
        Compute the destination folder for a given date.
        
        Example:
            date=2024-03-15, structure="YYYY/MM"
            → destination_root / "2024" / "03"
        """
        ...
    
    def compute_full_destination(self,
                                  source_path: Path,
                                  date: datetime,
                                  new_filename: Optional[str] = None) -> Path:
        """
        Compute full destination path including filename.
        
        Args:
            source_path: Original file path (for extension)
            date: Detected date
            new_filename: Optional renamed filename (without extension)
            
        Returns:
            Full destination path
        """
        ...
```

---

### 5. `core/renamer.py` — File Renaming

**Responsibility:** Generate new filenames based on pattern.

```python
from pathlib import Path
from datetime import datetime
from typing import Optional

class Renamer:
    """Generates new filenames based on configurable patterns."""
    
    DEFAULT_PATTERN = "{date}_{time}"
    DEFAULT_DATE_FORMAT = "%Y%m%d"
    DEFAULT_TIME_FORMAT = "%H%M%S"
    
    def __init__(self,
                 pattern: str = None,
                 date_format: str = None,
                 time_format: str = None,
                 lowercase_ext: bool = True):
        """
        Args:
            pattern: Filename pattern with placeholders
                     Supported: {date}, {time}, {tag}, {original}
            date_format: strftime format for date
            time_format: strftime format for time
            lowercase_ext: Convert extensions to lowercase
        """
        self.pattern = pattern or self.DEFAULT_PATTERN
        self.date_format = date_format or self.DEFAULT_DATE_FORMAT
        self.time_format = time_format or self.DEFAULT_TIME_FORMAT
        self.lowercase_ext = lowercase_ext
    
    def generate_filename(self,
                          original_path: Path,
                          date: datetime,
                          tag: Optional[str] = None) -> str:
        """
        Generate a new filename.
        
        Args:
            original_path: Original file path (for extension)
            date: Date to use in filename
            tag: Optional folder tag to include
            
        Returns:
            New filename with extension
            
        Example:
            original="IMG_1234.JPG", date=2024-03-15 14:30:00
            → "20240315_143000.jpg"
        """
        ...
    
    def _format_tag(self, tag: str) -> str:
        """
        Format tag for filename inclusion.
        
        - Remove special characters
        - Replace spaces with underscores
        - Limit length
        """
        ...
```

---

### 6. `core/folder_tagger.py` — Folder Tag Detection

**Responsibility:** Identify meaningful folder names for tagging.

```python
from pathlib import Path
from typing import List, Tuple

class FolderTagger:
    """Detects and classifies folder names for potential use as file tags."""
    
    # Default ignore patterns (case-insensitive)
    DEFAULT_IGNORE_LIST = [
        "tosort", "unsorted", "misc", "backup", "temp", "tmp",
        "download", "downloads", "dcim", "camera", "pictures",
        "photos", "images", "100apple", "100andro", "camera roll"
    ]
    
    def __init__(self,
                 ignore_list: List[str] = None,
                 force_list: List[str] = None,
                 min_length: int = 3,
                 max_length: int = 40):
        """
        Args:
            ignore_list: Folder names to never use as tags
            force_list: Folder names to always use as tags
            min_length: Minimum tag length
            max_length: Maximum tag length
        """
        self.ignore_list = [s.lower() for s in (ignore_list or self.DEFAULT_IGNORE_LIST)]
        self.force_list = [s.lower() for s in (force_list or [])]
        self.min_length = min_length
        self.max_length = max_length
    
    def is_meaningful(self, folder_name: str) -> bool:
        """
        Determine if a folder name is meaningful for tagging.
        
        Returns True if:
        - Not in ignore list
        - Meets length requirements
        - Contains actual words (not just numbers/dates)
        - Not a camera-generated folder name
        """
        ...
    
    def classify_folder(self, folder_name: str) -> Tuple[bool, str]:
        """
        Classify a folder name.
        
        Returns:
            Tuple of (usable: bool, reason: str)
            
        Example:
            "Paris Trip 2024" → (True, "meaningful")
            "DCIM" → (False, "in_ignore_list")
            "ab" → (False, "too_short")
        """
        ...
    
    def extract_tag(self, folder_path: Path) -> Optional[str]:
        """
        Extract the best tag from a folder path.
        
        Walks up the path to find the first meaningful folder name.
        """
        ...
    
    def is_tag_in_filename(self, 
                           filename: str, 
                           tag: str,
                           threshold: float = 0.75) -> bool:
        """
        Check if tag is already present in filename (fuzzy match).
        
        Uses string similarity to detect if the tag or similar
        text already appears in the filename.
        """
        ...
```

---

### 7. `core/scanner.py` — Directory Scanner

**Responsibility:** Scan directories and build file records.

```python
from pathlib import Path
from typing import Iterator, Optional, List

from .models import FileRecord, ScanResult, FileType
from .exif_reader import ExifReader
from .date_inference import DateInferenceEngine
from .folder_tagger import FolderTagger

class Scanner:
    """Scans directories and builds file records."""
    
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", 
                        ".heic", ".heif", ".webp", ".bmp", ".gif"}
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v",
                        ".3gp", ".wmv", ".webm"}
    
    def __init__(self,
                 exif_reader: ExifReader = None,
                 date_engine: DateInferenceEngine = None,
                 folder_tagger: FolderTagger = None,
                 include_videos: bool = True,
                 recursive: bool = True,
                 ignore_hidden: bool = True):
        self.exif_reader = exif_reader or ExifReader()
        self.date_engine = date_engine or DateInferenceEngine()
        self.folder_tagger = folder_tagger or FolderTagger()
        self.include_videos = include_videos
        self.recursive = recursive
        self.ignore_hidden = ignore_hidden
    
    def scan(self, source_path: Path, limit: Optional[int] = None) -> ScanResult:
        """
        Scan a directory and return results.
        
        Args:
            source_path: Directory to scan
            limit: Optional limit on number of files (for debugging)
            
        Returns:
            ScanResult with all file records
        """
        ...
    
    def _iter_files(self, source_path: Path) -> Iterator[Path]:
        """Iterate over files in directory (with filters applied)."""
        ...
    
    def _classify_file_type(self, path: Path) -> FileType:
        """Determine if file is image, video, or unknown."""
        ...
    
    def _build_file_record(self, file_path: Path) -> FileRecord:
        """Build a FileRecord for a single file."""
        ...
```

---

### 8. `core/file_operations.py` — Safe File Operations

**Responsibility:** Perform safe file moves/copies.

```python
from pathlib import Path
from typing import List, Tuple
import shutil

class FileOperations:
    """Safe file operations with conflict handling."""
    
    def __init__(self,
                 dry_run: bool = True,
                 create_dirs: bool = True,
                 backup_on_conflict: bool = True):
        self.dry_run = dry_run
        self.create_dirs = create_dirs
        self.backup_on_conflict = backup_on_conflict
    
    def move_file(self, 
                  source: Path, 
                  destination: Path) -> Tuple[bool, str]:
        """
        Move a file safely.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        ...
    
    def ensure_unique_path(self, path: Path) -> Path:
        """
        Ensure the path is unique by adding suffix if needed.
        
        Example:
            "photo.jpg" exists → "photo_001.jpg"
        """
        ...
    
    def check_disk_space(self, 
                         path: Path, 
                         required_mb: int) -> bool:
        """Check if sufficient disk space is available."""
        ...
```

---

### 9. `config/loader.py` — Configuration Loading

**Responsibility:** Load and validate configuration.

```python
from pathlib import Path
from typing import Optional
import yaml

from .schema import ChronoCleanConfig

class ConfigLoader:
    """Loads configuration from YAML files."""
    
    DEFAULT_CONFIG_PATHS = [
        Path("chronoclean.yaml"),
        Path("chronoclean.yml"),
        Path(".chronoclean/config.yaml"),
        Path.home() / ".config/chronoclean/config.yaml",
    ]
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> ChronoCleanConfig:
        """
        Load configuration.
        
        Priority:
        1. Explicit config_path argument
        2. Default config paths (first found)
        3. Built-in defaults
        """
        ...
    
    @classmethod
    def merge_with_defaults(cls, user_config: dict) -> dict:
        """Merge user config with defaults."""
        ...
    
    @classmethod
    def validate(cls, config: dict) -> List[str]:
        """Validate configuration, return list of errors."""
        ...
```

---

### 10. `config/schema.py` — Configuration Schema

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

@dataclass
class GeneralConfig:
    timezone: str = "local"
    recursive: bool = True
    include_videos: bool = True
    ignore_hidden_files: bool = True
    dry_run_default: bool = True
    output_folder: str = ".chronoclean"

@dataclass
class PathsConfig:
    source: Optional[Path] = None
    destination: Optional[Path] = None
    temp_folder: Optional[Path] = None

@dataclass
class SortingConfig:
    folder_structure: str = "YYYY/MM"
    fallback_date_priority: List[str] = field(
        default_factory=lambda: ["exif", "filesystem", "folder_name"]
    )

@dataclass
class FolderTagsConfig:
    enabled: bool = False
    min_length: int = 3
    max_length: int = 40
    ignore_list: List[str] = field(default_factory=list)
    force_list: List[str] = field(default_factory=list)
    distance_threshold: float = 0.75

@dataclass
class RenamingConfig:
    enabled: bool = False
    pattern: str = "{date}_{time}"
    date_format: str = "%Y%m%d"
    time_format: str = "%H%M%S"
    lowercase_extensions: bool = True

@dataclass
class LoggingConfig:
    level: str = "info"
    color_output: bool = True
    log_to_file: bool = True
    file_path: str = ".chronoclean/chronoclean.log"

@dataclass
class ChronoCleanConfig:
    """Root configuration object."""
    general: GeneralConfig = field(default_factory=GeneralConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    sorting: SortingConfig = field(default_factory=SortingConfig)
    folder_tags: FolderTagsConfig = field(default_factory=FolderTagsConfig)
    renaming: RenamingConfig = field(default_factory=RenamingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
```

---

## CLI Interface

### v0.1 Commands

Using **Typer** for modern, type-hinted CLI.

```python
# cli/main.py
import typer
from pathlib import Path
from typing import Optional

app = typer.Typer(
    name="chronoclean",
    help="Restore order to your photo collections.",
    add_completion=False,
)

@app.command()
def scan(
    source: Path = typer.Argument(..., help="Source directory to scan"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
    videos: bool = typer.Option(True, "--videos/--no-videos"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit files (debug)"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Analyze files in the source directory."""
    ...

@app.command()
def apply(
    source: Path = typer.Argument(..., help="Source directory"),
    destination: Path = typer.Argument(..., help="Destination directory"),
    dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run"),
    rename: bool = typer.Option(False, "--rename/--no-rename"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Apply file organization (moves and optional renames)."""
    ...

@app.command()
def version():
    """Show ChronoClean version."""
    typer.echo("ChronoClean v0.1.0")

if __name__ == "__main__":
    app()
```

---

## Testing Strategy

### Framework: pytest + pytest-mock

**Why pytest:**
- Industry standard for Python testing
- Excellent fixture system for test data
- Rich plugin ecosystem
- Clear assertion introspection

**Additional libraries:**
- `pytest-mock`: Mocking fixtures
- `pytest-cov`: Coverage reporting
- `pytest-xdist`: Parallel test execution (optional)

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (isolated, fast)
│   ├── test_exif_reader.py
│   ├── test_date_inference.py
│   ├── test_sorter.py
│   ├── test_renamer.py
│   ├── test_folder_tagger.py
│   ├── test_scanner.py
│   └── test_config_loader.py
├── integration/             # Integration tests (multiple components)
│   ├── test_scan_workflow.py
│   └── test_apply_workflow.py
└── fixtures/
    ├── images/              # Sample images with known EXIF
    │   ├── with_exif.jpg
    │   ├── no_exif.jpg
    │   └── corrupted_exif.jpg
    └── configs/
        ├── minimal.yaml
        └── full.yaml
```

### Key Test Fixtures

```python
# tests/conftest.py
import pytest
from pathlib import Path
import tempfile
import shutil

@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path)

@pytest.fixture
def sample_image_with_exif(temp_dir):
    """Create a sample image with EXIF data."""
    # Copy fixture image to temp dir
    src = Path(__file__).parent / "fixtures/images/with_exif.jpg"
    dst = temp_dir / "test_image.jpg"
    shutil.copy(src, dst)
    return dst

@pytest.fixture
def mock_filesystem(temp_dir):
    """Create a mock photo library structure."""
    # Create folder structure
    folders = [
        "Paris 2024",
        "tosort",
        "DCIM/100APPLE",
        "2023-12-25 Christmas",
    ]
    for folder in folders:
        (temp_dir / folder).mkdir(parents=True)
    return temp_dir

@pytest.fixture
def default_config():
    """Return default configuration."""
    from chronoclean.config.schema import ChronoCleanConfig
    return ChronoCleanConfig()
```

### Example Unit Tests

```python
# tests/unit/test_folder_tagger.py
import pytest
from chronoclean.core.folder_tagger import FolderTagger

class TestFolderTagger:
    
    def test_meaningful_folder_name(self):
        tagger = FolderTagger()
        assert tagger.is_meaningful("Paris Trip 2024") is True
        
    def test_ignored_folder_name(self):
        tagger = FolderTagger()
        assert tagger.is_meaningful("tosort") is False
        assert tagger.is_meaningful("DCIM") is False
        
    def test_too_short_folder_name(self):
        tagger = FolderTagger(min_length=3)
        assert tagger.is_meaningful("ab") is False
        
    def test_force_list_overrides_ignore(self):
        tagger = FolderTagger(
            ignore_list=["vacation"],
            force_list=["vacation"]
        )
        assert tagger.is_meaningful("vacation") is True
        
    @pytest.mark.parametrize("folder,expected", [
        ("Wedding 2024", True),
        ("IMG_1234", False),
        ("100APPLE", False),
        ("Naomie Birthday", True),
        ("temp", False),
    ])
    def test_folder_classification(self, folder, expected):
        tagger = FolderTagger()
        assert tagger.is_meaningful(folder) is expected
```

```python
# tests/unit/test_date_inference.py
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from chronoclean.core.date_inference import DateInferenceEngine
from chronoclean.core.models import DateSource

class TestDateInference:
    
    def test_exif_date_priority(self):
        mock_exif = Mock()
        mock_exif.get_date.return_value = datetime(2024, 3, 15, 14, 30)
        
        engine = DateInferenceEngine(exif_reader=mock_exif)
        date, source = engine.infer_date(Path("/fake/image.jpg"))
        
        assert date == datetime(2024, 3, 15, 14, 30)
        assert source == DateSource.EXIF
        
    def test_fallback_to_filesystem(self):
        mock_exif = Mock()
        mock_exif.get_date.return_value = None
        
        engine = DateInferenceEngine(exif_reader=mock_exif)
        
        with patch.object(engine, '_get_filesystem_date') as mock_fs:
            mock_fs.return_value = datetime(2024, 1, 1)
            date, source = engine.infer_date(Path("/fake/image.jpg"))
            
        assert source == DateSource.FILESYSTEM_MODIFIED
        
    @pytest.mark.parametrize("folder_name,expected_date", [
        ("2024-03-15", datetime(2024, 3, 15)),
        ("2024_03_15", datetime(2024, 3, 15)),
        ("20240315", datetime(2024, 3, 15)),
        ("2024-03 Paris", datetime(2024, 3, 1)),
        ("Random Folder", None),
    ])
    def test_folder_date_parsing(self, folder_name, expected_date):
        engine = DateInferenceEngine()
        result = engine._get_folder_date(Path(f"/photos/{folder_name}/img.jpg"))
        
        if expected_date:
            assert result.year == expected_date.year
            assert result.month == expected_date.month
        else:
            assert result is None
```

### Test Coverage Goals

| Module | Target Coverage |
|--------|----------------|
| core/exif_reader.py | 90% |
| core/date_inference.py | 95% |
| core/sorter.py | 95% |
| core/renamer.py | 95% |
| core/folder_tagger.py | 90% |
| core/scanner.py | 85% |
| config/loader.py | 90% |

---

## Dependencies

### requirements.txt

```
# Core
exifread>=3.0.0
typer>=0.9.0
pyyaml>=6.0

# Optional (recommended)
rich>=13.0.0          # Better CLI output

# Development
pytest>=7.0.0
pytest-mock>=3.0.0
pytest-cov>=4.0.0

# Type checking (optional)
mypy>=1.0.0
```

### pyproject.toml (alternative)

```toml
[project]
name = "chronoclean"
version = "0.1.0"
description = "Restore order to your photo collections"
requires-python = ">=3.10"
dependencies = [
    "exifread>=3.0.0",
    "typer>=0.9.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.0.0",
    "pytest-cov>=4.0.0",
    "mypy>=1.0.0",
]

[project.scripts]
chronoclean = "chronoclean.cli.main:app"
```

---

## Out of Scope for v0.1

The following features are explicitly **deferred** to later versions:

| Feature | Deferred To | Reason |
|---------|-------------|--------|
| Video metadata extraction | v0.3 | Requires ffmpeg/hachoir |
| Export command (JSON/CSV) | v0.2 | Not essential for prototype |
| Dryrun command | v0.2 | Apply with --dry-run covers this |
| Hash-based duplicate detection | v0.2 | Safety feature, not core |
| Interactive prompts | v0.4 | UX enhancement |
| Parallel processing | v0.5 | Performance optimization |
| Tags classify/auto commands | v0.2 | Tag management can be manual |
| Report commands | v0.2 | JSON export serves this purpose |
| Config show/set commands | v0.2 | Edit YAML directly for now |

---

## Implementation Order

Recommended order for implementation:

1. **Project setup**: pyproject.toml, folder structure
2. **Data models**: `core/models.py`
3. **Configuration**: `config/schema.py`, `config/loader.py`
4. **EXIF reader**: `core/exif_reader.py` + tests
5. **Date inference**: `core/date_inference.py` + tests
6. **Folder tagger**: `core/folder_tagger.py` + tests
7. **Sorter**: `core/sorter.py` + tests
8. **Renamer**: `core/renamer.py` + tests
9. **Scanner**: `core/scanner.py` + tests
10. **File operations**: `core/file_operations.py` + tests
11. **CLI commands**: `cli/main.py`, `cli/scan_cmd.py`, `cli/apply_cmd.py`
12. **Integration tests**
13. **Documentation updates**

---

## Appendix: Sample Test Images

For testing, create or source images with known EXIF data:

| File | EXIF Date | Notes |
|------|-----------|-------|
| `with_exif.jpg` | 2024-03-15 14:30:00 | Standard iPhone photo |
| `no_exif.jpg` | None | Screenshot or web image |
| `corrupted_exif.jpg` | Invalid | Malformed EXIF tags |
| `heic_sample.heic` | 2024-06-01 | iOS HEIC format |
| `old_camera.jpg` | 2010-01-01 | Old camera format |

---

*Document version: 1.0*  
*For ChronoClean v0.1*
