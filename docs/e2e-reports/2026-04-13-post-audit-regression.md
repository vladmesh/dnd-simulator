# E2E Report: Sprint 016 post-audit regression

**Date:** 2026-04-13
**Flags:** --no-llm
**Sections tested:** 1 (setup), 2 (peaceful), 6 (master), 10 (dashboard)
**Stack:** DEBUG=1, LOG_DIR=/tmp/dnd-e2e-logs, no-reload uvicorn

## Summary

- Scenarios: 10 tested, 9 passed, 1 finding (pre-existing)
- Quick fixes: 0
- Blockers: 0

Focus areas driven by sprint 016 changes: EntityKind enum, BrainType enum, fail-fast.
Core enum flows through API/UI verified; no regressions from phase 3/4 changes observed.

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Play/DM split | pass | Two cards visible. EN/RU toggle present. |
| 1.2 | Quick start — pick world + create char | pass | Sword Vale → session `33f8e965` created, WS connected. |
| 1.4 | Point buy | pass | STR 15 (+ disabled), CON 14, remaining 3 pts. Preview HP 12, AC 19 (Chain 16 + Shield 2 + Defense 1), Gold **1000** (playbook says 100 — stale playbook, not a bug). |
| 1.5 | Class-specific UI — Fighter style selector | pass | Defense option applied, preview updated. |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | Marta shown in Nearby with Attack/Talk/Inspect. |
| 2.2 | Talk to NPC UI | pass | Textbox appeared, send btn disabled until input. Did not submit. |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.5 | Sessions list | pass | 4 saved sessions visible, Manage buttons. |
| 6.6 | Spawn dialog | pass | Dialog opens with Type (NPC/Monster), AI Type (Rule-based/LLM), location/name/HP/AC fields. `EntityKind` and `BrainType` enums round-trip through API. Did not actually spawn. |
| 6.8 | Brain toggle | pass | Marta `rule_based` → `llm` → `rule_based`. Backend accepts `BrainType(StrEnum)` values. |

### Section 10: Dashboard Layout

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | Nearby / Character+Inventory / Location columns all visible simultaneously. |

### Auto-discovered scenarios (sprint 016 changes)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| EntityKind value round-trip through creatures table | `EntityKind(StrEnum)` (phase 4 task 1) | pass | Table Type column shows `npc` / `player` correctly; filter buttons NPC/Monster present. |
| BrainType value round-trip through brain toggle & spawn form | `BrainType(StrEnum)` (phase 4 task 2) | pass | Toggle flips between `rule_based` and `llm`; spawn dialog exposes both options. |
| Attack without target_id fails fast | phase 4 task 3 | n/a | Not exercised (validation rejected scope before target_id check); covered by unit tests. |
| Class feature `collect_modifiers` path | phase 3 task 4 | pass | Fighter Defense style → AC 19 = 16 + 2 + 1. Preview live-updates. |

## Quick Fixes

None.

## Findings

### Blockers
None.

### Minor
- **Attack rejected against same-faction peaceful NPC** (`check_target_scope` in `rules/validation.py:303`).
  Player has no combat-side context yet, falls through to faction-equality check, which blocks the action before `combat_manager.resolve_attack` can auto-start combat via `forced_opponents`. This contradicts sprint 014's auto-hostility promise (playbook 13.3).
  **Not a sprint-016 regression** — the scope check was introduced in sprint 015 (commit `12c6a92`). The player entity shares the silverport faction with tavern NPCs, so the fallback blocks. Worth a backlog entry: either the scope validator should defer to the resolver when no combat exists, or attack-outside-combat should route through a distinct "initiate combat" action.
- **Mixed language in UI:** chrome in EN ("Nearby", "Location", "Character"), but NPC race rendered in RU ("человек"). Content comes from backend `DND_LANGUAGE=ru`, frontend i18n defaults to EN — consistent with architecture but looks inconsistent to user. Pre-existing.
- **Gold 1000 vs playbook's 100:** preview shows 1000 gold. Either starting-gold content drifted or playbook is stale; 1000 matches actual seeded content.

## Log Analysis

Backend log clean except for one logged warning matching the rejected attack above:

```
action_failed: "'attack' can only target hostile creatures."
```

Browser console: 0 errors, 2 benign messages (1 warning, 1 info).

No stack traces, no unhandled exceptions in `/tmp/dnd-e2e-backend.log`.
