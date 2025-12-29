# ChronoClean v0.3.1 - Post-Copy Verification & Safe Source Cleanup

**Version:** 0.3.1 (Verification & Safe Cleanup)  
**Status:** Draft / Planned  
**Last Updated:** 2025-12-29

---

## Overview

v0.3 delivers a usable prototype for scanning and applying chronological organization. To make the tool safe for real-world archival workflows, v0.3.1 introduces an **explicit post-copy verification step** (hash-based) and an **optional, guarded cleanup step** that can delete source files **only when verification proves the destination copy is correct**.

Key principles:
- Verification is **opt-in** and can take as long as needed.
- Cleanup is **never automatic** and must be explicitly requested.
- Partial cleanup is supported (e.g., “70% verified OK” → delete only those).
- If a source file cannot be verified as present in the destination (by hash), it is **not eligible** for deletion.

---

## Goals for v0.3.1

| Goal | Priority | Description |
|------|----------|-------------|
| Capture deterministic mapping | P0 | Persist the real `source_path -> dest_path` mapping produced by `apply` so verification is reproducible |
| Verify copy integrity | P0 | Compute and compare hashes between source and destination (default: SHA-256) |
| Safe source cleanup | P0 | Delete only sources that are verified OK; never delete unmapped/mismatched files |
| Support "forgot the report" recovery | P1 | Allow reconstructing mapping after-the-fact from rules (conservative) |
| Make verification workflow discoverable | P1 | Document ideal workflows in README and docs |

Non-goals:
- Full-library deduplication
- “Smart” matching across renamed/moved destinations without a deterministic mapping
- Verifying moves (same disk) as “copy integrity”; cleanup is meaningful for copy workflows

---

## User Stories

1) **Safe archival (recommended)**
- As a user, I copy files to my archive destination.
- I run verification using SHA-256.
- I delete only sources that are verified OK.

2) **Partial recovery**
- As a user, verification shows only 70% OK (some files missing/mismatched).
- I still want to delete the verified OK subset and handle the rest manually.

3) **Forgot to export/run report**
- As a user, I ran `apply` but did not keep any report.
- I reconstruct the mapping by reapplying the same rules (structure/rename/tagging) in a conservative way.
- I verify and then optionally cleanup only verified OK entries.

---

## Terminology

- **Apply Run Record**: A structured record produced by `apply` describing what was planned/executed, including the final `source_path -> dest_path` mapping.
- **Verification Report**: The output of verification containing per-file results and aggregated counts; used as the input to cleanup.
- **Manifest (advanced)**: A standalone mapping file. It may exist for debugging/power-users, but the default UX should not require users to pass manifest paths around.

---

## UX & CLI Design (Proposed)

### Core UX Principle: no required file parameters

By default, users should not need to pass file paths like `--from-run`, `--from-manifest`, or `--from-verify`.
Instead, the CLI should:
- auto-discover the best matching prior run/report from `.chronoclean/`
- show what it found (timestamp, source, destination, counts)
- ask for confirmation when ambiguous
- fall back to requiring an explicit file path only when nothing matches

Non-interactive modes must exist (`--yes`, `--last`, `--run-id`, etc.).

### Core Storage Principle: `.chronoclean/` is a persistent local history (CWD)

All v0.3.1 artifacts are stored under the **current working directory**:

- `.chronoclean/runs/` stores apply run records (including dry-run)
- `.chronoclean/verifications/` stores verification reports
- `.chronoclean/` becomes a durable history of scans/applies/verifications
- it can evolve into a “lightweight database” over time (future versions)

This supports a workflow where the user always runs ChronoClean from the same “project folder” and accumulates a complete operational history across many runs and many source/destination pairs.

### A) `apply` writes an Apply Run Record (recommended default)

`apply` writes a run record by default (unless explicitly disabled):
- Default output: `.chronoclean/runs/YYYYMMDD_HHMMSS_apply.json`
- Opt-out: `apply --no-run-record`

This provides the best, least ambiguous mapping for later verification.

**Dry-run behavior:** dry-runs also write a run record (`mode: dry_run`). The file naming should make this obvious (e.g., `..._apply_dryrun.json`, or by relying on the `mode` field). The default `verify` UX should propose **live copy** runs first.

### B) `verify` auto-discovers what to verify

Primary use (no explicit inputs):

```bash
chronoclean verify
```

Expected prompt behavior:
- If exactly one eligible recent apply run is found:  
  “Last apply run: 3 minutes ago, 91 files copied from X to Y. Use it? (Y/n)”
- If multiple runs match: show a short numbered list and ask to select.
- If no runs are found: instruct the user to pass `--run-file` or use reconstruction mode.

Filtering rules (used for auto-selection and narrowing choices):
- `--source <PATH>` and `--destination <PATH>` filter candidate runs by `source_root`/`destination_root`
- When available, also filter by a config signature (structure/rename/tag/collision settings) stored in the run record

Explicit overrides (advanced, for scripting):
- `verify --last` (no prompt; use most recent matching run)
- `verify --run-id <ID>` (select exact run)
- `verify --run-file <PATH>` (direct path to a run record)
- `verify --yes` (auto-accept the best match; fail if ambiguous)

Recovery mode (no run record available):

```bash
chronoclean verify --source <SOURCE> --destination <DESTINATION> --reconstruct
```

In reconstruction mode, `verify` rebuilds the mapping using the same rules as `apply` (structure/rename/tagging/collision strategy), with these safety constraints:
- If no matching destination content is found: status `missing_destination` (not deletable).
- If the source file is missing: status `missing_source` (not deletable).

Important decision: if the destination already contains the same content (historical duplicates), this is not considered “ambiguous”.
If the source hash matches any destination file hash, the source is eligible for cleanup.

Recommended reconstruction strategy (safe, deterministic):
1. Compute the expected destination path for the source (same rules as apply).
2. If the expected destination file exists: hash-compare source vs that destination.
3. If the expected destination file does not exist, optionally search for a destination match by content (gated by `verify.content_search_on_reconstruct`):
   - restrict candidates by extension and size (fast prefilter)
   - hash-compare candidates until a match is found
4. If any destination file matches by hash: mark the entry OK.

### C) Verification modes

Default verification mode:
- `sha256` (default): compute full SHA-256 on both source and destination.

Optional fast mode (not eligible for cleanup by default):
- `quick`: compare size + timestamps only.

The output is a single **Verification Report** file. Default output should be auto-named under `.chronoclean/verifications/` (and printed to the user).

### D) `cleanup` auto-discovers the latest Verification Report

Primary use (no explicit inputs):

```bash
chronoclean cleanup
```

Expected prompt behavior:
- If exactly one eligible recent verification report is found:  
  “Last verification: 2 minutes ago, 91 OK / 12 missing. Use it? (Y/n)”
- If multiple match: show a list filtered by `--source/--destination` if provided.
- If none found: instruct the user to pass `--verify-file` (or run `verify` first).

Typical usage:

```bash
chronoclean cleanup --only ok --dry-run
chronoclean cleanup --only ok --no-dry-run
```

Cleanup safety rules:
- Delete only entries where `status` is `ok` or `ok_existing_duplicate`, destination exists, and verification mode is eligible (default: sha256).
- Never delete entries with status:
  - `missing_destination`, `mismatch`, `missing_source`, `error`, `skipped`
- Support partial deletion (only verified OK subset).
- Default `--dry-run`; require `--no-dry-run` + confirmation (and optionally `--force`).

Explicit overrides (advanced, for scripting):
- `cleanup --last` (no prompt; use most recent matching verification report)
- `cleanup --verify-id <ID>` / `cleanup --verify-file <PATH>`
- `cleanup --yes` (auto-accept the best match; fail if ambiguous)

---

## Data Model (Proposed)

### Apply Run Record schema (JSON)

Per-entry:
- `source_path` (string, absolute or workspace-relative)
- `destination_path` (string, nullable; should exist for planned/executed copy operations)
- `operation` (enum: `copy`, `move`, `skip`)
- `reason` (string, optional; for skipped entries)

Top-level:
- `created_at`
- `run_id` (string)
- `source_root`
- `destination_root`
- `mode` (enum: `dry_run`, `live_copy`, `live_move`)
- `config_signature` (string or object; subset of config values affecting mapping)
- `entries[]`

### Verification Report schema (JSON)

Per-entry:
- `status` (enum: `ok`, `ok_existing_duplicate`, `mismatch`, `missing_destination`, `missing_source`, `error`, `skipped`)
- `hash_algorithm` (e.g., `sha256`, `none` for quick)
- `source_hash` (nullable)
- `destination_hash` (nullable)
- `match_type` (enum: `expected_path`, `content_search`, `unknown`), optional but recommended
- `destination_path` (string, nullable; actual verified destination path if known)
- `error` (nullable)

Top-level:
- `created_at`
- `verify_id` (string)
- `source_root`
- `destination_root`
- `input_source` (enum: `run_record`, `reconstructed`)
- `run_id` (nullable; when `input_source` is `run_record`)
- `summary` counts per status
- `duration_seconds`

### Manifest (advanced)

A separate manifest file may exist for debugging/power-users, but is not required for the default UX. If implemented, it should share the same entry shape as the apply run record mapping.

---

## Configuration (Proposed)

New optional section to provide defaults (CLI still overrides):

```yaml
verify:
  enabled: false              # default off; user opts in when needed
  algorithm: "sha256"         # sha256 | quick
  state_dir: ".chronoclean"   # stored in current working directory by default
  run_record_dir: "runs"      # resolved under state_dir
  verification_dir: "verifications"  # resolved under state_dir
  allow_cleanup_on_quick: false
  content_search_on_reconstruct: false   # planned: search destination tree by content if expected path missing
```

---

## Implementation Notes

- Hashing should be streamed (avoid loading files into memory).
- All run records and verification reports should be written under `verify.state_dir` (default: `./.chronoclean` in the current working directory).
- Verification should be resumable in a future version (out of scope for v0.3.1).
- When `apply` is run in copy mode, the Apply Run Record should record the final destination path after collision handling.
- Cleanup should be conservative:
  - if any doubt about mapping or verification, do not delete.
  - provide a clear summary and require explicit confirmation.
- Auto-discovery should be safe by default:
  - filter by source/destination when provided
  - otherwise propose "last run/report" with an explicit prompt
  - provide `--last/--yes` for non-interactive usage

---

## Success Criteria

- A user can run: `apply` (copy) → `verify` (sha256) → `cleanup --only ok` safely without passing any file paths.
- If the user forgot to generate a report, `verify --reconstruct` can reconstruct a conservative mapping.
- Cleanup never deletes a file without a verified destination match.
- Documentation clearly shows:
  - minimal quick workflow
  - safe verified workflow
  - recovery workflow

---

*Document version: 0.1 (draft)*  
*Planned scope for ChronoClean v0.3.1*
