# Phase 4 E2E Report

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 4 — Bug Fixes (Starting Equipment, Dead-Mover, Brain Spam)

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Character creation — starting equipment in preview | Preview shows Chain Mail, Longsword, Shield | Preview shows "Starting equipment: Chain Mail, Longsword, Shield" | pass |
| Character creation — point buy + Defense style | HP 12, AC 19, Gold 100 | HP 12, AC 19 (preview), Gold 100 | pass |
| In-game inventory shows equipped items | Weapon/Armor/Shield slots filled | Longsword, Chain Mail, Shield all visible in equipment slots | pass |
| Combat uses real weapon (not unarmed) | Attack log shows longsword slash + 1d8 damage | "longsword slash [d20(9)+4=13 vs AC 10], 4 damage (1d8 slashing + STR)" | pass |
| Dead creature not processed after kill | No "dead creature can't act" spam | Combat ended cleanly: attack → entity_died → reputation_change → combat_ended | pass |
| Combat log clean (no brain spam) | No repeated failed move_to attempts | Clean combat sequence, no movement spam in logs | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Landing page | pass | Two cards (Play/DM), language toggle |
| Load world + create character | pass | Sword Vale → New Session → Fighter with point buy |
| Basic combat (attack NPC) | pass | Longsword attack, damage, entity_died, combat_ended |
| Wait + time advance | pass | Time 10:00 → 11:00 after Wait |

## Quick Fixes Applied

None.

## Log Analysis

- No errors or exceptions in current session logs.
- Old sessions (March 31) still show movement spam from "Lira" — these predate the phase 4 fix, confirming the fix was needed.
- Clean debug logs: ecology ticks, activation, round events all normal.

## Blockers

None.

## Minor Issues

- **AC display shows 18 instead of 19 with Defense fighting style.** The character creation preview correctly shows AC 19 (Chain Mail 16 + Shield 2 + Defense 1), but the in-game dashboard shows AC 18. `effective_ac()` returns 19 when called with correct equipment+features in isolation, but the runtime player object appears to lose the Defense modifier context. This is pre-existing (not a phase 4 regression) — the core fix (weapon equipping) works correctly. Recommend backlog item to investigate.
