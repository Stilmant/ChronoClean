# ChronoClean v0.2 — Implementation Specification

**Version:** 0.2 (Export & Duplicate Detection)  
**Status:** Planning 📋  
**Last Updated:** 2024-12-27

---

## Table of Contents

1. [Overview](#overview)
2. [Goals for v0.2](#goals-for-v02)
3. [New Features](#new-features)
4. [Module Changes](#module-changes)
5. [CLI Commands](#cli-commands)
6. [Data Models](#data-models)
7. [Configuration Changes](#configuration-changes)
8. [Testing Requirements](#testing-requirements)
9. [Implementation Order](#implementation-order)
10. [Dependencies](#dependencies)

---

## Overview

### Purpose

v0.2 builds on the solid foundation of v0.1 to add:
1. **Filename date parsing** — Extract dates embedded in filenames
2. **Export functionality** — Save scan results to JSON/CSV for review
3. **Duplicate detection** — Hash-based detection on filename collision
4. **Improved reporting** — Better analysis and visibility

### Prerequisites

- v0.1 must be complete and stable
- All 315+ existing tests must pass
- No breaking changes to existing CLI commands

---

## Goals for v0.2

| Goal | Priority | Description |
|------|----------|-------------|
| Filename date parsing | P0 | Parse dates from filenames like `IMG_090831.jpg`, `2024-03-15_photo.jpg` |
| Date mismatch warnings | P0 | Warn when filename date differs from EXIF/filesystem date |
| Export to JSON | P0 | Export scan results for external review/editing |
| Export to CSV | P1 | Human-readable export format |
| Hash-based duplicate detection | P1 | Detect duplicates when destination filename collides |
| Config show command | P2 | Display current configuration |
| Report command | P2 | Detailed analysis output |

---

## New Features

### 1. Filename Date Parsing

**Purpose:** Extract dates embedded in filenames when EXIF is unavailable.

**Patterns to Recognize:**

| Pattern | Example | Extracted Date |
|---------|---------|----------------|
| `YYYYMMDD` anywhere | `IMG_20240315_143000.jpg` | 2024-03-15 |
| `YYMMDD` with underscore prefix | `IMG_090831.jpg` | 2009-08-31 |
| `YYYY-MM-DD` | `2024-03-15_photo.jpg` | 2024-03-15 |
| `YYYY_MM_DD` | `photo_2024_03_15.jpg` | 2024-03-15 |
| `DD-MM-YYYY` (configurable) | `15-03-2024_vacation.jpg` | 2024-03-15 |
| WhatsApp format | `IMG-20240315-WA0001.jpg` | 2024-03-15 |
| Screenshot format | `Screenshot_20240315_143000.png` | 2024-03-15 14:30:00 |

**Configuration:**
```yaml
filename_date:
  enabled: true
  patterns:
    - "YYYYMMDD"
    - "YYMMDD"
    - "YYYY-MM-DD"
    - "YYYY_MM_DD"
  year_cutoff: 30  # 2-digit years: 00-29 = 2000s, 30-99 = 1900s
  priority: "after_exif"  # before_exif, after_exif, after_filesystem
```

**Module:** `core/date_inference.py`
- New method: `_get_filename_date(file_path: Path) -> Optional[tuple[datetime, DateSource]]`
- New DateSource: `FILENAME`
- Update `priority` configuration to include `filename`

---

### 2. Date Mismatch Warnings

**Purpose:** Alert users when filename suggests a different date than EXIF/filesystem.

**Behavior:**
- Compare filename-derived date with EXIF date
- If difference > configurable threshold (default: 1 day), flag as mismatch
- Store mismatch info in `FileRecord`
- Display warnings in scan output
- Include in export

**FileRecord additions:**
```python
filename_date: Optional[datetime] = None
date_mismatch: bool = False
date_mismatch_days: Optional[int] = None
```

**Configuration:**
```yaml
date_mismatch:
  enabled: true
  threshold_days: 1
  warn_on_scan: true
```

---

### 3. Export to JSON

**Purpose:** Export scan results for external review, editing, and re-import.

**Command:** `chronoclean export json`

**Output Schema:**
```json
{
  "metadata": {
    "version": "0.2.0",
    "export_timestamp": "2024-03-15T14:30:00Z",
    "source_root": "/volume1/photos/unsorted",
    "total_files": 1000
  },
  "files": [
    {
      "source_path": "/volume1/photos/unsorted/Paris/IMG_1234.jpg",
      "file_type": "image",
      "size_bytes": 2500000,
      "detected_date": "2024-03-15T14:30:00",
      "date_source": "exif",
      "filename_date": "2024-03-15",
      "date_mismatch": false,
      "folder_tag": "Paris",
      "folder_tag_usable": true,
      "proposed_destination": "2024/03/IMG_1234.jpg",
      "proposed_filename": "20240315_143000.jpg",
      "has_exif": true,
      "hash_sha256": null,
      "duplicate_of": null
    }
  ],
  "folder_tags": {
    "Paris": {"usable": true, "reason": "meaningful", "count": 50},
    "DCIM": {"usable": false, "reason": "in_ignore_list", "count": 200}
  },
  "statistics": {
    "by_date_source": {"exif": 800, "filesystem_modified": 150, "filename": 50},
    "by_year": {"2024": 500, "2023": 300, "2022": 200},
    "mismatches": 10,
    "no_date": 5
  }
}
```

---

### 4. Export to CSV

**Purpose:** Human-readable spreadsheet format for manual review.

**Command:** `chronoclean export csv`

**Columns:**
- `source_path`
- `filename`
- `file_type`
- `size_mb`
- `detected_date`
- `date_source`
- `filename_date`
- `date_mismatch`
- `folder_tag`
- `tag_usable`
- `proposed_destination`
- `proposed_filename`
- `has_exif`

---

### 5. Hash-Based Duplicate Detection

**Purpose:** Detect identical files when destination filenames collide.

**Behavior:**
1. During `apply`, if destination file already exists:
   - Compute hash of source and destination
   - If hashes match → skip (duplicate)
   - If hashes differ → rename with suffix
2. Optional: Pre-scan for duplicates before apply

**Module:** `core/duplicate_checker.py` (new)

**Class: `DuplicateChecker`**
- `compute_hash(file_path: Path, algorithm: str = "sha256") -> str`
- `are_duplicates(file1: Path, file2: Path) -> bool`
- `find_duplicates_in_batch(files: list[Path]) -> dict[str, list[Path]]`

**Configuration:**
```yaml
duplicates:
  enabled: true
  algorithm: "sha256"  # sha256, md5, xxhash
  on_collision: "check_hash"  # check_hash, rename, skip, fail
  cache_hashes: true
```

**FileRecord additions:**
```python
file_hash: Optional[str] = None
duplicate_of: Optional[Path] = None
is_duplicate: bool = False
```

---

### 6. Config Show Command

**Purpose:** Display current effective configuration.

**Command:** `chronoclean config show`

**Output:**
```
ChronoClean Configuration
=========================

Source: chronoclean.yaml (merged with defaults)

general:
  timezone: local
  recursive: true
  ...

sorting:
  folder_structure: YYYY/MM
  ...

[Config file location: /path/to/chronoclean.yaml]
```

**Options:**
- `--json`: Output as JSON
- `--section <name>`: Show only specific section

---

### 7. Report Command

**Purpose:** Generate detailed analysis report from scan.

**Command:** `chronoclean report <source>`

**Output Sections:**
1. **Summary** — File counts, date source breakdown
2. **Date Analysis** — Date distribution by year/month
3. **Folder Tags** — All detected tags with classification
4. **Date Mismatches** — Files with conflicting dates
5. **Issues** — Files without dates, errors

**Options:**
- `--format <text|json|html>`: Output format
- `--output <file>`: Save to file
- `--section <name>`: Show specific section only

---

## Module Changes

### Existing Modules

| Module | Changes |
|--------|---------|
| `core/models.py` | Add `filename_date`, `date_mismatch`, `file_hash`, `duplicate_of` to FileRecord |
| `core/date_inference.py` | Add `_get_filename_date()`, new `FILENAME` DateSource, update priority handling |
| `core/scanner.py` | Integrate filename date extraction, compute mismatches |
| `core/file_operations.py` | Integrate duplicate checking before copy/move |
| `config/schema.py` | Add `FilenameDate`, `DateMismatch`, update `DuplicatesConfig` |
| `cli/main.py` | Add `export`, `config`, `report` command groups |

### New Modules

| Module | Purpose |
|--------|---------|
| `core/duplicate_checker.py` | Hash computation and duplicate detection |
| `core/exporter.py` | JSON/CSV export functionality |
| `cli/export_cmd.py` | Export subcommands |
| `cli/config_cmd.py` | Config subcommands |
| `cli/report_cmd.py` | Report command |

---

## CLI Commands

### Export Commands

```bash
# Export scan results to JSON
chronoclean export json <source> [options]
  --output, -o <file>     Output file (default: stdout)
  --destination, -d <dir> Include proposed destinations
  --hashes               Compute file hashes
  --config, -c <file>    Config file

# Export scan results to CSV  
chronoclean export csv <source> [options]
  --output, -o <file>     Output file (default: chronoclean_export.csv)
  --destination, -d <dir> Include proposed destinations
  --config, -c <file>    Config file
```

### Config Commands

```bash
# Show current configuration
chronoclean config show [options]
  --json                 Output as JSON
  --section <name>       Show specific section
```

### Report Command

```bash
# Generate analysis report
chronoclean report <source> [options]
  --format <text|json>   Output format (default: text)
  --output, -o <file>    Save to file
  --recursive/--no-recursive
  --config, -c <file>    Config file
```

### Updated Scan Command

```bash
chronoclean scan <source> [options]
  # Existing options...
  --check-mismatches     Check for date mismatches (default: true)
  --warn-mismatches      Show mismatch warnings (default: true)
```

---

## Data Models

### Updated FileRecord

```python
@dataclass
class FileRecord:
    # Existing fields...
    
    # New: Filename date
    filename_date: Optional[datetime] = None
    
    # New: Date mismatch detection
    date_mismatch: bool = False
    date_mismatch_days: Optional[int] = None
    
    # New: Duplicate detection
    file_hash: Optional[str] = None
    duplicate_of: Optional[Path] = None
    is_duplicate: bool = False
```

### New: ExportResult

```python
@dataclass
class ExportResult:
    """Result of exporting scan data."""
    
    format: str  # "json" or "csv"
    output_path: Optional[Path]
    files_exported: int
    export_timestamp: datetime
    metadata: dict
```

### Updated DateSource Enum

```python
class DateSource(Enum):
    EXIF = "exif"
    FILESYSTEM_CREATED = "filesystem_created"
    FILESYSTEM_MODIFIED = "filesystem_modified"
    FOLDER_NAME = "folder_name"
    FILENAME = "filename"  # New
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"
```

---

## Configuration Changes

### New Sections

```yaml
# Filename date extraction
filename_date:
  enabled: true
  patterns:
    - "YYYYMMDD_HHMMSS"  # 20240315_143000
    - "YYYYMMDD"          # 20240315
    - "YYMMDD"            # 090831
    - "YYYY-MM-DD"        # 2024-03-15
    - "YYYY_MM_DD"        # 2024_03_15
  year_cutoff: 30
  priority: "after_exif"

# Date mismatch detection
date_mismatch:
  enabled: true
  threshold_days: 1
  warn_on_scan: true
  include_in_export: true

# Export settings
export:
  default_format: "json"
  include_statistics: true
  include_folder_tags: true
  pretty_print: true
  
# Updated duplicates section
duplicates:
  enabled: true
  algorithm: "sha256"
  on_collision: "check_hash"
  cache_hashes: true
  cache_location: ".chronoclean/hash_cache.db"
```

### Updated Schema Classes

```python
@dataclass
class FilenameDateConfig:
    enabled: bool = True
    patterns: list[str] = field(default_factory=lambda: [
        "YYYYMMDD_HHMMSS", "YYYYMMDD", "YYMMDD", "YYYY-MM-DD"
    ])
    year_cutoff: int = 30
    priority: str = "after_exif"

@dataclass
class DateMismatchConfig:
    enabled: bool = True
    threshold_days: int = 1
    warn_on_scan: bool = True
    include_in_export: bool = True

@dataclass
class ExportConfig:
    default_format: str = "json"
    include_statistics: bool = True
    include_folder_tags: bool = True
    pretty_print: bool = True
```

---

## Testing Requirements

### New Test Files

| File | Coverage |
|------|----------|
| `test_filename_date.py` | Filename date pattern matching |
| `test_duplicate_checker.py` | Hash computation, duplicate detection |
| `test_exporter.py` | JSON/CSV export |
| `test_export_cmd.py` | Export CLI commands |
| `test_config_cmd.py` | Config CLI commands |
| `test_report_cmd.py` | Report CLI command |

### Test Scenarios

**Filename Date Parsing:**
- Parse `IMG_20240315_143000.jpg` → 2024-03-15 14:30:00
- Parse `IMG_090831.jpg` → 2009-08-31
- Parse `2024-03-15_photo.jpg` → 2024-03-15
- Parse `Screenshot_20240315-143000.png` → 2024-03-15 14:30:00
- Parse `IMG-20240315-WA0001.jpg` (WhatsApp) → 2024-03-15
- Handle invalid dates gracefully
- Handle ambiguous formats (configurable DD-MM vs MM-DD)

**Date Mismatch:**
- Detect mismatch when filename says 2024 but EXIF says 2023
- No mismatch warning when dates match
- Configurable threshold (1 day, 7 days, etc.)
- Handle missing dates gracefully

**Export JSON:**
- Correct JSON schema
- All file records included
- Statistics calculated correctly
- Folder tags included
- Handle special characters in paths

**Export CSV:**
- Correct CSV format with headers
- Handle commas and quotes in data
- Date formatting consistent
- File sizes in MB

**Duplicate Detection:**
- Detect identical files by hash
- Handle large files efficiently
- Cache hash values
- Correct behavior on collision

### Test Count Target

- **New unit tests:** ~80-100
- **New integration tests:** ~15-20
- **Total after v0.2:** ~400+ tests

---

## Implementation Order

### Phase 1: Filename Date Parsing
1. Add `FILENAME` to `DateSource` enum
2. Implement `_get_filename_date()` in `date_inference.py`
3. Add filename date patterns configuration
4. Update `DateInferenceEngine` priority handling
5. Write tests for filename date parsing

### Phase 2: Date Mismatch Detection
1. Add mismatch fields to `FileRecord`
2. Implement mismatch detection in `Scanner`
3. Add mismatch configuration
4. Update scan output to show warnings
5. Write tests for mismatch detection

### Phase 3: Duplicate Checker Module
1. Create `core/duplicate_checker.py`
2. Implement hash computation
3. Implement duplicate detection
4. Add hash caching (optional)
5. Write tests for duplicate checker

### Phase 4: Export Functionality
1. Create `core/exporter.py`
2. Implement JSON export
3. Implement CSV export
4. Create `cli/export_cmd.py`
5. Write tests for export

### Phase 5: Config & Report Commands
1. Create `cli/config_cmd.py`
2. Create `cli/report_cmd.py`
3. Integrate with main CLI
4. Write tests for new commands

### Phase 6: Integration
1. Integrate duplicate checking into `apply`
2. Update scan output with new features
3. Integration tests
4. Documentation updates

---

## Dependencies

### New Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| `xxhash` | Fast hashing for large files | Optional |

### Updated pyproject.toml

```toml
[project]
version = "0.2.0"
dependencies = [
    "exifread>=3.0.0",
    "typer>=0.9.0",
    "pyyaml>=6.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
fast = [
    "xxhash>=3.0.0",  # Optional: faster hashing
]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.0.0",
    "pytest-cov>=4.0.0",
]
```

---

## Migration Notes

### From v0.1 to v0.2

- **No breaking changes** to existing commands
- Existing configs remain valid (new fields have defaults)
- New features are opt-in via configuration
- `scan` command gains mismatch warnings (can be disabled)

### Configuration Migration

v0.1 configs work unchanged. New features activate when:
1. `filename_date.enabled: true` (default)
2. `date_mismatch.enabled: true` (default)
3. `duplicates.enabled: true` (default)

---

## Success Criteria

v0.2 is complete when:

- [ ] Filename dates extracted from common patterns
- [ ] Date mismatch warnings displayed in scan
- [ ] `chronoclean export json` works
- [ ] `chronoclean export csv` works
- [ ] `chronoclean config show` works
- [ ] `chronoclean report` works
- [ ] Duplicate detection on collision works
- [ ] All new tests pass (~400+ total)
- [ ] Documentation updated
- [ ] No regressions in v0.1 functionality

---

*Document version: 1.0*  
*Planning document for ChronoClean v0.2*
