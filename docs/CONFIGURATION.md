# ChronoClean Configuration Guide

This guide explains how to configure ChronoClean using YAML configuration files.

## Quick Start

1. Copy one of the sample configs to your project root:
   ```bash
   cp configs/chronoclean.minimal.yaml chronoclean.yaml
   ```

2. Edit the file to match your needs

3. Run ChronoClean - it will automatically find the config:
   ```bash
   chronoclean scan /path/to/photos
   ```

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
    - "exif"                    # EXIF metadata (most reliable)
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
  policy: "safe"              # safe, skip, overwrite
  hashing_algorithm: "sha256" # sha256, md5
```

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
| `Invalid fallback source` | Use `exif`, `filesystem`, `folder_name` |
| `Invalid log level` | Use `debug`, `info`, `warning`, `error` |
| `threshold out of range` | Must be 0.0 to 1.0 |

## Sample Config Files

See the `configs/` folder for examples:

- `chronoclean.default.yaml` — Full config with all options documented
- `chronoclean.minimal.yaml` — Minimal config showing only essentials
