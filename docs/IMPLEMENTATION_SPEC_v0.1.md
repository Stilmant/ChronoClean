# ChronoClean v0.1 — Implementation Specification

**Version:** 0.1 (Prototype)  
**Status:** Implemented ✅  
**Last Updated:** 2024-12-27

---

## Table of Contents

1. [Overview](#overview)
2. [Project Structure](#project-structure)
3. [Module Reference](#module-reference)
4. [Data Models](#data-models)
5. [Configuration Schema](#configuration-schema)
6. [CLI Interface](#cli-interface)
7. [Testing](#testing)
8. [Dependencies](#dependencies)
9. [Out of Scope for v0.1](#out-of-scope-for-v01)

---

## Overview

### v0.1 Implemented Features

The v0.1 prototype establishes the core foundation of ChronoClean:

| Feature | Status | Module |
|---------|--------|--------|
| EXIF extraction | ✅ Implemented | `core/exif_reader.py` |
| Date parsing | ✅ Implemented | `core/date_inference.py` |
| Chronological sorting | ✅ Implemented | `core/sorter.py` |
| Fallback date logic | ✅ Implemented | `core/date_inference.py` |
| Basic renaming | ✅ Implemented | `core/renamer.py` |
| Folder tag detection | ✅ Implemented | `core/folder_tagger.py` |
| Minimal CLI | ✅ Implemented | `cli/main.py` |
| Safe file operations | ✅ Implemented | `core/file_operations.py` |
| Directory scanning | ✅ Implemented | `core/scanner.py` |
| YAML configuration | ✅ Implemented | `config/loader.py`, `config/schema.py` |
| Unit test suite | ✅ 315 tests | `tests/` |

### Design Principles

1. **Safety first**: Copy mode by default, move requires explicit `--move` flag
2. **Predictable output**: Same input always produces same output
3. **Testable**: Every module has clear inputs/outputs with 315 unit tests
4. **Configurable**: Behavior controlled via YAML config
5. **Logging**: All operations are logged for debugging

---

## Project Structure

```
chronoclean/
├── __init__.py                 # Package version (__version__ = "0.1.0")
├── __main__.py                 # Entry point: python -m chronoclean
├── cli/
│   ├── __init__.py
│   └── main.py                 # Typer CLI: scan, apply, version commands
├── core/
│   ├── __init__.py
│   ├── models.py               # Data classes (FileRecord, ScanResult, etc.)
│   ├── scanner.py              # Directory scanning logic
│   ├── exif_reader.py          # EXIF extraction via exifread
│   ├── date_inference.py       # Date parsing and fallback logic
│   ├── sorter.py               # Sorting logic (destination path computation)
│   ├── renamer.py              # File renaming logic with conflict resolution
│   ├── folder_tagger.py        # Folder tag detection and classification
│   └── file_operations.py      # Safe file move/copy operations
├── config/
│   ├── __init__.py
│   ├── loader.py               # Config file loading with defaults
│   └── schema.py               # Config dataclass definitions
└── utils/
    ├── __init__.py
    ├── logging.py              # Logging setup with Rich
    ├── path_utils.py           # Path manipulation helpers
    └── constants.py            # File extensions, patterns

tests/
├── conftest.py                 # Pytest fixtures (temp_dir, sample files, mocks)
├── unit/
│   ├── test_models.py          # FileRecord, ScanResult, OperationPlan tests
│   ├── test_config.py          # ConfigLoader, schema validation tests
│   ├── test_exif_reader.py     # EXIF extraction tests
│   ├── test_date_inference.py  # Date inference priority, fallback tests
│   ├── test_folder_tagger.py   # Folder classification tests
│   ├── test_renamer.py         # Filename generation, conflict resolution tests
│   ├── test_sorter.py          # Destination path computation tests
│   ├── test_scanner.py         # Directory scanning tests
│   └── test_file_operations.py # File move/copy, dry-run tests
└── integration/
    └── test_workflow.py        # End-to-end scan→apply workflow tests
```

---

## Module Reference

### 1. `core/models.py` — Data Models

**Classes:**
- `DateSource` (Enum): Origin of detected date (`EXIF`, `FILESYSTEM_CREATED`, `FILESYSTEM_MODIFIED`, `FOLDER_NAME`, `HEURISTIC`, `UNKNOWN`)
- `FileType` (Enum): File classification (`IMAGE`, `VIDEO`, `RAW`, `UNKNOWN`)
- `FileRecord`: Represents a single file with metadata, dates, and destination info
- `ScanResult`: Container for scan results with statistics
- `MoveOperation`: Single file operation descriptor
- `OperationPlan`: Collection of planned operations

**Key Properties on FileRecord:**
- `destination_path`: Computed full destination path
- `extension`: Lowercase file extension
- `original_filename`: Original filename without path

---

### 2. `core/exif_reader.py` — EXIF Extraction

**Classes:**
- `ExifReadError`: Exception for EXIF read failures
- `ExifData`: Container for extracted EXIF metadata
- `ExifReader`: Main reader class using `exifread` library

**Key Features:**
- Reads from JPEG, TIFF, HEIC, PNG, WebP, RAW formats
- Priority date extraction: `DateTimeOriginal` → `DateTimeDigitized` → `DateTime`
- Handles corrupted EXIF gracefully (returns empty data)
- Configurable `skip_errors` mode

**Date Tags Checked (priority order):**
1. `EXIF DateTimeOriginal`
2. `EXIF DateTimeDigitized`
3. `Image DateTime`
4. `EXIF DateTime`

---

### 3. `core/date_inference.py` — Date Inference

**Classes:**
- `DateInferenceEngine`: Main inference engine with configurable priority

**Key Features:**
- Configurable source priority (default: `exif` → `filesystem` → `folder_name`)
- Filesystem date prefers modification time (survives file copies)
- Folder date parsing with multiple patterns

**Folder Date Patterns Recognized:**
| Pattern | Example |
|---------|---------|
| `YYYY-MM-DD` | `2024-03-15` |
| `YYYY_MM_DD` | `2024_03_15` |
| `YYYY.MM.DD` | `2024.03.15` |
| `YYYYMMDD` | `20240315` |
| `YYYY-MM` | `2024-03` |
| `YYYY_MM` | `2024_03` |
| Year anywhere | `Photos 2024` |

---

### 4. `core/sorter.py` — Sorting Logic

**Classes:**
- `Sorter`: Computes destination paths based on dates
- `SortingPlan`: Builds sorting plan for multiple files

**Supported Folder Structures:**
- `YYYY` → `2024/`
- `YYYY/MM` → `2024/03/`
- `YYYY/MM/DD` → `2024/03/15/`

**Key Methods:**
- `compute_destination_folder(date)`: Returns folder path for given date
- `compute_full_destination(source, date, new_filename)`: Returns complete destination path
- `get_relative_destination(date, filename)`: Returns relative path for display

---

### 5. `core/renamer.py` — File Renaming

**Classes:**
- `Renamer`: Generates new filenames from patterns
- `ConflictResolver`: Resolves filename conflicts with counters

**Pattern Placeholders:**
- `{date}`: Formatted date (default: `%Y%m%d`)
- `{time}`: Formatted time (default: `%H%M%S`)
- `{tag}`: Folder tag (if provided)
- `{original}`: Original filename stem
- `{counter}`: Numeric counter for conflicts

**Default Pattern:** `{date}_{time}` → `20240315_143000.jpg`

---

### 6. `core/folder_tagger.py` — Folder Tag Detection

**Classes:**
- `FolderTagger`: Detects and classifies folder names

**Key Features:**
- Default ignore list (23 common non-meaningful names)
- Camera folder pattern detection (e.g., `100APPLE`, `DCIM`)
- Force list for override
- Fuzzy matching to detect if tag already in filename

**Default Ignore List Includes:**
`tosort`, `unsorted`, `misc`, `backup`, `temp`, `dcim`, `camera`, `pictures`, `photos`, `images`, `100apple`, `100andro`, `camera roll`, `new folder`, `screenshots`, `inbox`, `import`, etc.

**Classification Results:**
| Result | Reason |
|--------|--------|
| `True` | `meaningful`, `in_force_list` |
| `False` | `in_ignore_list`, `too_short`, `too_long`, `camera_generated`, `numbers_only`, `no_letters` |

---

### 7. `core/scanner.py` — Directory Scanner

**Classes:**
- `Scanner`: Scans directories and builds file records

**Supported Extensions:**
- **Images:** `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`, `.heic`, `.heif`, `.webp`, `.bmp`, `.gif`
- **Videos:** `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.3gp`, `.wmv`, `.webm`, `.mts`, `.m2ts`
- **RAW:** `.cr2`, `.cr3`, `.nef`, `.arw`, `.dng`, `.orf`, `.rw2`, `.raf`, `.pef`, `.srw`

**Options:**
- `recursive`: Scan subdirectories (default: `True`)
- `include_videos`: Include video files (default: `True`)
- `include_raw`: Include RAW files (default: `True`)
- `ignore_hidden`: Skip hidden files/folders (default: `True`)

---

### 8. `core/file_operations.py` — Safe File Operations

**Classes:**
- `FileOperationError`: Exception for operation failures
- `FileOperations`: Single file operations with dry-run support
- `BatchOperations`: Batch operations with rollback capability

**Key Features:**
- Dry-run mode by default
- Copy and move operations
- Automatic directory creation
- Metadata preservation with `shutil.copy2`
- Conflict resolution with numbered suffixes
- Disk space checking
- Batch rollback on failure

**Key Methods (FileOperations):**
- `move_file(source, destination)`: Move with validation
- `copy_file(source, destination)`: Copy with validation
- `ensure_unique_path(path)`: Add suffix if path exists
- `check_disk_space(path, required_bytes)`: Verify available space

**Key Methods (BatchOperations):**
- `add_operation(source, destination)`: Queue an operation
- `execute_copies()`: Execute all as copies
- `execute_moves()`: Execute all as moves
- `rollback()`: Undo completed operations

---

### 9. `config/loader.py` — Configuration Loading

**Classes:**
- `ConfigLoader`: Loads and merges YAML configuration

**Search Paths (in order):**
1. Explicit `--config` argument
2. `chronoclean.yaml` or `chronoclean.yml` in current directory
3. `.chronoclean/config.yaml` in current directory
4. `~/.config/chronoclean/config.yaml`
5. Built-in defaults

**Key Methods:**
- `ConfigLoader.load(config_path)`: Load config with fallbacks
- `ConfigLoader.load_from_dict(data)`: Create config from dict

---

### 10. `config/schema.py` — Configuration Schema

**Configuration Sections:**

| Section | Key Settings |
|---------|--------------|
| `GeneralConfig` | `timezone`, `recursive`, `include_videos`, `dry_run_default` |
| `PathsConfig` | `source`, `destination`, `temp_folder` |
| `ScanConfig` | `image_extensions`, `video_extensions`, `raw_extensions` |
| `SortingConfig` | `folder_structure`, `fallback_date_priority`, `include_day` |
| `HeuristicConfig` | `enabled`, `max_days_from_cluster` |
| `FolderTagsConfig` | `enabled`, `ignore_list`, `force_list`, `distance_threshold` |
| `RenamingConfig` | `enabled`, `pattern`, `date_format`, `time_format` |
| `DuplicatesConfig` | `policy`, `hashing_algorithm` |
| `LoggingConfig` | `level`, `color_output`, `log_to_file` |
| `PerformanceConfig` | `multiprocessing`, `max_workers`, `chunk_size` |
| `SynologyConfig` | `safe_fs_mode`, `min_free_space_mb` |

---

## CLI Interface

### Commands Implemented

#### `scan` — Analyze files

```bash
chronoclean scan <source> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--recursive/--no-recursive` | `True` | Scan subfolders |
| `--videos/--no-videos` | `True` | Include video files |
| `--limit, -l` | None | Limit files (debug) |
| `--config, -c` | None | Config file path |
| `--report, -r` | `False` | Show detailed per-file report |

**Output:**
- Scan summary table (total files, processed, errors, duration)
- Date source breakdown
- Folder tags detected
- Optional: Detailed per-file report table

---

#### `apply` — Apply file organization

```bash
chronoclean apply <source> <destination> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run/--no-dry-run` | `True` | Simulate without changes |
| `--move` | `False` | Move files (default: copy) |
| `--rename/--no-rename` | `False` | Enable file renaming |
| `--tag-names/--no-tag-names` | `False` | Add folder tags |
| `--recursive/--no-recursive` | `True` | Scan subfolders |
| `--videos/--no-videos` | `True` | Include video files |
| `--structure, -s` | `YYYY/MM` | Folder structure |
| `--force, -f` | `False` | Skip confirmation |
| `--limit, -l` | None | Limit files |
| `--config, -c` | None | Config file path |

**Output:**
- Mode indicator (DRY RUN / LIVE MODE)
- Operation type (COPY / MOVE)
- Operation plan table
- Summary statistics

---

#### `version` — Show version

```bash
chronoclean version
```

Outputs: `ChronoClean v0.1.0`

---

## Testing

### Test Framework

- **pytest 9.0.2**: Test framework
- **pytest-mock**: Mocking fixtures
- **pytest-cov**: Coverage reporting

### Test Statistics

| Category | Tests |
|----------|-------|
| Unit tests | 295 |
| Integration tests | 20 |
| **Total** | **315** |

### Test Files

| File | Module Tested | Description |
|------|---------------|-------------|
| `test_models.py` | `core/models.py` | FileRecord, ScanResult, OperationPlan |
| `test_config.py` | `config/loader.py`, `config/schema.py` | Config loading, validation |
| `test_exif_reader.py` | `core/exif_reader.py` | EXIF extraction, error handling |
| `test_date_inference.py` | `core/date_inference.py` | Date priority, fallback logic |
| `test_folder_tagger.py` | `core/folder_tagger.py` | Classification, ignore/force lists |
| `test_renamer.py` | `core/renamer.py` | Patterns, conflicts |
| `test_sorter.py` | `core/sorter.py` | Destination computation |
| `test_scanner.py` | `core/scanner.py` | Directory iteration, filtering |
| `test_file_operations.py` | `core/file_operations.py` | Copy, move, dry-run |
| `test_workflow.py` | Integration | End-to-end scan→apply |

### Running Tests

```bash
# All tests
py -m pytest

# With coverage
py -m pytest --cov=chronoclean --cov-report=html

# Specific module
py -m pytest tests/unit/test_scanner.py

# Quick summary
py -m pytest --tb=short -q
```

---

## Dependencies

### pyproject.toml

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
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.0.0",
    "pytest-cov>=4.0.0",
]

[project.scripts]
chronoclean = "chronoclean.cli.main:app"
```

### Installed Versions (tested)

| Package | Version |
|---------|---------|
| Python | 3.14.2 |
| exifread | 3.5.1 |
| typer | 0.21.0 |
| PyYAML | 6.0.3 |
| Rich | 14.2.0 |
| pytest | 9.0.2 |
| pytest-mock | 3.14.0 |
| pytest-cov | 6.1.1 |

---

## Out of Scope for v0.1

The following features were explicitly **deferred** to later versions:

| Feature | Deferred To | Reason |
|---------|-------------|--------|
| Export command (JSON/CSV) | v0.2 | Not essential for prototype |
| Dedicated dryrun command | v0.2 | `apply --dry-run` covers this |
| Hash-based duplicate detection | v0.2 | Safety feature, not core |
| Filename date parsing | v0.2 | Detect dates in filenames like `IMG_090831.jpg` |
| Date mismatch warnings | v0.2 | Warn when filename date ≠ file date |
| Video metadata extraction | v0.3 | Requires ffmpeg/hachoir |
| Interactive prompts | v0.4 | UX enhancement |
| Parallel processing | v0.5 | Performance optimization |
| Tags classify/auto commands | v0.2 | Tag management can be manual |

---

## Commits

1. **`8a97979`** — feat: implement ChronoClean v0.1 with full test suite
   - 38 files changed, 8,248 insertions
   - Complete core modules, CLI, config, and 315 tests

2. **`6d48ef5`** — fix: improve CLI and date inference for v0.1
   - Added `--report/-r` flag to scan
   - Added `--move` flag to apply (default is now COPY)
   - Fixed date inference to prefer modification date over creation date
   - Added `execute_copies()` to BatchOperations

---

*Document version: 1.1*  
*Reflects actual implementation as of December 27, 2024*
