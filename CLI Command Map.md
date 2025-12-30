**ChronoClean - CLI Command Map**
=================================

Note: As of v0.3.2, the implemented commands are `scan`, `export`, `apply`, `verify`, `cleanup`, `config`, `doctor`, and `version`.
`dryrun`, `tags`, `report`, and `hash` are planned for later phases per the roadmap and are documented here
as forward-looking commands.

ChronoClean supports a quick workflow today, plus an optional plan-based workflow (planned v0.5).

1) **Quick workflow (today)**
1. **scan** - analyze the library
2. **export** - export a scan report (JSON/CSV)
3. **apply** - perform the real operations (defaults to dry-run)
4. **verify** - verify copy integrity (v0.3.1)
5. **cleanup** - delete verified source files (v0.3.1)

2) **Plan-based workflow (planned v0.5)**
1. **report** - analysis outputs (JSON/CSV)
2. **plan** - generate an executable plan (JSON)
3. **dryrun** - simulate changes from plan
4. **apply** - execute from plan

Each phase has subcommands and options to keep everything clean and explicit.

**Top-Level Command Structure**
===============================

Usage:

`chronoclean [options]`

Available commands:

- `scan` - Analyze files, read EXIF, infer dates, detect meaningful folders
- `export` - Export a scan report for review (JSON/CSV) (v0.2)
- `dryrun` - Simulate operations without touching disk
- `plan` - Generate an executable plan file (JSON) (planned v0.5)
- `apply` - Perform actual file moves and renames
- `verify` - Verify copy integrity using hash comparison (v0.3.1)
- `cleanup` - Delete verified source files (v0.3.1)
- `tags` - Manage/inspect folder-tag rules
- `report` - Show summary reports after scan or apply
- `config` - Show or edit configuration settings
- `doctor` - Check system dependencies and configuration (v0.3.1)
- `hash` - Compute hashes for debugging or tests
- `version` — Show tool version

**Command Details**
===================

1. **scan**
-------

Analyze the source folder.

Usage:

`chronoclean scan [options]`

Options:

- `--recursive / --no-recursive` — Scan subfolders (default: recursive)
- `--videos / --no-videos` — Include video files
- `--limit N` — Scan only first N files (debugging)
- `--config PATH` — Specify config file path

Note: EXIF error handling and date inference are controlled via config file
(`scan.skip_exif_errors`, `filename_date.enabled`).

Output:

- In-memory model
- `.chronoclean/scan.json` (optional persistent state)

2. **export** (v0.2)
---------

Export scan results for review (report output).

Usage:

`chronoclean export [json|csv]`

Options:

- `--output PATH` / `-o PATH` — Where to save the plan (default: stdout)
- `--statistics / --no-statistics` — Include summary statistics (JSON only)
- `--pretty / --no-pretty` — Pretty-print JSON output (JSON only)
- `--recursive / --no-recursive` — Scan subfolders
- `--videos / --no-videos` — Include video files
- `--limit N` — Limit files (debugging)
- `--config PATH` — Specify config file path

Note: Duplicate detection occurs during `apply`, not during export.
Folder tags are detected during scan/apply.

Output example:

`results.json`, `results.csv`

Planned v0.5: introduce an unambiguous split:
- `report ...` = analysis outputs (replaces `export` for scan reporting)
- `plan ...` = executable plan generation (what will be done)

3. **dryrun** (Planned)
---------

Simulate the entire operation.

Usage:

`chronoclean dryrun`

Planned Options:

- `--from-plan PATH` — Use a specific plan file
- `--summary` — Print only summary (no full logs)
- `--show-renames` — Display proposed renames
- `--show-moves` — Display proposed moves
- `--show-tags` — Display inferred or applied folder tags
- `--color / --no-color` — Output formatting

*Note: Currently, use `apply --dry-run` for simulation.*

4. **apply**
--------

Perform the real operations: moving, renaming, resolving conflicts.

Usage:

`chronoclean apply <source> <destination>`

Implemented Options:

- `--dry-run / --no-dry-run` — Simulate without changes (default: dry-run)
- `--move` — Move files instead of copy (default: copy)
- `--rename / --no-rename` — Enable file renaming
- `--tag-names / --no-tag-names` — Add folder tags to filenames
- `--recursive / --no-recursive` — Scan subfolders
- `--videos / --no-videos` — Include video files
- `--structure` — Folder structure (YYYY/MM, YYYY/MM/DD, etc.)
- `--force` — Skip confirmation
- `--limit N` — Limit files (debugging)
- `--config PATH` — Config file path

Planned Options:

- `--from-plan PATH` - Use a specific plan file
- `--preserve-names` - Do not rename files, only move
- `--conflict-strategy` - Strategy for handling conflicts (use config for now)

5. **plan** (Planned v0.5)
--------

Generate an executable plan file (JSON) for review and deterministic execution.

Usage:

`chronoclean plan build <source> <destination> -o plan.json [options]`

Planned options:
- `--rename / --no-rename`
- `--tag-names / --no-tag-names`
- `--structure`
- `--recursive / --no-recursive`
- `--videos / --no-videos`
- `--limit`
- `--config`

Safeguards:

- Confirmation prompt unless `--force`
- Keeps backups in `.chronoclean/backups/` (if enabled)
- Duplicate handling occurs during apply based on `duplicates.on_collision` config

Folder Tag Management Commands
=============================

5. **tags list**
------------

List folder-tag classification.

Usage:

`chronoclean tags list`

Shows:

- Meaningful folders
- Junk folders
- Unclassified folders
- Ignored folders

6. **tags classify**
-----------------

Manual classification.

Usage:

`chronoclean tags classify "<folder>" <action>`

Examples:

`chronoclean tags classify "Paris 2022" use`

`chronoclean tags classify "tosort" ignore`

7. **tags auto**
------------

Automatically classify using heuristics.

Usage:

`chronoclean tags auto`

Heuristics include:

- String patterns (`misc`, `temp`, `backup`, `DCIM`)
- Semantic similarity (`wedding`, `vacation`, `birthday`)
- Filename similarity checks

Reporting Commands
==================

8. **report scan**
--------------

Summary of the last scan.

Usage:

`chronoclean report scan`

9. **report apply**
---------------

Summary after processing:

- Moved files
- Renamed files
- Conflicts
- Duplicates

Usage:

`chronoclean report apply`

Utility Commands
================

10. **hash**
--------

Compute a hash of a file.

Usage:

`chronoclean hash <file>`

11. **config**
----------

Configuration management commands.

### config init

Initialize a new configuration file.

Usage:

`chronoclean config init`
`chronoclean config init --full`

Options:

- `--output PATH` / `-o PATH` — Output file path (default: chronoclean.yaml)
- `--full` — Generate complete config with all options documented
- `--force` / `-f` — Overwrite existing config file

### config show

Display current configuration.

Usage:

`chronoclean config show`
`chronoclean config show --section sorting`

Options:

- `--config PATH` / `-c PATH` — Specify config file path
- `--section NAME` / `-s NAME` — Show only specific section

### config path

Show where ChronoClean looks for config files.

Usage:

`chronoclean config path`

Shows search paths and marks the active config file.

12. **doctor** (v0.3.1)
-----------

Check system dependencies and configuration.

Usage:

`chronoclean doctor`
`chronoclean doctor --fix`

Options:

- `--config PATH` / `-c PATH` — Specify config file path
- `--fix` — Interactively fix issues found

Checks:

- **External dependencies:** ffprobe, hachoir, exiftool
- **Python packages:** exifread, rich, typer, pyyaml
- **Configuration:** active config file, video metadata settings

If ffprobe is not found at the configured path but found elsewhere (e.g., `/opt/bin/ffprobe` on Synology),
the `--fix` option will offer to update the configuration file.

Example output:

```
ChronoClean Doctor
Checking system dependencies...

┏━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Component ┃ Status    ┃ Path / Version     ┃ Affects               ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ ffprobe   │ ✓ found   │ /opt/bin/ffprobe   │ video dates           │
│ hachoir   │ ✓ installed │ version 3.2.0    │ video dates (fallback)│
│ exiftool  │ ○ not installed │ optional     │ advanced EXIF         │
└───────────┴───────────┴────────────────────┴───────────────────────┘

✓ All dependencies OK!
```

13. **version**
-----------

Show ChronoClean version.

Usage:

`chronoclean version`

Suggested CLI Behavior Summary
=============================

- Scan images: `chronoclean scan /path/to/photos`
- Export plan: `chronoclean export json`
- Simulate: `chronoclean dryrun`
- Apply: `chronoclean apply --rename --tag-names`
- Show scan report: `chronoclean report scan`
- Classify folder name: `chronoclean tags classify "ParisTrip" use`
- Ignore junk folder: `chronoclean tags classify "tosort" ignore`
