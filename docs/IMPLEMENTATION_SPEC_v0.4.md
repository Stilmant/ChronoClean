# ChronoClean v0.4 - Robust Apply & Resume

**Version:** 0.4 (Robust Apply & Resume)  
**Status:** Planned  
**Last Updated:** 2025-12-30

---

## Overview

v0.4 focuses on making `apply` reliable on NAS / large batches:

- Avoid partial destination files on interruption or I/O errors.
- Persist apply state on disk (plan + journal) to support resume/retry.
- Keep the default UX simple: users still run `chronoclean apply <src> <dest>`.

This version is intentionally about robustness, not new UX commands.

---

## Goals for v0.4

| Goal | Priority | Description |
|------|----------|-------------|
| Atomic copy/write | P0 | Copy via a temp file + atomic rename into place |
| Durable execution journal | P0 | Persist per-file status so Ctrl+C/crash is recoverable |
| Resume incomplete runs | P0 | Detect incomplete run and resume naturally |
| Detailed errors | P1 | Record which files failed + why (not only a summary counter) |
| RAM-bounded execution | P1 | Avoid building huge in-memory operation lists |
| Retries/backoff | P2 | Optional retry strategy for transient NAS/network errors |

---

## Key Behaviors

### 1) `apply` stays the primary UX

Default flow remains:

1. Scan
2. Plan
3. Execute

But v0.4 persists state automatically under `.chronoclean/` so `apply` can resume.

### 2) Atomic copy (no partial files)

**Problem:** If the process is interrupted (Ctrl+C, crash, connection loss) during a copy, a partial destination file may be left behind.

**Solution:** Copy to a temp file in the destination directory, then rename atomically:

- Destination temp name pattern: `<final_name>.chronoclean_tmp.<run_id>.<op_id>`
- If rename succeeds: final file exists, temp file is gone.
- If interrupted: only the temp file remains and can be cleaned/resumed.

### 3) Durable plan + journal (stream-friendly)

v0.4 introduces a persistent apply run directory:

```
.chronoclean/
  apply_runs/
    <run_id>/
      meta.json
      plan.jsonl
      journal.jsonl
```

**Why JSONL:** it supports streaming writes and incremental processing without holding everything in memory.

**Plan (`plan.jsonl`)** contains the deterministic mapping per file (source → final destination path), plus decisions (rename/tag/collision strategy outcome).

**Journal (`journal.jsonl`)** is append-only and records per-file execution events:

- `pending` / `started` / `done` / `failed`
- error details when `failed`

### 4) Resume behavior

When `apply` starts, it checks for the most recent incomplete run that matches:

- source root
- destination root
- mode (copy/move)
- config signature (values that change mapping)

If found:

- Interactive default: prompt to resume
- Non-interactive: support `chronoclean resume --last` (planned)

Resume semantics:

- `done` operations are skipped
- `failed` operations can be retried (policy: retry all, or only transient errors)
- leftover temp files are detected and handled (cleanup or overwrite)

---

## Non-Goals (v0.4)

- Introducing `plan` / `report` / `dryrun` command split (moved to v0.5).
- Parallel copy by default (kept sequential; parallelism only considered later and opt-in).

---

## Success Criteria

- Interrupting `apply` does not corrupt destinations (no partial final files).
- After restart, user can resume and finish without rescanning everything.
- The tool can report exactly which files failed and why.

---

*Document version: 0.1 (draft)*  
*Planned scope for ChronoClean v0.4*

