# ChronoClean – Architecture Contract

This project is largely AI-assisted.  
The following rules exist to prevent structural drift, accidental complexity,
and silent duplication.

They must be respected by humans and AI alike.

---

## 1. General principles

- One responsibility per file.
- One business rule = one implementation.
- No copy-paste across core modules.
- Prefer simple, explicit code over generic abstractions.

---

## 2. Constants and configuration

- `utils/constants.py` contains **values only**.
- No functions, no conditionals, no logic in `constants.py`.
- If behavior is required, it belongs to a core or utils module.

---

## 3. Utilities

- Utilities must solve a **real duplication** (used in at least 2 places).
- No speculative helpers.
- No “utils dumping ground”.

Examples of valid utilities:
- JSON serialization helpers
- Path manipulation helpers
- Dependency detection helpers

---

## 4. Duplication policy

- Intra-file duplication must be refactored immediately.
- Inter-module duplication is forbidden.
- `jscpd` is the source of truth for duplication detection.

---

## 5. Function complexity

- Functions should stay under ~40 lines.
- High branching or many locals must be justified.
- Refactor locally before introducing new abstractions.

---

## 6. CLI-specific rules

- CLI code is orchestration code.
- Higher complexity is acceptable in `chronoclean/cli/**`.
- Business logic must never live in CLI modules.

---

## 7. Tooling as contract

The following tools define the structural baseline of the project:

- `jscpd` → duplication guardrail
- `pylint` → structural warnings
- `radon` → complexity visibility

Warnings are signals, not dogma.
