**ChronoClean - CLI Command Map**
=================================

Note: As of v0.2, the implemented commands are `scan`, `export`, `apply`, `config`, and `version`.
`dryrun`, `tags`, `report`, and `hash` are planned for later phases per the roadmap and are documented here
as forward-looking commands.

ChronoClean follows a 4-phase workflow:

1. **scan** — analyze the library
2. **export** — generate a detailed plan (JSON/CSV) 
3. **dryrun** — simulate changes
4. **apply** — perform the real operations

Each phase has subcommands and options to keep everything clean and explicit.

**Top-Level Command Structure**
===============================

Usage:

`chronoclean [options]`

Available commands:

- `scan` — Analyze files, read EXIF, infer dates, detect meaningful folders
- `export` — Generate an export plan for review (JSON/CSV)
- `dryrun` — Simulate operations without touching disk
- `apply` — Perform actual file moves and renames
- `tags` — Manage/inspect folder-tag rules
- `report` — Show summary reports after scan or apply
- `config` — Show or edit configuration settings
- `hash` — Compute hashes for debugging or tests
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

2. **export**
---------

Export a full plan that can be reviewed or edited by the user.

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
Folder tags are detected during scan/apply, but the export output does not currently include folder tag fields (planned).

Output example:

`.chronoclean/plan.json`, `.chronoclean/plan.csv`

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

- `--from-plan PATH` — Use a specific plan file
- `--preserve-names` — Do not rename files, only move
- `--conflict-strategy` — Strategy for handling conflicts (use config for now)

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

12. **version**
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
