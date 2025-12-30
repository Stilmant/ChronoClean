# ChronoClean v0.6 - NAS & Large-Scale Support

**Version:** 0.6 (NAS & Large-Scale Support)  
**Status:** Planned  
**Last Updated:** 2025-12-29

---

## Overview

v0.6 focuses on large libraries and NAS environments. It delivers performance
optimizations (parallel scanning, memory-efficient iteration), metadata caching,
and headless/task-scheduler friendly workflows suitable for Synology DSM.

---

## Goals for v0.6

| Goal | Priority | Description |
|------|----------|-------------|
| Performance knobs | P0 | Implement parallel scan/inference and streaming iteration |
| Metadata caching | P0 | SQLite cache for EXIF/metadata/hash results |
| NAS workflows | P1 | Headless mode, Task Scheduler notes, safe defaults |
| Large-batch stability | P1 | Bounded memory usage for plans and collisions |

---

## Key Features

### 1) Performance Knobs (Implemented Config)

**Purpose:** Make existing config options functional.

**Targets:**
- `performance.multiprocessing`
- `performance.max_workers`
- `performance.chunk_size`

**Behavior:**
- Parallelize scanning and metadata extraction where safe.
- Keep deterministic output ordering.

---

### 2) Metadata and Hash Caching (SQLite)

**Purpose:** Avoid recomputing expensive metadata and hashes on re-runs.

**Cache inputs:**
- EXIF / video metadata timestamps
- Hash values (SHA256/MD5)

**Invalidation:**
- Use file size + mtime checks to invalidate stale cache entries.

---

### 3) NAS / Headless Workflows

**Purpose:** Ensure predictable runs on Synology and other NAS devices.

**Deliverables:**
- DSM Task Scheduler examples
- Headless-friendly logging and exit codes
- Safe defaults for large batch runs

---

### 4) Large-Batch Collision Handling

**Purpose:** Scale duplicate/collision logic to 100k+ files.

**Approach:**
- Streaming plan generation (avoid full in-memory lists when possible)
- Bounded caches and configurable limits

---

## Success Criteria

- Large scans complete within expected time/memory bounds.
- Cache improves re-run performance without incorrect results.
- NAS guides cover installation + scheduling end-to-end.

---

*Document version: 0.1 (draft)*  
*Planned scope for ChronoClean v0.6*
