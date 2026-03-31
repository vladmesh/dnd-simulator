# Phase 2 E2E Report

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 2 — Movement Integration + Round Wiring

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| OA triggers on move away from adjacent NPC | NPC melee attack as reaction | OA fired: `[d20(3)+2=5 vs AC 10], miss` | pass |
| Movement continues after OA miss | Player completes click-to-move path | Player moved to target cell, movement budget decreased | pass |
| Disengage then move away | No OA fires | No OA event in log, movement succeeded cleanly | pass |
| Budget display shows Reaction | Reaction: 1 visible in action bar | Reaction: 1 shown alongside Actions/Bonus/Movement | pass |
| Game loop continues after NPC moves away from player | PlayerBrain auto-skips reaction (no frontend UI yet) | Game loop continues, no hang | pass (after fix) |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | Dashboard renders correctly, 3-column layout |
| Start combat (attack NPC) | pass | Combat log, battle map, initiative order all correct |
| Basic attack + damage | pass | Roll displayed with modifier, damage applied |
| NPC takes turn (LLM brain) | pass | NPC moves, attacks, turn ends correctly |
| Click-to-move on battle map | pass | Reachable cells highlighted, movement works |
| End turn + round progression | pass | Rounds advance, NPC/player alternate |

## Quick Fixes Applied

- **PlayerBrain.choose_reaction blocks forever** when no frontend reaction UI is wired up. `_on_reaction` callback was never set by the WebSocket transport (Phase 3 scope), so `_reaction_queue.get()` blocked indefinitely when the NPC moved away from the player. Fixed: auto-return SKIP when `_on_reaction` is None. File: `src/dnd_simulator/core/brain.py:378-381`.

## Log Analysis

- No unexpected errors or exceptions in backend logs
- LLM NPC occasionally tries `move_to` with no movement remaining (pre-existing behavior, not Phase 2 related)
- OA events logged correctly in round logs

## Blockers

None.

## Minor Issues

- `opportunity_attack` event shows as "Something happened (opportunity_attack)" in combat log — missing dedicated perception handler for OA events (backlog for Phase 3)
- `entity_disengage` event shows as "Something happened (entity_disengage)" — same missing perception handler issue
