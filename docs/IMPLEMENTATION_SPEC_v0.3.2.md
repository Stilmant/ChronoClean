# ChronoClean v0.3.2 - Doctor Command & Code Quality

**Version:** 0.3.2 (Doctor Command & Code Quality)  
**Status:** Complete  
**Last Updated:** 2025-12-30

---

## Overview

v0.3.2 introduces the `doctor` command for diagnosing system dependencies and configuration issues, along with significant code quality improvements through refactoring CLI helpers to reduce duplication.

This version addresses a common pain point: users on Synology NAS or other systems where ffprobe is installed in non-standard paths (e.g., `/opt/bin/ffprobe`) often see "video dates won't be read" without understanding why or how to fix it.

---

## Goals for v0.3.2

| Goal | Priority | Description |
|------|----------|-------------|
| Dependency diagnostics | P0 | `doctor` command to check ffprobe, hachoir, exiftool availability |
| Interactive fix | P1 | `doctor --fix` to update config with correct paths |
| Common path search | P1 | Probe common locations for ffprobe (Synology, macOS, Linux, Windows) |
| Code deduplication | P2 | Centralize VideoMetadataReader and component instantiation |
| CLI helpers module | P2 | Create reusable factory functions for scan/apply/verify commands |

---

## New Command: `doctor`

### Usage

```bash
chronoclean doctor              # Check all dependencies
chronoclean doctor --fix        # Check and offer to fix issues
chronoclean doctor --config PATH  # Use specific config file
```

### What It Checks

**External Dependencies:**
- **ffprobe**: Video metadata extraction (preferred provider)
- **hachoir**: Python fallback for video dates
- **exiftool**: Optional advanced EXIF support (pyexiftool package)

**Python Packages:**
- exifread (EXIF metadata reading)
- rich (terminal formatting)
- typer (CLI framework)
- pyyaml (configuration parsing)

**Configuration:**
- Active config file location
- Video metadata settings (enabled, provider, ffprobe path)

### Example Output

```
ChronoClean Doctor
Checking system dependencies...

┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component ┃ Status               ┃ Path / Version     ┃ Affects               ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ ffprobe   │ ✓ found              │ /opt/bin/ffprobe   │ video dates           │
│ hachoir   │ ✓ installed          │ version 3.2.0      │ video dates (fallback)│
│ exiftool  │ ○ not installed      │ optional           │ advanced EXIF         │
└───────────┴──────────────────────┴────────────────────┴───────────────────────┘

✓ All dependencies OK!
```

### Common ffprobe Paths Searched

The `find_ffprobe_path()` function searches these locations in order:

1. System PATH (`ffprobe`)
2. `/opt/bin/ffprobe` - Synology DSM (Entware)
3. `/usr/local/bin/ffprobe` - macOS Homebrew
4. `/usr/bin/ffprobe` - Linux system packages
5. `C:\ffmpeg\bin\ffprobe.exe` - Windows common
6. `C:\Program Files\ffmpeg\bin\ffprobe.exe` - Windows Program Files

### Interactive Fix Mode

When `--fix` is passed and issues are found:

```
Issues Found:
  • ffprobe: Not found at configured path 'ffprobe'
    → Found at '/opt/bin/ffprobe'. Update config to use this path.

Available Fixes:
  • Set video_metadata.ffprobe_path = /opt/bin/ffprobe

Apply these fixes to configuration? [Y/n]:
```

If confirmed, the config file is created or updated with the correct settings.

---

## Code Quality Improvements

### New Module: `cli/helpers.py`

Centralizes common CLI functionality:

```python
@dataclass
class ScanComponents:
    """Container for scan-related components created from config."""
    exif_reader: ExifReader
    video_reader: Optional[VideoMetadataReader]
    folder_tagger: FolderTagger
    date_engine: DateInferenceEngine
    cfg: ChronoCleanConfig
    
    def create_scanner(self, recursive: bool, include_videos: bool) -> Scanner:
        """Create a Scanner instance with the stored components."""
        ...

def create_scan_components(cfg: ChronoCleanConfig) -> ScanComponents:
    """Create all scan-related components from configuration."""
    ...

def validate_source_dir(path: Path, console: Console) -> Path:
    """Validate and resolve a source directory path."""
    ...

def resolve_bool(cli_value: Optional[bool], config_value: bool) -> bool:
    """Resolve boolean value: CLI overrides config if explicitly set."""
    ...
```

### Refactored Commands

The following commands now use `create_scan_components()`:
- `scan`
- `apply`
- `_perform_scan` (used by export)
- `verify --reconstruct`

This eliminates ~120 lines of duplicated VideoMetadataReader/DateInferenceEngine instantiation code.

### New Helper Functions

**In `exif_reader.py`:**
- `is_exiftool_available()` - Check if pyexiftool is importable
- `get_exifread_version()` - Return installed exifread version

**In `video_metadata.py`:**
- `find_ffprobe_path()` - Search common locations for ffprobe
- `get_ffprobe_version(path)` - Get ffprobe version string
- `get_hachoir_version()` - Get hachoir package version

### Consolidated Hashing

`duplicate_checker.py` now uses `chronoclean.core.hashing.compute_file_hash()` instead of reimplementing the hashing logic, eliminating duplicate hashlib code.

---

## Files Changed

| File | Change |
|------|--------|
| `chronoclean/__init__.py` | Version bump to 0.3.2 |
| `chronoclean/cli/helpers.py` | **NEW** - Factory functions & validation helpers |
| `chronoclean/cli/main.py` | Added doctor command, refactored to use helpers |
| `chronoclean/core/duplicate_checker.py` | Consolidated to use hashing.py |
| `chronoclean/core/exif_reader.py` | Added availability check functions |
| `chronoclean/core/video_metadata.py` | Added ffprobe path finder & version functions |
| `tests/unit/test_config_integration.py` | Updated import for moved resolve_bool |
| `tests/unit/test_cli_helpers.py` | Tests for new helper functions |

---

## Success Criteria

- ✅ `chronoclean doctor` displays dependency status table
- ✅ `chronoclean doctor --fix` offers to update config when issues found
- ✅ ffprobe found at `/opt/bin/ffprobe` on Synology systems
- ✅ All 593 unit tests pass after refactoring
- ✅ Code duplication reduced by ~120 lines

---

## Synology Users

After installing ffprobe via Entware, run:

```bash
chronoclean doctor
```

If ffprobe is not detected, run:

```bash
chronoclean doctor --fix
```

This will automatically configure `video_metadata.ffprobe_path` to `/opt/bin/ffprobe`.

---

*Document version: 1.0 (complete)*  
*ChronoClean v0.3.2*
