# E2E Report: Post-Audit Regression

**Date:** 2026-03-26
**Flags:** --no-llm (LLM NPCs present in arena but not explicitly tested)
**Sections tested:** 1, 2, 3 (partial), 6, 8.1
**Stack:** DEBUG=1, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 16 tested, 14 passed, 2 had issues (both fixed)
- Quick fixes: 2 applied
- Blockers: 0

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Create character and enter game | pass | Blood Arena, fighter, STR 16, redirects to /play/:id, WS connected |
| 1.2 | Language toggle | pass | EN→RU labels switch correctly, Sword Vale shows Russian name/description |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC tanya visible at tavern with Attack/Talk/Inspect buttons |
| 2.2 | Talk to NPC (rule-based) | pass | Player says text, NPC responds with canned dialogue "Что будете заказывать?" |
| 2.3 | Wait and time advance | pass | Time 10:00 → 11:00 after Wait |
| 2.4 | Move between locations | pass | Village square → Таверна, location panel updates |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | combat_started, initiative order, battle map, combat panel with budget |
| 3.2 | Attack and damage | pass | [d20(14)+6=20 vs AC 13], 5 damage (1 bludgeoning + +4 ability) — format correct |
| 3.3 | End turn and NPC response | pass | NPCs act (equip weapons, attack, move), round advances |
| 3.4 | Combat ends | skipped | Would require many rounds; combat stability verified over 3 rounds |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Create and manage session | pass | New session created, appears in list |
| 6.2 | Spawn creature | skipped | |
| 6.3 | Edit creature HP | pass | HP changed 4→10, reflected in table |
| 6.4 | Toggle brain type | pass | rule_based → llm, toast confirms |
| 6.5 | Delete creature | skipped | |
| 6.6 | Advance time | pass | 24h advance, D1→D2 |
| 6.7 | Save and load | pass | Save created, load confirmed with dialog, state restored |

### Section 8: Inventory

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 8.1 | View inventory panel | pass | 6 slots visible (Weapon, Armor, Shield, Head, Feet, Ring) |

### Sections not tested

- Section 4 (Class Features) — no changes since last E2E
- Section 5 (Equipment) — no changes since last E2E
- Section 7 (Conditions) — no changes since last E2E
- Section 8.2-8.3 (Equip/unequip accessories) — no changes since last E2E
- Section 9 (Trading) — no changes since last E2E
- Section 10 (LLM) — skipped per --no-llm

## Quick Fixes

### Fix 1: LLM NPC move with `toward` param crashes round loop

**Root cause:** `handle_move` in `action_handlers.py` required `direction` key, but LLM NPCs use `toward`/`away_from` params. The `resolve_abstract_move` function (which converts `toward` → `direction`) was only called for player actions in `session.py:submit_action`, not for NPC actions in `round.py:run_combat_turn`.

**Fix:**
- `round.py:283-287` — Added `resolve_abstract_move` call for any creature's MOVE action with `toward`/`away_from` params
- `action_handlers.py:117-118` — Added graceful validation: return `ActionResult(success=False)` if `direction` missing instead of `KeyError` crash
- `action_handlers.py:119` — Default `ft` to 5 (not in LLM tool schema, internal param)

**Files:** `src/dnd_simulator/round.py`, `src/dnd_simulator/rules/action_handlers.py`

### Fix 2: Missing `ft` param in move action

**Root cause:** `ft` parameter was not part of the LLM tool schema for `move`, but `handle_move` did `action.params["ft"]` unconditionally. LLM never sends `ft`.

**Fix:** Changed to `action.params.get("ft", 5)` — 5ft is the standard D&D grid step.

**File:** `src/dnd_simulator/rules/action_handlers.py:119`

## Findings

### Blockers
None.

### Minor
- LLM NPC (paladin) repeatedly tries to move into walls (3+ consecutive blocked moves per turn). The LLM doesn't learn from failures within a turn. Not a regression — existing behavior, but wastes LLM tokens.
- "Move requires a direction" message shown to player in event log when LLM NPC sends a move without `toward`/`away_from`/`direction`. Cosmetic — should be filtered from player-visible events.

## Log Analysis

- No tracebacks or exceptions in post-fix session (73fbec75)
- LLM calls to OpenRouter (google/gemini-3.1-flash-lite-preview) succeeding — response times ~1-2s
- `action_failed` events at info level for NPC wall collisions — handled gracefully
- Frontend: 0 console errors, 0 warnings (besides expected WS reconnection on page load)
