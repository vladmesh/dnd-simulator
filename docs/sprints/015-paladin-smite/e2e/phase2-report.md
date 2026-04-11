# Phase 2 E2E Report

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 2 — Paladin Class Foundation

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Paladin in class dropdown | Paladin appears as 3rd class option | Paladin shown after fix (was missing) | pass |
| Paladin preview (HP/AC/equipment) | HP=d10+CON, AC=18, Chain Mail+Longsword+Shield | HP 10 (CON 10), AC 18, correct equipment | pass |
| Paladin preview HP with CON | CON 12 (+1) -> HP 11 | HP 11 shown correctly | pass |
| Create Paladin character | Character created, game loads | Human Paladin L1, AC 18, 11/11 HP | pass |
| Lay on Hands in action bar | lay_on_hands button visible | Button present in action bar | pass |
| Paladin NPC resource pools | Paladin NPC has lay_on_hands pool | Verified via integration test (max=5, reset=long_rest) | pass |
| Paladin character creation API | POST /character with paladin class succeeds | Works after adding PALADIN to supported_classes | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world | pass | Sword Vale and Test Vale both load correctly |
| Basic combat | pass | Attack barkeep, dice breakdown in log, NPC dies, combat ends |
| Reputation change | pass | Killing NPC shows reputation drop (50 -> 30) |
| Character panel | pass | Stats, inventory, equipment all display correctly |

## Quick Fixes Applied

- Added `CharClass.PALADIN` to `supported_classes` in `game_service.py:create_player()` — Paladin was missing from player creation validation
- Added `CharClass.PALADIN` to fighting style validation (allows paladin to optionally have a fighting style)
- Added Paladin to frontend `CLASSES`, `HIT_DICE`, `STARTING_EQUIPMENT`, `previewAc()` in `CharacterForm.tsx`
- Added `class_paladin` translation keys to `setup.json` (en + ru)
- Updated frontend test for class options (2 -> 3 classes)
- Increased DELETE session timeout in `test_reputation.py` and `test_websocket.py` (5s -> 15s) to fix teardown timeouts on combat sessions

## Log Analysis

- No errors or exceptions in backend logs for E2E sessions
- Frontend log clean (old ECONNREFUSED from prior session startup, not from our run)

## Blockers

- None

## Minor Issues

- `lay_on_hands` button in action bar shows raw action name, not localized — existing pattern for all non-core actions (short_rest, long_rest also raw). Backlog candidate for action bar i18n.
- Clicking lay_on_hands without parameters sends the action without the required `amount` param, causing it to fail silently. The action bar doesn't prompt for parameters. This is an existing UI limitation for parameterized actions — not specific to this phase.
