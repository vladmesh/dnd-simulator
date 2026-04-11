# Phase 3 E2E Report

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 3 — Divine Smite

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Create Paladin via character creation UI | Paladin class available, correct HP/AC/equipment | Paladin created: HP 12, AC 18, Longsword/Chain Mail/Shield | pass |
| Paladin dashboard shows class info | "Human Paladin L1" with correct stats | Displayed correctly, lay_on_hands in action bar | pass |
| Grant spell slots via PATCH resource_pools | API accepts and applies pools | 200 OK, spell_slot_1 added (2/2) | pass |
| Attack NPC (combat basics) | Combat starts, attack resolves with damage | Combat resolved: d20(9)+4=13 vs AC 10, 4 damage (1d8 slashing + +2 str) | pass |
| Divine Smite backend (integration tests) | smite_slot_level=1 adds 2d8 radiant on hit | 122 integration tests pass including 2 new smite tests | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | Session created, world loaded |
| Character creation (Paladin) | pass | Point buy, equipment preview, all functional |
| Basic combat (attack NPC) | pass | Longsword attack, damage log, reputation change |
| Navigation (move between locations) | pass | Tavern → Docks, NPC encountered |
| NPC interaction (LLM-brain) | pass | Marta and Lira spoke via LLM, responses coherent |

## Quick Fixes Applied

- Fixed `test_move_to_in_combat` flaky integration test — was trying only one adjacent cell which could be blocked; now tries 4 candidates
- Fixed `test_smite_without_slots_fails` — used invalid alignment value "neutral" instead of "true_neutral"
- Added `resource_pools` support to PATCH creature endpoint (needed for granting spell slots to level 1 characters in tests)

## Log Analysis

- **KeyError: 'amount' in handle_lay_on_hands** — pre-existing issue (phase 2). The action bar shows a `lay_on_hands` button but the frontend doesn't prompt for the `amount` parameter, causing a crash in the round loop. Not a phase 3 regression. Added to minor issues.
- No other errors, warnings, or unexpected behavior in session logs.

## Blockers

- None

## Minor Issues

- Fighting Style selector not shown for Paladin in character creation UI (shown for Fighter only). Paladin should also get fighting styles per D&D 5e. Pre-existing from phase 2.
- `lay_on_hands` action bar button crashes the round loop because it doesn't include the required `amount` parameter. Needs a UI dialog. Pre-existing from phase 2.
- Divine Smite has no frontend trigger yet — the `smite_slot_level` param exists on the attack action but the UI has no way to activate it. This is by design — spell slot display and smite UI are planned for phase 5.
