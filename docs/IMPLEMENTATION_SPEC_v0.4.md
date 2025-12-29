# ChronoClean v0.4 - User Experience & Safety

**Version:** 0.4 (User Experience & Safety)  
**Status:** Planned  
**Last Updated:** 2025-12-29

---

## Overview

v0.4 focuses on safer and clearer user workflows. It introduces an explicit
report/plan split, interactive review, and safety gates. It also tracks the
planned conditional rename mode for "garbage" filenames while keeping renaming
optional.

---

## Goals for v0.4

| Goal | Priority | Description |
|------|----------|-------------|
| Report/plan split | P0 | Clear separation between analysis output and executable plan |
| Apply from plan | P0 | Deterministic execution of reviewed plans |
| Interactive review | P1 | Rich-based prompts for risky actions |
| Safety gates | P1 | Disk-space checks, live-mode warnings, backup reminders |
| Conditional rename | P2 | Rename only when filenames are low-quality |

---

## Key Features

### 1) Unambiguous Command Split

**Purpose:** Make outputs explicit and avoid ambiguity.

Planned commands:
- `report ...` = analysis output (JSON/CSV)
- `plan ...` = executable plan generation (JSON)
- `apply --from-plan <plan.json>` = deterministic execution
- `dryrun --from-plan <plan.json>` = simulate plan without writing

---

### 2) Conditional Rename Mode (Planned)

**Purpose:** Keep original camera filenames while still fixing low-quality names.

**Behavior:**
- Renaming becomes an optional *additional* transformation.
- A new mode allows renaming only when a filename looks low-quality.

**Draft config:**
```yaml
renaming:
  mode: "only_if_garbage"   # planned: always, never, only_if_garbage
```

**Garbage detection heuristics (draft):**
- UUID-like names (e.g., `9A4FDBE4-4237-4789-B514-FAD6E158D937.jpg`)
- Hash-like names (hex strings, long alphanumeric runs)
- Generic export names (e.g., `image1234.jpg`, `IMG_E1234.JPG`)

When flagged as garbage, apply the configured rename pattern (date/time/tag).

---

## Success Criteria

- Report/plan split is documented and usable.
- `apply --from-plan` executes a reviewed plan deterministically.
- Conditional rename mode exists and is opt-in.
- Safety warnings are clear and prevent accidental destructive runs.

---

*Document version: 0.1 (draft)*  
*Planned scope for ChronoClean v0.4*
