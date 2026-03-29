# Phase 4 E2E Report

**Date:** 2026-03-29
**Sprint:** 011-class-mechanics-l1
**Phase:** 4 — Content & Tests

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Sword Vale world loads with new NPCs | Ser Aldric and Lira visible in Entities | Both present: Aldric (28 HP, AC 19), Lira (20 HP, AC 15) | pass |
| Ser Aldric has correct equipment | Longsword equipped, AC 19 (chain mail + shield + Defense) | Longsword slash (1d8 slashing) equipped, AC 19 | pass |
| Guard Captain Rodrik upgraded equipment | AC 18 | AC 18 (chain mail + shield) | pass |
| DM creature edit shows equipment | Dialog shows equipped weapon info | "Equipped weapon: longsword slash (1d8 slashing)" shown | pass |
| Attack vs high-AC target | Miss against AC 19 with low roll | d20(8)+5=13 vs AC 19 = miss | pass |
| Attack card modal shows breakdown | Clickable log entry expands to full breakdown | Modal: d20(19), +3 STR, +2 Prof = 24 vs AC 10. Damage: 1 bludgeon + 3 STR = 4 | pass |
| Range validation | "Target too far" when out of reach | "25 ft, reach 5 ft" message shown correctly | pass |
| Battle map movement | Click-to-move decrements budget | Movement budget correctly decremented per 5ft step | pass |
| Flee action | Ends combat, consumes action | Combat ended, action consumed, back to exploration | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world | pass | Sword Vale and Test Vale both load |
| Create character | pass | Fighter created, stats displayed correctly |
| Travel between locations | pass | Tavern -> Market -> City Gates, paths and distances correct |
| Basic combat (vs Marta) | pass | One-shot kill, initiative, attack, damage, death, combat end all work |
| NPC interaction (nearby panel) | pass | NPCs shown with Attack/Talk buttons, race displayed |
| Trade UI | pass | Gretta merchant panel shown at Market Square with gold amount |
| DM session management | pass | Create session, manage creatures, view world layers |
| Structured dice in log | pass | d20 rolls, modifiers, damage dice all shown with values |

## Quick Fixes Applied

- None needed.

## Log Analysis

- **WebSocket disconnect error**: `ConnectionClosedError: no close frame received or sent` — happens when browser navigates away from a WS-connected page. Expected behavior, not a bug.
- **LLM calls**: Memory summarizer fires after combat ends (3117ms, 368 tokens in, 96 out). Working as expected.
- **NPC memory update**: `npc_memory_updated` event fires for Aldric after combat — memory system working.
- No unexpected errors or warnings in server logs.

## Blockers

- None.

## Minor Issues

- **Battle map centering**: When player and NPC are far apart on the battle map, the player marker ("1") can be off-screen while the NPC ("@") is visible. The map doesn't auto-scroll/center on the player. Pre-existing issue, not phase 4 related.
- **RuleBrain fleeing**: Guard NPC (Ser Aldric, a fighter) flees from hostile player instead of fighting back. Equal-speed NPCs can never be caught. Game design consideration for future sprint — guards should stand and fight.
