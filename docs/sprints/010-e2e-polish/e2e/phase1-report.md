# Phase 1 E2E Report

**Date:** 2026-03-28
**Sprint:** 010-e2e-polish
**Phase:** 1 — E2E UX Fixes

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Combat log i18n — damage types, weapon names, AC label | All combat log text in Russian when DND_LANGUAGE=ru | "кулаки", "дробящий", "КЗ", "модификатор" — all translated | pass |
| BattleMap click occupied cell → inspect card | Click numbered cell opens creature inspect dialog with name, distance, status, attack button | Dialog opened: "Гоблин, выглядит раненым", "25фт на северо-востоке", "(ранен)", Attack button | pass |
| Combatants list removed from CombatPanel | Combat panel shows only round/stats, no participant list | No combatants list visible; battlemap is sole combat UI | pass |
| HP current/max in creature edit dialog | Separate Current HP and Max HP input fields | Two spinbutton fields: "Current HP" = 18, "Max HP" = 18 | pass |
| Brain toggle with LLM key present | Toggle works, success toast, ai_type changes | Toggled edgar to llm, success toast "Сменить мозг", table updated | pass |
| Brain toggle warning (no LLM key) | Returns warning, stays rule_based | Verified via integration test (no key in Docker): brain_type=rule_based, warning=no_llm_key | pass |
| Consumable drawer tooltip | Health Potion shows description tooltip | Tooltip: "Health Potion (heals 2d4+2 HP)" visible on item | pass |
| Log overlay backfill | Opening overlay shows existing events, not "Waiting..." | Overlay showed full event history from Round 11 through current | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (master panel) | pass | Regions, nations, settlements all load correctly |
| Creature list in master panel | pass | HP shows as current/max, brain toggle works |
| Join session as player | pass | WebSocket connects, player view renders |
| Basic combat — attack NPC | pass | Attack resolves, damage logged, battlemap updates |
| End turn — NPC turns process | pass | Round advances, NPCs act, player turn resumes |
| Character panel & inventory | pass | Stats, equipment slots, bag with items all render |

## Quick Fixes Applied

- Recompiled `dnd_simulator.mo` with `pybabel` — the committed `.mo` had broken charset encoding (ascii instead of UTF-8), causing `UnicodeDecodeError` on import. Root cause: `make compile-messages` used `msgfmt` which wasn't installed, silently failing.
- Fixed `make compile-messages` Makefile target to use `uv run pybabel compile` instead of system `msgfmt`.
- Updated integration test `test_save_load_preserves_brain_switch` to account for new brain toggle behavior (returns actual type + warning instead of optimistic type).

## Log Analysis

- No errors, exceptions, or tracebacks in server logs or session logs.
- 1 console warning in browser: WebSocket reconnection attempt (benign — occurs on page load before session is fully initialized).

## Blockers

None.

## Minor Issues

None.
