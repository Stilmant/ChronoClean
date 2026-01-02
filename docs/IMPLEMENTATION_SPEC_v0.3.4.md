# ChronoClean v0.3.4 - Tag Management & Preflight Reporting

**Version:** 0.3.4 (Tag Management & Preflight Reporting)  
**Status:** Planned  
**Last Updated:** 2026-01-02

---

## Overview

v0.3.4 makes folder-name tagging **reviewable and controllable** before you move/copy anything.

It adds:
- A persistent "tag decisions" store (use/ignore/clear + optional alias)
- CLI commands to list tag candidates and classify folder names without editing YAML
- Export outputs (JSON/CSV) that are useful for preflight review and external analysis (including AI)

This version is aimed at real-world messy sources: many folders, inconsistent naming, mixed exports, and duplicates.

---

## Current State (v0.3.3) - What's Implemented Today

### Tagging behavior (implemented)

- Folder tag detection exists (`FolderTagger.classify_folder()` + `extract_tag()`).
- `scan` reports detected tags (unique list) and per-file tag display in `--report`.
- `apply --tag-names` can append tags **even when `--rename` is off** (tag-only mode).
- Tag application avoids double-tagging via fuzzy filename checks (`folder_tag_usable`).

### Gaps relevant to tag management

- No `chronoclean tags ...` commands exist yet (only documented).
- No persistent tag decisions besides editing config `folder_tags.ignore_list/force_list`.
- Export outputs do not fully support "preflight planning":
  - `export` does not include folder tag fields
  - `export` does not compute proposed destinations (`target_path`) unless made destination-aware

---

## Goals for v0.3.4

| Goal | Priority | Description |
|------|----------|-------------|
| Tag review command | P0 | List tag candidates + counts + reasons from a scan |
| Tag decision persistence | P0 | Persist folder-name decisions (use/ignore/clear) |
| Tag classify CLI | P0 | `tags classify "<folder>" use|ignore|clear` updates decisions store |
| Rich preflight export | P1 | Export JSON/CSV including folder-tag fields + optional computed destinations |
| Tag aliasing | P1 | Allow mapping folder name -> custom tag text (shorten/normalize) |
| Multi-tag strategy (design only) | P2 | Decide filename vs sidecar vs index/DB for multiple tags |

---

## Non-Goals (v0.3.4)

- Plan-based workflow (`plan/dryrun/report` split) - stays v0.5.
- Robust apply/resume/journaling - stays v0.4.
- Full-library deduplication/merge (beyond collision-safe duplicate handling).
- Writing per-file sidecars by default.

---

## User Stories

### Story A (Developer / power user): export scan findings for external analysis (AI)

**As a developer**, I want a scan export that includes dates, tag candidates, and (optionally) proposed destinations so I can pass the file to AI/tools and decide next steps.

Acceptance:
- `chronoclean export json <source> --output scan.json` includes folder-tag fields.
- Optionally `--destination <dest>` computes proposed `target_path` like `apply --dry-run` would.
- Output is stable and machine-readable (JSON schema documented).

### Story B (User): list tag candidates and why they are/aren't used

**As a user**, I want `tags list` to show which folder names become tags, which are ignored, and why, so I can tune rules before apply.

Acceptance:
- `chronoclean tags list <source>` prints:
  - tag candidates (chosen tag, count, samples)
  - ignored folder names with reasons (`ignore_list`, `camera_generated`, `too_short`, etc.)
- Can output JSON for deeper review.

### Story C (User): override tagging without editing YAML

**As a user**, I want to classify a folder name as "use" or "ignore" and have it persist across runs.

Acceptance:
- `chronoclean tags classify "Paris 2022" use` persists the decision.
- Next `scan` / `apply --tag-names` uses that decision automatically.

### Story D (User): shorten or normalize tags without renaming folders

**As a user**, I want to map a folder name to a custom tag (alias) to avoid long/noisy filename tags.

Acceptance:
- `chronoclean tags classify "Paris 2022" use --tag "ParisTrip"` makes the applied tag `ParisTrip`.
- Mapping persists and is shown in `tags list`.

### Story E (Messy sources): duplicates from multiple sources preserve context

**As a user**, when duplicates are skipped, I still want to keep the "source context" tags somewhere.

Acceptance (P2 design; implementation may slip):
- Run record / export can capture: "this file was seen in multiple sources with tags X, Y".

---

## Proposed UX / CLI

### 1) `chronoclean tags list`

List tag classification from a scan.

Proposed usage:
- `chronoclean tags list <source>`
- `chronoclean tags list <source> --format json -o tags.json`

Options:
- `--recursive/--no-recursive`
- `--videos/--no-videos`
- `--limit N`
- `--format text|json`
- `--output PATH`
- `--samples N` (include N sample file paths per item)
- `--show-ignored/--no-show-ignored` (default: show)

Output (text):
- "Will tag": `<tag>` (count, example files)
- "Ignored": `<folder_name>` (reason, count, examples)

### 2) `chronoclean tags classify`

Persist a decision for a folder name.

Proposed usage:
- `chronoclean tags classify "<folder>" use`
- `chronoclean tags classify "<folder>" ignore`
- `chronoclean tags classify "<folder>" clear`

Optional:
- `--tag "<custom_tag>"` (only valid with `use`)

Behavior:
- `use` adds folder to forced-use list (and optionally alias map).
- `ignore` adds folder to ignore list.
- `clear` removes overrides; returns to heuristic classification.

### 3) Export improvements (preflight planning)

Enhance existing `export` to support the "report to AI" workflow.

Proposed changes:
- Always include:
  - `folder_tag`, `folder_tag_usable`, `source_folder_name`
  - `folder_tag_reason` (from classify_folder / trace)
- Add optional destination-aware mapping:
  - `chronoclean export json <source> --destination <dest> [--structure ...] [--rename/--no-rename] [--tag-names/--no-tag-names]`
  - Adds `proposed_destination_folder`, `proposed_filename`, `proposed_target_path`

Note: This is "dry-run planning output", not execution.

---

## Persistence: Tag Decisions Store

### Location

Default: `.chronoclean/tag_rules.yaml` (relative to CWD, consistent with other `.chronoclean/` state).

### File format (draft)

```yaml
version: 1
updated_at: "2026-01-02T00:00:00Z"

use:
  - "Paris 2022"

ignore:
  - "tosort"

aliases:
  "Paris 2022": "ParisTrip"
```

### Precedence (highest wins)

1. Tag rules file (`.chronoclean/tag_rules.yaml`) aliases + decisions
2. Config `folder_tags.force_list` / `folder_tags.ignore_list`
3. Heuristics (`FolderTagger.classify_folder`)
4. Formatting (`FolderTagger.format_tag`), unless alias overrides tag text

---

## Data Model / Reporting Additions (minimal)

Per-file export fields:
- `source_folder_name`
- `folder_tag`
- `folder_tag_usable`
- `folder_tag_reason` (e.g., `meaningful`, `in_ignore_list`, `camera_generated`, `too_short`)
- `folder_tag_source_folder` (which folder name produced the tag)

Aggregated outputs for `tags list`:
- `tag_candidates`: list of `{tag, count, examples[]}`
- `ignored_folders`: list of `{folder_name, reason, count, examples[]}`

---

## Multi-tag: filename vs sidecar vs index (decision guidance)

### Filename tags (today)

Pros:
- Zero extra files
- Simple mental model

Cons:
- Filename inflation with multiple tags
- Hard to preserve all "source context"

### Per-file sidecars (future option)

Pros:
- Store multiple tags per file cleanly
- Avoid filename bloat

Cons:
- Doubles file count (e.g., 300k photos -> +300k sidecars)
- Many small files can hurt NAS performance (metadata overhead, backups, traversal)
- Sidecars can be separated from media unless strictly managed

### Recommended direction (v0.3.4)

- Keep filename tags as the primary/optional UX (single tag).
- Do not generate per-file sidecars in v0.3.4.
- If multi-tag becomes necessary, prefer a central index:
  - JSONL in `.chronoclean/`, or
  - SQLite (aligns with v0.6 caching plans)

---

## Implementation Order (suggested)

1. Core: implement `TagRulesStore` (load/save/merge; apply alias + decisions)
2. CLI: add `tags` command group (`list`, `classify`)
3. Scan/export: surface reasons and folder tag fields in export output
4. Destination-aware export mapping (`--destination`) using same planning logic as `apply`
5. Docs: update README + CLI Command Map + CONFIGURATION.md to reflect new tag workflow

---

## Testing Requirements

- Unit tests for `TagRulesStore`:
  - load/save roundtrip
  - precedence rules (alias beats format, use/ignore beats heuristic)
- CLI smoke tests with Typer runner:
  - `tags classify` creates/updates `.chronoclean/tag_rules.yaml`
  - `tags list` outputs expected counts/reasons on a small fixture tree
- Export tests:
  - JSON includes new tag fields
  - With `--destination`, `proposed_target_path` is computed deterministically

---

## Success Criteria

- Users can generate a scan export that's useful for preflight review and AI analysis.
- Users can list tag candidates + ignored folder names with reasons.
- Users can persist overrides via CLI and see changes reflected immediately in scan/apply.
- No breaking changes to existing apply behavior; new features are additive.

---

*Document version: 0.1 (draft)*  
*Planned scope for ChronoClean v0.3.4*
