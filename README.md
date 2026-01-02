# ChronoClean

![Status](https://img.shields.io/badge/status-v0.3.4_prototype-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-SynologyNAS-lightgrey)
![Maintained](https://img.shields.io/badge/maintained-yes-success)

---

<p align="center">
  <img src=".github/assets/chronoclean-logo.png" width="320" alt="ChronoClean Logo">
</p>

<h2 align="center">Restore Time. Restore Order.</h2>

---

## Project Vision
Over the years, photo collections accumulate in many places: phones, cameras, messaging apps, backups, cloud exports, USB drives, “miscellaneous” folders on a NAS, and even old SD cards.
The result is usually a chaotic archive of:

- inconsistent naming conventions
- missing or broken EXIF dates
- photos in wrong folders
- duplicates scattered everywhere
- folders with meaningless names
- unsorted collections imported from past devices

**ChronoClean** is a practical, conservative tool whose goal is simple:
Reorganize decades of photos into a clean, consistent chronological structure, with safe renaming rules and optional folder-name tagging.

It is designed for real-life usage on large libraries (50k–300k files), including preparation for long-term archival on systems like a Synology NAS.

---
## Why the Name “ChronoClean”?
ChronoClean reflects the tool’s purpose:
- **Chrono** – time-based ordering at the heart of the system
- **Clean** – removing clutter, inconsistencies, duplicates, and chaotic structures

It focuses on rebuilding a clean chronological library without aggressively deduplicating or altering media unless needed.

---
## Purpose of the Tool

ChronoClean restores order to photo collections by:

- Reading EXIF timestamps when available
- Using fallback logic when EXIF is missing
- Organizing files into a time-based hierarchy
- Optionally renaming files using a standard pattern
- Optionally tagging filenames with relevant folder names
- Providing dry-run and export analysis before modifying anything
- Ensuring safe handling of duplicates or filename conflicts

The philosophy is:

- Predictable output
- Minimal risk
- Clear visibility before acting
- User-controlled decisions

ChronoClean does not attempt complex AI deduplication or modification of image contents.

---


## Features Overview

### Sorting & Organization
- EXIF-based sorting into a chronological folder hierarchy (year/month) (day optional)
- Video metadata extraction for MP4, MOV, MKV, etc. (v0.3)
- Fallback to creation/modification timestamp when EXIF is missing
- Optionally infer date from directory name if metadata is absent
- Consistent, predictable tree structure suitable for NAS archives and long-term storage

### File Renaming (Optional)
- Disabled by default; original filenames are preserved unless renaming is enabled
- Configurable renaming rules for standard, readable patterns
- Configurable folder-tag insertion for context-rich filenames
- Tag-only mode: add tags without full renaming (v0.3)
- Prevents double-tagging and name inflation

### Dry Run System
Two levels:
- **Dry-run console output**: shows exactly what would be done, without making changes
- **Export report** (current `export` command): JSON or CSV including:
  - source path and filename
  - detected date and date source (EXIF, filesystem, filename, video_metadata)
  - date mismatch detection (when filename date ≠ EXIF/file date)
  - error categories for troubleshooting (v0.3)

This export can be reviewed before applying changes.

### Duplicate Management
- Only checked when needed (filename clash after sorting/renaming)
- Uses SHA256 for reliable comparison (MD5 optional via config)
- If same hash → skip second copy
- If different → rename second file safely to avoid collision

### Folder-Tag Logic
- Identify meaningful folder names for possible filename enrichment
- Detect if folder name already appears in filenames (distance-based logic)
- Tag enrichment is optional and user-controlled
- Possibility to maintain allow/ignore lists for folder tags

### NAS Compatibility
- Designed with Synology usage in mind
- Works on Python 3 installed on Synology
- Can be executed manually or via Task Scheduler
- Works well with shared folders and large volumes
- Instructions provided for installing dependencies and running the tool on Synology DSM

---

## Core Use Cases
1. **Clean chronological sorting**

Photo libraries often contain a mix of sources: phone backups, WhatsApp exports, SD card dumps, and more. ChronoClean reorganizes them into a clear, time-based structure:

```
2024/
  01/
  02/
2025/
  01/
  02/
```

Files are moved based on EXIF or fallback dates, ensuring chronological order regardless of original folder or filename chaos.

2. **Optional file renaming**

Many users prefer to keep original names, so ChronoClean provides renaming as optional, not default. When enabled, files are renamed using a standard, readable pattern:

```
20240214_153200.jpg
```

Or, with a folder tag for context:

```
20240214_153200_ParisTrip.jpg
```

3. **Folder-name influence**

Some folders contain meaningful names (e.g., “Paris 2022”, “SkiTrip”, “Mariage Julie”, “Naomie Anniversary”), while others are generic or unhelpful (e.g., “tosort”, “unsorted”, “misc”, “downloaded”).

ChronoClean allows you to:
- Tag folder names for filename enrichment
- Ignore folder names that are not informative
- Detect if the folder name is already present in filenames (using a similarity/distance check)

Folder tag detection is automatic during scan and apply. Configuration allows setting
ignore/force lists to control which folder names are used as tags.

4. **Duplicate handling**

Duplicate detection is not a feature goal but a safety mechanism:

If two files collide on filename (after sorting), ChronoClean checks their hashes.
- If identical: only one copy is kept (depending on options).
- If different: filename is adjusted to avoid collision.

ChronoClean does not attempt full-library deduplication unless explicitly requested.

---

## Workflow
ChronoClean supports two workflows (the second is planned for v0.4).

### 1) Quick workflow (today)
1. **Scan** - analyze directories, read EXIF, classify folder names.
2. **Dry run apply** - simulate actions (`apply` defaults to dry-run).
3. **Apply** - perform sorting, moves, renames, and conflict resolution.

### 2) Plan-based workflow (planned v0.5)
This workflow introduces an explicit, reviewable plan file for large/messy imports.
1. **Scan/report** - generate analysis output for review (JSON/CSV).
2. **Plan** - generate an executable plan file (JSON) that includes destinations + final names + decisions.
3. **Dry run from plan** - simulate the plan without touching disk.
4. **Apply from plan** - execute exactly what the reviewed plan specifies.

Planned command split for clarity:
- `report ...` = analysis output (what was detected)
- `plan ...` = executable plan (what will be done)

---

## Ideal Use Cases

### Minimal (quick, one folder)
Use when you just want to organize a folder, with a safety dry-run first:

```bash
python -m chronoclean apply D:\photos\incoming D:\photos\archive --dry-run
python -m chronoclean apply D:\photos\incoming D:\photos\archive --no-dry-run
```

Optional (info-only):

```bash
python -m chronoclean scan D:\photos\incoming
```

### Safe archival (copy + verify + optional cleanup)
Use when you want cryptographic confirmation before deleting sources:

```bash
python -m chronoclean apply D:\photos\incoming D:\photos\archive --no-dry-run
python -m chronoclean verify --last
python -m chronoclean cleanup --only ok --dry-run
python -m chronoclean cleanup --only ok --no-dry-run
```

### Recovery (you forgot the apply report)
Use when you copied files but did not keep a run report:

```bash
python -m chronoclean verify --source D:\photos\incoming --destination D:\photos\archive --reconstruct
python -m chronoclean cleanup --only ok --no-dry-run
```

## High-Level Structure (indicative)
```
chronoclean/
  cli/
  core/
    exif_reader.py
    date_inference.py
    sorter.py
    renamer.py
    folder_tagging.py
    duplicate_checker.py
    export_plan.py
  utils/
  tests/
README.md
```

---


## Tech Stack (Flexible)

ChronoClean is implemented in **Python 3** for its readability, ecosystem, and easy deployment on Synology NAS.


The following libraries are recommended but not mandatory:
- **Pillow** (image metadata): Used for general image processing and reading/writing image metadata, including basic EXIF extraction and manipulation. Pillow is versatile and works with many image formats, but for advanced or lossless EXIF editing, see below.
- **piexif** or **exifread** (EXIF handling):
  - **piexif** is ideal for lossless EXIF extraction, insertion, and modification, especially when you need to preserve all metadata exactly or write EXIF back to files. It is more specialized for EXIF than Pillow.
  - **exifread** is focused on reading EXIF data only (no writing), and is robust for extracting metadata from a wide range of JPEGs and TIFFs.
- **hachoir** or **ffprobe** (video metadata - v0.3):
  - **ffprobe** (part of FFmpeg) is the preferred provider for extracting creation dates from video files. It's fast and handles most formats including MP4, MOV, MKV, AVI.
  - **hachoir** is a pure Python fallback that requires no external installation but supports fewer formats and is slower.
  - ChronoClean automatically uses ffprobe if available, falling back to hachoir otherwise.
- **hashlib** (hashing):
  - Provides cryptographic hashes (SHA256, MD5) for duplicate detection.
  - Included in Python's standard library; reliable and portable.
- **Typer** or **Argparse** (CLI):
  - **Typer** is a modern, user-friendly CLI framework based on Python type hints, making it easy to build intuitive command-line tools.
  - **Argparse** is Python’s built-in CLI parser, stable and widely supported, but with a more traditional interface.
- **pytest** (testing): Used for writing and running automated tests, ensuring code reliability and correctness.

Alternatives may be chosen depending on portability and Synology constraints.

---

## Development Installation (local)

This section is for local development (tests, linting). On a NAS, follow `docs/SYNOLOGY_INSTALLATION.md`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```


## Synology NAS Installation (Overview)
ChronoClean requires **Python 3.10+**. On many Synology DSM setups, **Package Center** only provides Python up to **3.9**, so the recommended approach is to install a newer Python via **Entware**.

See the dedicated guide: `docs/SYNOLOGY_INSTALLATION.md`.

Quick usage reminder (after install):

```bash
# Analyze files
chronoclean scan /volume1/photos
chronoclean scan /volume1/photos --report  # Detailed per-file report

# Review folder tag classifications (v0.3.4)
chronoclean tags list /volume1/photos
chronoclean tags classify "Paris 2024" use --tag "ParisTrip"
chronoclean tags classify "temp" ignore

# Export scan results (v0.2)
chronoclean export json /volume1/photos -o results.json
chronoclean export csv /volume1/photos -o results.csv

# Export with destination preview (v0.3.4)
chronoclean export json /volume1/photos --destination /volume1/archive -o preview.json

# Organize files (dry-run by default)
chronoclean apply /volume1/unsorted /volume1/photos

# Apply changes with copy (safe)
chronoclean apply /volume1/unsorted /volume1/photos --no-dry-run

# Apply changes with move
chronoclean apply /volume1/unsorted /volume1/photos --no-dry-run --move
```

Optionally schedule via DSM Task Scheduler.

---

## Best-Practice Notes
- **Run on a copy of your library the first time**: Always test ChronoClean on a duplicate or backup of your photo collection to ensure the results match your expectations and to prevent accidental data loss.
- **Use the export report to tune tagging rules**: Review and edit the export (JSON/CSV) to refine folder-tagging, renaming, and conflict resolution before applying changes.
- **Ensure you have enough space for temporary moves**: Large reorganizations may require extra disk space for file operations, especially when working with tens of thousands of files.

---

## Configuration

ChronoClean can be configured via YAML files. Create a `chronoclean.yaml` in your project root:

```yaml
# Minimal config example
sorting:
  folder_structure: "YYYY/MM/DD"

folder_tags:
  enabled: true
  ignore_list: ["tosort", "misc", "temp"]

renaming:
  enabled: true
  pattern: "{date}_{time}"
```

**Config file search order:**
1. `--config <path>` argument
2. `chronoclean.yaml` in current directory
3. `.chronoclean/config.yaml`
4. Built-in defaults

**CLI arguments always override config file values.**

📄 **See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for complete configuration reference.**

---


## Roadmap

ChronoClean development follows a phased approach from prototype to production-ready tool.

> 📄 **See [docs/IMPLEMENTATION_SPEC_v0.1.md](docs/IMPLEMENTATION_SPEC_v0.1.md) for v0.1 implementation details.**  
> 📄 **See [docs/IMPLEMENTATION_SPEC_v0.2.md](docs/IMPLEMENTATION_SPEC_v0.2.md) for v0.2 implementation details.**  
> 📄 **See [docs/IMPLEMENTATION_SPEC_v0.3.md](docs/IMPLEMENTATION_SPEC_v0.3.md) for v0.3 planning.**  
> 📄 **See [docs/IMPLEMENTATION_SPEC_v0.3.1.md](docs/IMPLEMENTATION_SPEC_v0.3.1.md) for v0.3.1 planning.**  
> 📄 **See [docs/IMPLEMENTATION_SPEC_v0.3.2.md](docs/IMPLEMENTATION_SPEC_v0.3.2.md) for v0.3.2 details.**  
> 📄 **See [docs/IMPLEMENTATION_SPEC_v0.4.md](docs/IMPLEMENTATION_SPEC_v0.4.md) for v0.4 planning.**  
> 📄 **See [docs/IMPLEMENTATION_SPEC_v0.5.md](docs/IMPLEMENTATION_SPEC_v0.5.md) for v0.5 planning.**  
> 📄 **See [docs/IMPLEMENTATION_SPEC_v0.6.md](docs/IMPLEMENTATION_SPEC_v0.6.md) for v0.6 planning.**

### v0.1 – Prototype ✅ Complete
- ✅ Project structure and configuration system (YAML-based)
- ✅ Data models (`FileRecord`, `ScanResult`, `OperationPlan`, `MoveOperation`)
- ✅ EXIF extraction and date parsing (images via `exifread`)
- ✅ Date inference engine with fallback priority (EXIF → filesystem → folder name)
- ✅ Chronological sorting into YYYY/MM folders (YYYY/MM/DD optional)
- ✅ Basic file renaming (optional, pattern-based with `{date}_{time}`)
- ✅ Folder tag detection (heuristics, ignore/force lists, fuzzy matching)
- ✅ Safe file operations (copy/move with dry-run, rollback support)
- ✅ CLI with Typer (`scan`, `apply`, `version`)
- ✅ Unit test suite (352 tests with pytest + pytest-mock)
- ✅ Dry-run mode (default) with `--no-dry-run` to apply
- ✅ Copy mode (default) with `--move` for moves
- ✅ Detailed scan report (`--report` flag)

### v0.2 – Export & Duplicate Detection
- ✅ Filename date parsing (detect dates in filenames like `IMG_090831.jpg`)
- ✅ Date mismatch detection (when filename date ≠ EXIF/file date)
- ✅ Export: JSON/CSV with detected dates, tags, target paths, mismatch info
- ✅ `export` command with `json` and `csv` subcommands
- ✅ Hash-based duplicate detection on filename collision (SHA256)
- ✅ Collision resolution strategies: check_hash, rename, skip, fail
- ✅ `config show` command to display current configuration
- Planned: `report` command for detailed analysis output

### v0.3 - Video & Advanced Metadata
- ✅ Video "taken date" extraction (choose backend: `ffprobe` vs `hachoir`) mapped into `DateSource.VIDEO_METADATA`
- ✅ Unified "best date" resolution across image+video metadata + filesystem + filename + folder-name (same priority system)
- ✅ Improved metadata error handling/logging (clear per-file reason + summary counts by category)
- ✅ Decouple tagging from date renaming; allow tag-only filenames (append tags even when `--rename` is off)
- Deferred to future: Optional heuristics for "no metadata" cases (config placeholder added)

### v0.3.1 - Verification & Safe Cleanup ✅ Complete
- ✅ Apply run record (captures `source -> destination` mapping for later verification)
- ✅ `verify` command (hash-based SHA-256; `--algorithm quick` for size-only)
- ✅ `cleanup` command to delete only sources verified OK (supports `--only ok`)
- ✅ Recovery path when the apply report was forgotten (`verify --reconstruct`)
- ✅ Auto-discovery of recent runs and verification reports with interactive prompts
- ✅ `--no-run-record` flag for apply when record not needed

### v0.3.2 - Doctor Command & Code Quality ✅ Complete
- ✅ `doctor` command to check system dependencies (ffprobe, hachoir, exiftool)
- ✅ `doctor --fix` to interactively update config with correct paths
- ✅ Searches common paths including `/opt/bin/ffprobe` (Synology DSM)
- ✅ CLI helpers refactoring to reduce code duplication
- ✅ Centralized component factory for scan/apply/verify commands

### v0.4 - Robust Apply & Resume
- Atomic copy (temp file + rename) to avoid partial destination files
- Persistent apply state on disk (plan + journal) for resume/retry on interruption
- Resume/detect incomplete runs and continue safely
- Detailed per-file error recording (not only a summary counter)
- Streaming execution to keep memory bounded on large libraries

### v0.5 - User Experience & Safety
- Unambiguous command split:
  - `report` = scan/analysis outputs (JSON/CSV)
  - `plan` = executable plan generation (JSON)
- `apply --from-plan <plan.json>` (deterministic execution of reviewed plans)
- `dryrun --from-plan <plan.json>` (optional; `apply --dry-run` remains for quick runs)
- `report` command(s) for scan/plan/apply summaries (mismatches, collisions, duplicates)
- Interactive review (Rich): confirm risky ops, inspect collisions, accept/reject tags/renames
- Conditional rename for garbage filenames (optional)
- Persistent state for tag decisions/overrides (separate from main YAML), plus optional `config set`
- Safety gates: disk-space check, live-mode warnings, backup reminders, clearer "what will change"

### v0.6 - NAS & Large-Scale Support
- Implement performance knobs: parallel scan/inference (configurable workers) and memory-efficient iteration
- Caching (SQLite) for metadata/hash results with invalidation strategy (mtime/size), to speed re-runs
- Synology DSM notes + headless/Task Scheduler friendly mode and recommended configs
- Optimize collision/duplicate handling for large batches (streaming plan generation, bounded caches)

### v1.0 – Stable Release
- Full conflict resolution and rollback support
- Comprehensive NAS documentation
- Extended CLI options (filtering, simulation, advanced tagging)
- Test suite and CI integration
- User documentation and troubleshooting guide

### Beyond v1.0 (Ideas)
- Web-based UI for plan review and approval
- Advanced duplicate analysis (optional, opt-in)
- Customizable renaming/tagging templates
- Multi-language support
- Plugin system for custom workflows

---

<p align="center">
  <img src="https://raw.githubusercontent.com/github/explore/main/topics/python/python.png" width="80"/>
</p>

<p align="center"><i>ChronoClean — Order your memories.</i></p>
