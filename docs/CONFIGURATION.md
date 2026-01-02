# ChronoClean Configuration Guide

This guide explains how to configure ChronoClean using YAML configuration files.

## Quick Start

**Option 1: Using `config init` (Recommended)**

```bash
# Create a minimal config file
chronoclean config init

# Or create a full config with all options documented
chronoclean config init --full
```

**Option 2: Manual creation**

Create a `chronoclean.yaml` file in your project directory with the following minimal content:

```yaml
sorting:
  folder_structure: "YYYY/MM"
```

Then edit the file and run ChronoClean:
```bash
chronoclean scan /path/to/photos
```

## Config Commands

### `config init`

Create a new configuration file:

```bash
chronoclean config init                    # Minimal config (recommended for beginners)
chronoclean config init --full             # Full config with all options documented
chronoclean config init -o myconfig.yaml   # Custom output path
chronoclean config init --force            # Overwrite existing file
```

### `config show`

Display current effective configuration:

```bash
chronoclean config show                    # Show all settings
chronoclean config show --section sorting  # Show only sorting section
chronoclean config show -c custom.yaml     # Show specific config file
```

### `config path`

Show where ChronoClean looks for config files:

```bash
chronoclean config path
```

This displays all search paths and marks which config file is currently active.

## Config File Locations

ChronoClean searches for configuration files in this order:

1. **Explicit path** via `--config` argument
2. `chronoclean.yaml` in current directory
3. `chronoclean.yml` in current directory  
4. `.chronoclean/config.yaml`
5. `.chronoclean/config.yml`
6. **Built-in defaults** (no file needed)

The first file found is used. If no file is found, built-in defaults apply.

## CLI Overrides Config

**CLI arguments always override config file values.** This lets you:
- Set defaults in config file
- Override specific values per-command

Example:
```yaml
# chronoclean.yaml
general:
  recursive: false  # Default: don't recurse
```

```bash
# Override for this run only
chronoclean scan /photos --recursive
```

## Configuration Sections

### `general` — General Settings

```yaml
general:
  timezone: "local"           # Timezone for date operations
  recursive: true             # Scan subdirectories
  include_videos: true        # Include video files in scans
  ignore_hidden_files: true   # Skip files/folders starting with '.'
  dry_run_default: true       # Default to dry-run mode (safe)
  output_folder: ".chronoclean"
```

### `scan` — Scan Settings

```yaml
scan:
  image_extensions:
    - ".jpg"
    - ".jpeg"
    - ".png"
    - ".tiff"
    - ".heic"
    - ".webp"
    - ".bmp"
    - ".gif"
  video_extensions:
    - ".mp4"
    - ".mov"
    - ".avi"
    - ".mkv"
    - ".m4v"
    - ".webm"
  raw_extensions:
    - ".cr2"
    - ".nef"
    - ".arw"
    - ".dng"
  skip_exif_errors: true      # Continue if EXIF read fails
  limit: null                 # Limit files scanned (for debugging)
```

### `sorting` — Sorting Settings

```yaml
sorting:
  folder_structure: "YYYY/MM"   # Options: YYYY, YYYY/MM, YYYY/MM/DD
  fallback_date_priority:       # Order to try when inferring dates
    - "exif"                    # EXIF metadata (most reliable for images)
    - "video_metadata"          # Video container metadata (v0.3)
    - "filename"                # Date from filename pattern
    - "filesystem"              # File modification date
    - "folder_name"             # Date from folder name
```

**Folder structures:**
| Value | Example Output |
|-------|----------------|
| `YYYY` | `2024/photo.jpg` |
| `YYYY/MM` | `2024/03/photo.jpg` |
| `YYYY/MM/DD` | `2024/03/15/photo.jpg` |

### `folder_tags` — Folder Tag Settings

Control which folder names are used as tags in filenames.

```yaml
folder_tags:
  enabled: false              # Enable folder tag detection
  min_length: 3               # Minimum tag length
  max_length: 40              # Maximum tag length
  ignore_list:                # Folder names to never use as tags
    - "tosort"
    - "unsorted"
    - "misc"
    - "backup"
    - "temp"
    - "dcim"
    - "camera"
    - "pictures"
    - "photos"
  force_list: []              # Always use these as tags
  distance_threshold: 0.75    # Fuzzy match threshold (0-1)
```

### Tag Rules Store (v0.3.4)

In addition to config file settings, folder tag decisions can be persisted 
using the `tags classify` command. These decisions are stored in 
`.chronoclean/tag_rules.yaml` and take precedence over config settings.

**File location:** `.chronoclean/tag_rules.yaml`

**File format:**
```yaml
use:
  - "Paris 2024"
  - "Wedding Photos"
ignore:
  - "tosort"
  - "temp"
  - "misc"
aliases:
  "Paris 2024": "ParisTrip"
  "Wedding Photos": "Wedding"
```

**Precedence (highest to lowest):**
1. Tag rules store (`tag_rules.yaml`) — explicit user decisions
2. Config force_list — always use as tags
3. Config ignore_list — never use as tags
4. Heuristic detection — automatic classification

**Managing tag rules:**
```bash
# List current tag classifications
chronoclean tags list /photos

# Mark folder as usable tag
chronoclean tags classify "Paris 2024" use

# Mark with alias
chronoclean tags classify "Paris 2024" use --tag "ParisTrip"

# Mark as ignored
chronoclean tags classify "temp" ignore

# Clear a decision
chronoclean tags classify "Paris 2024" clear
```

### `renaming` — File Renaming Settings

```yaml
renaming:
  enabled: false              # Enable file renaming
  pattern: "{date}_{time}"    # Rename pattern
  date_format: "%Y%m%d"       # strftime format for date
  time_format: "%H%M%S"       # strftime format for time
  tag_part_format: "_{tag}"   # Format when adding tag
  lowercase_extensions: true  # Convert .JPG to .jpg
```

**Pattern placeholders:**
| Placeholder | Description | Example |
|-------------|-------------|---------|
| `{date}` | Formatted date | `20240315` |
| `{time}` | Formatted time | `143000` |
| `{tag}` | Folder tag | `Paris` |
| `{original}` | Original filename | `IMG_1234` |

**Example results:**
| Pattern | Result |
|---------|--------|
| `{date}_{time}` | `20240315_143000.jpg` |
| `{date}_{time}_{tag}` | `20240315_143000_Paris.jpg` |
| `{original}_{date}` | `IMG_1234_20240315.jpg` |

### `duplicates` — Duplicate Handling

```yaml
duplicates:
  enabled: true               # Enable duplicate detection
  policy: "safe"              # Planned: safe, skip, overwrite
  hashing_algorithm: "sha256" # sha256, md5
  on_collision: "check_hash"  # check_hash, rename, skip, fail
```

**Collision strategies (`on_collision`):**
| Strategy | Behavior |
|----------|----------|
| `check_hash` | Compare file hashes; skip if identical, rename if different |
| `rename` | Always rename colliding files (add counter suffix) |
| `skip` | Skip all files that would collide |
| `fail` | Stop with error on first collision |

> **Note:** `policy` is reserved for future use (planned).

### `filename_date` — Filename Date Parsing (v0.2)

Extract dates embedded in filenames like `IMG_20240315_143000.jpg`.

```yaml
filename_date:
  enabled: true               # Enable filename date extraction
  patterns: []                # Planned: custom regex patterns (uses built-in patterns)
  year_cutoff: 30             # 2-digit year: 00-30 = 2000s, 31-99 = 1900s
  priority: "after_exif"      # When to try filename in date inference
```

**Priority options:**
| Value | Behavior |
|-------|----------|
| `before_exif` | Try filename first (before EXIF) |
| `after_exif` | Try filename after EXIF but before filesystem |
| `after_filesystem` | Try filename after filesystem date |

> **Note:** `patterns` is reserved for future use. Currently uses built-in regex patterns
> that match common formats like `YYYYMMDD_HHMMSS`, `YYYYMMDD`, `IMG_YYMMDD`, etc.

### `date_mismatch` — Date Mismatch Detection (v0.2)

Detect when a file's filename date doesn't match its EXIF/filesystem date.

```yaml
date_mismatch:
  enabled: true               # Enable mismatch detection
  threshold_days: 1           # Days difference to flag as mismatch
  warn_on_scan: true          # Planned: show warnings during scan
  include_in_export: true     # Planned: conditionally include in export
```

Mismatches are flagged in scan results and exports, helping identify
renamed files or files with incorrect EXIF data.

> **Note:** `warn_on_scan` and `include_in_export` are reserved for future use.

### `video_metadata` — Video Metadata Settings (v0.3)

Extract creation dates from video container metadata (MP4, MOV, MKV, etc.).

```yaml
video_metadata:
  enabled: true               # Enable video metadata extraction
  provider: "ffprobe"         # ffprobe (preferred) or hachoir
  ffprobe_path: "ffprobe"     # Path to ffprobe binary
  fallback_to_hachoir: true   # Use hachoir if ffprobe unavailable
  skip_errors: true           # Continue on metadata read failures
```

**Provider comparison:**
| Provider | Pros | Cons |
|----------|------|------|
| `ffprobe` | Fast, handles most formats | Requires FFmpeg installation |
| `hachoir` | Pure Python, no external deps | Slower, fewer formats |

**Installing ffprobe:**
- **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use `winget install ffmpeg`
- **macOS:** `brew install ffmpeg`
- **Linux:** `apt install ffmpeg` or `dnf install ffmpeg`

When `provider: "ffprobe"` and ffprobe is unavailable:
- If `fallback_to_hachoir: true` and hachoir is installed, uses hachoir
- Otherwise, video metadata is skipped (with warning if `skip_errors: false`)

### `export` — Export Settings (v0.2)

```yaml
export:
  default_format: "json"      # json, csv
  include_statistics: true    # Include summary stats in export
  include_folder_tags: true   # Include folder tag fields (v0.3.4)
  pretty_print: true          # Format JSON with indentation
  output_path: ".chronoclean/export"  # Default output directory
```

**Folder tag fields in export (v0.3.4):**

When folder tags are enabled, the following fields are included in exports:

| Field | Description |
|-------|-------------|
| `source_folder_name` | Original parent folder name |
| `folder_tags` | Array of assigned tags (future: multi-tag support) |
| `folder_tag_reasons` | Why each tag was assigned |
| `folder_tag` | Primary tag (backward compatible) |
| `folder_tag_reason` | Primary tag reason |
| `folder_tag_usable` | Whether primary tag is usable |

**Destination preview in export (v0.3.4):**

Use `--destination` flag to compute and include proposed file destinations:

```bash
chronoclean export json --destination /photos/organized
```

This adds the following fields:

| Field | Description |
|-------|-------------|
| `proposed_destination_folder` | Target folder path |
| `proposed_filename` | Target filename |
| `proposed_target_path` | Full target path |

Use `--sample N` to limit export to N files for preview.

### `verify` — Verification & Cleanup Settings (v0.3.1)

Control verification of applied changes and safe source cleanup.

```yaml
verify:
  enabled: false                        # Master switch (default off)
  algorithm: "sha256"                   # sha256 (recommended) or quick
  state_dir: ".chronoclean"             # Where to store run records
  run_record_dir: "runs"                # Subdirectory for run records
  verification_dir: "verifications"     # Subdirectory for verification reports
  allow_cleanup_on_quick: false         # Allow cleanup with quick verification
  content_search_on_reconstruct: false  # Search by content if expected path missing
  write_run_record: true                # Write run record on apply
```

**Algorithm options:**
| Algorithm | Speed | Safety for Cleanup |
|-----------|-------|-------------------|
| `sha256` | Slower (reads full file) | Safe - cryptographic verification |
| `quick` | Fast (size comparison only) | Not safe - cannot guarantee content match |

**Key settings:**

- **`algorithm`**: Use `sha256` for reliable verification. Use `quick` only for 
  quick sanity checks when you don't plan to delete source files.
  
- **`allow_cleanup_on_quick`**: By default, `cleanup` command refuses to delete
  files verified with `quick` mode since size-only verification isn't reliable.
  Set to `true` only if you accept the risk.

- **`content_search_on_reconstruct`**: When verifying without a run record 
  (reconstructed mapping), enable this to search the destination tree for files
  matching source content. Useful when file was renamed during apply.

- **`write_run_record`**: Automatically writes a run record after each `apply`.
  Disable with `--no-run-record` CLI flag if not needed.

**Typical workflow:**
```bash
# 1. Apply changes (automatically writes run record)
chronoclean apply --no-dry-run

# 2. Verify the copy succeeded
chronoclean verify

# 3. After verification, safely delete verified sources
chronoclean cleanup --no-dry-run
```

> **Note:** Run records and verification reports are stored in `.chronoclean/runs/` 
> and `.chronoclean/verifications/` respectively.

### `logging` — Logging Settings

```yaml
logging:
  level: "info"               # debug, info, warning, error
  color_output: true          # Colored terminal output
  log_to_file: true           # Write to log file
  file_path: ".chronoclean/chronoclean.log"
```

### `performance` — Performance Settings

```yaml
performance:
  multiprocessing: true       # Use multiple CPU cores
  max_workers: 0              # 0 = auto-detect
  chunk_size: 500             # Files per batch
  enable_cache: true          # Cache EXIF data
  cache_location: ".chronoclean/cache.db"
```

### `synology` — Synology NAS Settings

```yaml
synology:
  safe_fs_mode: true          # Extra filesystem safety
  use_long_paths: false       # Windows long path support
  min_free_space_mb: 500      # Minimum free space required
```

## Example Configurations

### Minimal Config (sorting only)

```yaml
sorting:
  folder_structure: "YYYY/MM"
```

### Enable Renaming

```yaml
renaming:
  enabled: true
  pattern: "{date}_{time}"
```

### Enable Folder Tags

```yaml
folder_tags:
  enabled: true
  ignore_list:
    - "temp"
    - "misc"
    - "inbox"
```

### Custom Date Priority

```yaml
sorting:
  fallback_date_priority:
    - "exif"
    - "folder_name"    # Try folder name before filesystem
    - "filesystem"
```

### Synology NAS Config

```yaml
general:
  dry_run_default: true       # Always safe by default

sorting:
  folder_structure: "YYYY/MM/DD"

folder_tags:
  enabled: true
  ignore_list:
    - "@eaDir"                # Synology thumbnail folder
    - "#recycle"              # Synology recycle bin
    - "tosort"
    - "inbox"

synology:
  safe_fs_mode: true
  min_free_space_mb: 1000     # 1GB minimum
```

## Validating Config

ChronoClean validates your config on load. Common errors:

| Error | Cause |
|-------|-------|
| `Invalid folder_structure` | Use `YYYY`, `YYYY/MM`, or `YYYY/MM/DD` |
| `Invalid fallback source` | Use `exif`, `video_metadata`, `filename`, `filesystem`, `folder_name` |
| `Invalid log level` | Use `debug`, `info`, `warning`, `error` |
| `threshold out of range` | Must be 0.0 to 1.0 |

## Sample Config Files

Use the `config init` command to generate sample configuration files:

- `chronoclean config init` — Minimal config showing only essentials
- `chronoclean config init --full` — Full config with all options documented
