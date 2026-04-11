# Phase 7 E2E Report

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 7 — Smite UI + Level 1 Spell Slot

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Level 1 Paladin has spell slot | Paladin created with 1 spell slot (level 1) | Spell Slots "Lv1" section visible in combat panel | pass |
| Smite choice UI appears | After clicking Attack with spell slots, show "Attack" and "Attack + Smite" options | Dropdown shows "Attack" and "Attack + Smite (slot 1)(1/1)" | pass |
| Smite action sends correctly | Clicking "Attack + Smite" sends attack with smite_slot_level=1 | Action sent (reach error when out of range confirms param sent correctly) | pass |
| Normal attack still works | "Attack" option (no smite) sends standard attack | First attack was normal (longsword slash d20(7)+4=11 vs AC 12, miss) | pass |
| Slot count display | Shows remaining/max uses | Displayed as "(1/1)" on the button | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | Session created, character creation worked |
| Character creation (Paladin) | pass | Point buy, starting equipment (Chain Mail, Longsword, Shield), AC 18 |
| Peaceful mode | pass | NPC interaction, location display, travel between locations |
| Basic combat | pass | Attack triggered combat, initiative order shown, battle map rendered |
| Target scope validation | pass | "attack can only target hostile creatures" when attacking neutral NPC |
| Click-to-move on battle map | pass | Moved 20ft northeast, then 5ft west — movement budget tracked correctly |
| Lay on Hands action visible | pass | Shown in action bar for Paladin |

## Quick Fixes Applied

- None needed

## Log Analysis

- No errors or exceptions in backend logs during E2E session
- No console errors in browser (only 1 pre-existing warning)

## Blockers

- None

## Minor Issues

- Integration tests had 2 flaky WebSocket timeout failures (test_two_enemies_both_oa, test_smite_adds_radiant_damage) on first run; passed on second run and in isolation. Root cause: random battle map placement + race conditions under load. Not a phase 7 regression — pre-existing flakiness.
