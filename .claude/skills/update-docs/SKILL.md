---
name: update-docs
description: >
  Update living documentation to match current codebase state. Two modes:
  `/update-docs` — incremental, checks git log since last run;
  `/update-docs full` — deep-reads actual code and compares with all docs.
  Use when user says "update docs", "docs are stale", "sync documentation",
  or after a batch of changes lands.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent
argument-hint: "[full]"
---

# Update Documentation

Keep living docs in sync with the codebase. Documentation lives in two places: markdown files in the repo root and module-level docstrings in `__init__.py` files.

## Managed Documentation

### Markdown files

| Doc | What it covers | Code signals |
|-----|---------------|-------------|
| `CLAUDE.md` | Dev commands, architecture overview, code style, environment | `pyproject.toml`, `Makefile`, `src/dnd_simulator/core/`, new layers, new adapters |
| `ARCHITECTURE.md` | Detailed system design, module map, data flow, principles | `core/`, `layers/`, `service.py`, `adapters/`, `llm/`, `storage/` |
| `README.md` | Project overview, quick start | Major feature additions, new dependencies |

### Module docstrings (`__init__.py`)

Every package under `src/dnd_simulator/` has a module-level docstring in its `__init__.py` that describes the package's purpose, key types, and architectural role. These are part of the living documentation and must stay in sync with the code.

| Package | Docstring scope | Code signals |
|---------|----------------|-------------|
| `core/` | Foundation types: GameDateTime, TimeDelta, Event, Query, Answer, Layer, World, Entity/Character | Any change to `core/*.py` |
| `layers/` | Layer stack overview, ordering, dependencies | New/removed layers, reordering |
| `layers/geography/` | Physical world: regions, weather, terrain, daylight | `layers/geography/*.py` |
| `layers/politics/` | Nations, diplomacy, warfare, economy | `layers/politics/*.py` |
| `layers/settlements/` | Towns, population, prosperity | `layers/settlements/*.py` |
| `layers/npcs/` | NPC schedules, activities, dialog | `layers/npcs/*.py` |
| `master/` | Dungeon Master orchestrator role | `master/*.py` |
| `rules/` | Pure game mechanics functions | `rules/*.py` |
| `adapters/` | Transport adapters (CLI, API, Telegram) | `adapters/*.py` |
| `storage/` | Save/load interface and implementations | `storage/*.py` |
| `llm/` | LLM client and prompt builders | `llm/*.py` |

When updating a docstring, match the existing style: top-level packages (`core`, `master`, `rules`, `adapters`, `storage`) use comprehensive multi-line docstrings explaining architecture; layer sub-packages use brief one-line docstrings followed by imports and `__all__`.

### Not managed by this skill

- `BACKLOG.md` — maintained manually by the user
- `content/*.yaml` — game data, not documentation
- `.claude/skills/*/SKILL.md` — managed by `/skill-creator`
- Class-level and function-level docstrings — too granular, updated inline when code changes

## Modes

### `/update-docs` — incremental

Fast default. Reads git log since last run, determines which docs are affected by file changes, updates only those.

### `/update-docs full` — deep review

Reads actual source code for all managed docs and compares with what the docs say. Use after major refactors or when docs haven't been reviewed in a while.

## State

Last-run metadata lives in `.claude/skills/update-docs/state.json`:

```json
{
  "last_run": "2026-03-20",
  "last_run_mode": "incremental",
  "last_commit": "fa402c8",
  "last_full_run": null
}
```

If `state.json` doesn't exist — this is the first run. For incremental mode, use the last 2 weeks of git history as baseline.

## Protocol

### 0. Load state

Read `state.json`. If missing, note this is the first run.

### 1. Determine scope

**Incremental:**

```bash
git log --oneline --since="<last_run>" --name-only
```

From changed files, use the "Code signals" column to determine which docs are potentially affected. Only review those.

If nothing changed — say so and exit.

**Full:**

All markdown docs and all `__init__.py` docstrings are in scope. Read the actual code areas listed in "Code signals" — not just what changed recently, but the current state.

### 2. Review & update

#### Markdown files

For each markdown doc in scope:

1. **Read the current doc**
2. **Read the relevant code** — use "Code signals" to know where to look. In incremental mode, focus on the specific files that changed. In full mode, do a broader read.
3. **Compare** — look for: outdated descriptions, missing new features/layers, removed components still mentioned, wrong file paths, stale examples, incorrect command syntax
4. **Update the doc** — edit directly. Keep existing style and structure. Don't rewrite accurate sections.

#### Module docstrings

For each `__init__.py` in scope:

1. **Read the current docstring** in the `__init__.py`
2. **Read the package's source files** — all `.py` files in that package directory
3. **Compare** — look for: new classes/functions not mentioned, removed types still listed, renamed exports, changed architectural role, new dependencies
4. **Update the docstring** — edit the module-level docstring in place. Match the existing style (comprehensive for top-level packages, brief for layer sub-packages).

#### General guidelines

- Preserve the author's voice and formatting conventions
- Don't bloat docs with implementation details — keep the same level of abstraction
- If a section is completely wrong, rewrite it; if mostly right, patch it
- When unsure if something changed, check the code rather than guessing

### 3. Save state

```json
{
  "last_run": "<today>",
  "last_run_mode": "<mode>",
  "last_commit": "<current HEAD sha>",
  "last_full_run": "<today if full mode, else keep previous>"
}
```

### 4. Commit

```bash
git add <updated docs> .claude/skills/update-docs/state.json
git commit -m "docs: update living docs (<mode> sync, <N> files)"
```

Do NOT push.

### 5. Report

```
## Docs Update Summary
- Mode: incremental | full
- Docs reviewed: N
- Docs updated: N (list them)
- Docs unchanged: N
- Notable changes: <brief bullets>
- Last full review: <date or "never">
```
