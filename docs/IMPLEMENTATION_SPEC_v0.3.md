# ChronoClean v0.3 - Video & Advanced Metadata

**Version:** 0.3 (Video & Advanced Metadata)  
**Status:** Planned  
**Last Updated:** 2025-12-29

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Goals for v0.3](#goals-for-v03)
4. [New Features](#new-features)
5. [Module Changes](#module-changes)
6. [Data Model Changes](#data-model-changes)
7. [Configuration Changes](#configuration-changes)
8. [CLI Changes](#cli-changes)
9. [Testing Requirements](#testing-requirements)
10. [Implementation Order](#implementation-order)
11. [Success Criteria](#success-criteria)

---

## Overview

v0.3 extends ChronoClean beyond images by extracting metadata from videos and
unifying date inference across all file types. It also decouples folder-tag
appending from date renaming so tags can be applied while preserving original
camera filenames. Error reporting becomes clearer and more actionable, while
optional heuristics remain deterministic and opt-in.

### Current State (v0.2.1)

The codebase already supports:
- **Video file detection:** `FileType.VIDEO` enum exists, scanner classifies videos
- **Video extensions:** Configurable list in `scan.video_extensions`
- **Include/exclude videos:** `--videos/--no-videos` CLI flag
- **Date inference pipeline:** Priority-based with EXIF, filesystem, filename, folder_name

What's missing:
- **Video metadata extraction:** Videos fall back to filesystem/filename dates only
- **Tag-only mode:** `--tag-names` currently requires `--rename` to be effective
- **Granular error reporting:** Errors are logged but not summarized by category

---

## Prerequisites

- v0.2.1 complete and stable
- All 511+ existing tests passing
- No breaking changes to existing CLI commands

---

## Goals for v0.3

| Goal | Priority | Description |
|------|----------|-------------|
| Video metadata extraction | P0 | Extract capture date for video files via `ffprobe` or `hachoir` |
| Unified date resolution | P0 | One priority-based date pipeline for images and videos |
| Tag-only filenames | P1 | `--tag-names` appends tags even when `--rename` is off |
| Improved metadata logging | P1 | Clear per-file reasons + summary counts by error category |
| Optional heuristics | P2 | Deterministic fallback clustering for files with no metadata |

---

## New Features

### 1) Video Metadata Extraction

**Purpose:** Infer a reliable capture date for video files, equivalent to EXIF for images.

**Approach options:**

| Provider | Pros | Cons |
|----------|------|------|
| `ffprobe` (preferred) | Fast, accurate, handles all formats | External binary required |
| `hachoir` | Pure Python, no external deps | Slower, limited format support |

**Implementation:**

Create new module `core/video_metadata.py`:

```python
class VideoMetadataReader:
    """Extract metadata from video files."""
    
    def __init__(self, provider: str = "ffprobe", ffprobe_path: str = "ffprobe"):
        self.provider = provider
        self.ffprobe_path = ffprobe_path
    
    def get_creation_date(self, path: Path) -> Optional[datetime]:
        """Extract creation/recording date from video metadata."""
        if self.provider == "ffprobe":
            return self._ffprobe_date(path)
        elif self.provider == "hachoir":
            return self._hachoir_date(path)
        return None
```

**Metadata fields to check (priority order):**
1. `creation_time` (QuickTime/MP4)
2. `date` / `DATE` tags
3. `com.apple.quicktime.creationdate`
4. `DateTimeOriginal` (if present)

**Behavior:**
- When metadata is present, use it as the primary date source for videos
- If metadata is missing/unusable, fall back to configured priority (filename, filesystem, folder_name)
- Output should clearly label the date source as `video_metadata`

**Synology considerations:**
- `ffprobe` is available via `ffmpeg` package from SynoCommunity
- Document installation: `opkg install ffmpeg` or via Package Center
- Provide fallback to `hachoir` for systems without ffprobe

---

### 2) Unified Date Resolution

**Purpose:** Apply a consistent date inference policy across images and videos.

**Current state:**
- `DateSource` enum has: EXIF, FILESYSTEM_CREATED, FILESYSTEM_MODIFIED, FOLDER_NAME, FILENAME, HEURISTIC, UNKNOWN
- Date inference priority is configurable via `sorting.fallback_date_priority`

**Changes required:**
- Add new `DateSource.VIDEO_METADATA` value
- Treat `video_metadata` like `exif` in the priority system
- Scanner should detect file type and route to appropriate metadata reader

**Updated priority handling:**

```python
# Priority list now supports both image and video metadata
DEFAULT_PRIORITY = ["exif", "video_metadata", "filename", "filesystem", "folder_name"]

# In DateInferenceEngine:
def infer_date(self, path: Path, file_type: FileType) -> tuple[Optional[datetime], DateSource]:
    for source in self.priority:
        if source == "exif" and file_type in (FileType.IMAGE, FileType.RAW):
            date = self.exif_reader.get_date(path)
            if date:
                return date, DateSource.EXIF
        elif source == "video_metadata" and file_type == FileType.VIDEO:
            date = self.video_reader.get_creation_date(path)
            if date:
                return date, DateSource.VIDEO_METADATA
        # ... other sources
```

---

### 3) Tag-Only Filenames (Decoupled from Rename)

**Purpose:** Allow tagging without changing the core filename format.

**Current behavior:**
- `--tag-names` adds folder tag to the renamed filename
- If `--rename` is off, the original filename is preserved, and tags are not applied

**New behavior:**
- `--tag-names` can append tags even when `--rename` is off
- Original camera filename is preserved, tag is appended before extension

**Examples:**

| Original | --rename off, --tag-names | --rename on, --tag-names |
|----------|---------------------------|--------------------------|
| `IMG_0001.jpg` | `IMG_0001_ParisTrip.jpg` | `20240315_143000_ParisTrip.jpg` |
| `DSC01234.jpg` | `DSC01234_Wedding.jpg` | `20240620_160000_Wedding.jpg` |

**Implementation:**

Modify `core/renamer.py`:

```python
def generate_filename(
    self,
    record: FileRecord,
    rename_enabled: bool,
    tag_names_enabled: bool,
) -> str:
    if rename_enabled:
        # Full rename with date pattern + optional tag
        base = self._format_date_pattern(record)
    else:
        # Keep original filename (without extension)
        base = record.source_path.stem
    
    if tag_names_enabled and record.folder_tag_usable:
        base = f"{base}_{record.folder_tag}"
    
    return f"{base}{record.extension}"
```

**CLI change:**
- `--tag-names` becomes independent of `--rename`
- Help text updated to clarify: "Add folder tags to filenames (works with or without --rename)"

---

### 4) Improved Metadata Error Handling

**Purpose:** Make failures actionable with clear per-file reasons and summary counts.

**Current state:**
- `FileRecord.exif_error` stores error message
- Errors are logged but not categorized
- Summary only shows `error_files` count

**New behavior:**

**Error categories:**
- `exif_read_error` — Failed to read EXIF data
- `exif_parse_error` — EXIF present but date field unparseable
- `video_metadata_error` — Failed to extract video metadata
- `video_metadata_missing` — Video has no creation date
- `no_date_found` — No date from any source
- `file_access_error` — Permission or I/O error

**FileRecord additions:**
```python
error_category: Optional[str] = None  # categorized error type
```

**ScanResult additions:**
```python
errors_by_category: dict[str, int] = field(default_factory=dict)
```

**Scan output example:**
```
Scan complete: 1000 files processed

Date sources:
  EXIF:            720 (72%)
  Video metadata:   80 (8%)
  Filename:         50 (5%)
  Filesystem:      120 (12%)
  Unknown:          30 (3%)

Warnings:
  Date mismatches:  15

Errors by category:
  exif_parse_error:       10
  video_metadata_error:    5
  no_date_found:          15
```

---

### 5) Optional Heuristics (Deterministic)

**Purpose:** Improve outcomes for files with no metadata.

**Constraints:**
- Must be opt-in (disabled by default)
- Must be deterministic (same input = same output)

**Approach: Directory clustering**

When a file has no date, look at siblings in the same directory:
1. Collect dates from files in the same folder
2. If majority have dates within N days of each other, assume this file belongs to same event
3. Use the median date of the cluster

**Configuration:**
```yaml
heuristic:
  enabled: false  # opt-in
  max_days_from_cluster: 2
  min_cluster_size: 3  # minimum files with dates to form cluster
```

**Note:** Config section `heuristic` already exists with `enabled` and `max_days_from_cluster` fields.

---

## Module Changes

### Core Modules

| Module | Change |
|--------|--------|
| `core/video_metadata.py` | **NEW** — Video metadata extraction |
| `core/models.py` | Add `DateSource.VIDEO_METADATA`, `FileRecord.error_category` |
| `core/date_inference.py` | Integrate video metadata, pass file_type to infer_date |
| `core/scanner.py` | Use video metadata reader, populate error categories, summarize |
| `core/renamer.py` | Support tag-only mode without rename |
| `core/exporter.py` | Include `video_metadata` in date_source breakdown |

### CLI Changes

| Command | Change |
|---------|--------|
| `scan` | Display video metadata counts, error category summary |
| `apply` | `--tag-names` works independently of `--rename` |
| `export` | Include video metadata and error categories in output |

---

## Data Model Changes

### DateSource (models.py)

```python
class DateSource(Enum):
    EXIF = "exif"
    VIDEO_METADATA = "video_metadata"  # NEW
    FILESYSTEM_CREATED = "filesystem_created"
    FILESYSTEM_MODIFIED = "filesystem_modified"
    FOLDER_NAME = "folder_name"
    FILENAME = "filename"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"
```

### FileRecord (models.py)

```python
# v0.3 additions
video_metadata_date: Optional[datetime] = None  # raw video creation date
error_category: Optional[str] = None  # categorized error type
```

### ScanResult (models.py)

```python
# v0.3 additions
errors_by_category: dict[str, int] = field(default_factory=dict)
```

---

## Configuration Changes

### New Section: video_metadata

```yaml
video_metadata:
  enabled: true
  provider: "ffprobe"        # ffprobe, hachoir
  ffprobe_path: "ffprobe"    # path to ffprobe binary
  fallback_to_hachoir: true  # use hachoir if ffprobe unavailable
  skip_errors: true          # continue on metadata read failures
```

### Updated Section: sorting

```yaml
sorting:
  folder_structure: "YYYY/MM"
  # Updated default to include video_metadata
  fallback_date_priority: ["exif", "video_metadata", "filename", "filesystem", "folder_name"]
  include_day: false
```

### Updated Section: heuristic

```yaml
heuristic:
  enabled: false             # opt-in (default was true, changing to false for safety)
  max_days_from_cluster: 2
  min_cluster_size: 3        # NEW: minimum files needed to form a cluster
```

---

## CLI Changes

### scan command

No new flags. Video metadata extraction is automatic for video files.

Output changes:
- Date source breakdown includes `video_metadata`
- New "Errors by category" section

### apply command

```
--tag-names / --no-tag-names   Add folder tags to filenames
                               (works with or without --rename)
```

Help text clarifies independent operation from `--rename`.

### export command

JSON/CSV output includes:
- `video_metadata` as possible date_source value
- `error_category` field per file
- Statistics include video_metadata counts

---

## Testing Requirements

### New Test Files

**`tests/unit/test_video_metadata.py`:**
- Provider initialization (ffprobe, hachoir)
- Date extraction from various video formats (mocked)
- Missing metadata handling
- ffprobe unavailable fallback

### Extended Tests

**`tests/unit/test_date_inference.py`:**
- Priority order with video_metadata
- Video files skip EXIF reader
- Mixed image/video directories

**`tests/unit/test_scanner.py`:**
- Videos get VideoMetadataReader routed
- Error category population
- ScanResult.errors_by_category counts

**`tests/unit/test_renamer.py`:**
- Tag-only mode (rename off, tag-names on)
- Tag ignored when already in filename
- Combined rename + tag mode unchanged

**`tests/unit/test_exporter.py`:**
- video_metadata in date_source stats
- error_category in file records

### Integration Tests

**`tests/integration/test_video_workflow.py`:**
- End-to-end scan with video files
- Apply with video files and tag-only mode

---

## Implementation Order

| Phase | Task | Estimated Effort |
|-------|------|------------------|
| 1 | Add `DateSource.VIDEO_METADATA` to models | 0.5h |
| 2 | Create `core/video_metadata.py` with ffprobe provider | 3h |
| 3 | Add hachoir fallback provider | 2h |
| 4 | Integrate video metadata into DateInferenceEngine | 2h |
| 5 | Update Scanner to use video metadata reader | 1h |
| 6 | Implement error categories in FileRecord/ScanResult | 1h |
| 7 | Update scan output with error category summary | 1h |
| 8 | Decouple tag-only mode in Renamer | 2h |
| 9 | Update CLI apply command help text | 0.5h |
| 10 | Update Exporter for video_metadata/error_category | 1h |
| 11 | Add video_metadata config section | 1h |
| 12 | Write tests | 4h |
| 13 | Documentation updates | 1h |
| **Total** | | **~20h** |

---

## Success Criteria

- [ ] Video files produce reliable capture dates when metadata exists
- [ ] `video_metadata` appears in date source breakdown for videos
- [ ] One consistent priority system for images and videos
- [ ] `--tag-names` appends tags even when `--rename` is off
- [ ] Scan output shows error counts by category
- [ ] Export includes video_metadata source and error categories
- [ ] All existing tests pass (no regressions)
- [ ] New test coverage for video metadata and tag-only mode
- [ ] Synology installation notes for ffprobe

---

*Document version: 0.2*  
*Planned scope for ChronoClean v0.3*
