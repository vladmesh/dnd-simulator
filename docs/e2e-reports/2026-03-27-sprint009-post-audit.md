# E2E Report: Post-audit regression (Sprint 009)

**Date:** 2026-03-27
**Flags:** --no-llm
**Sections tested:** 1, 2, 3, 6 + auto-discovered (sprint 009 features)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 24 tested, 24 passed, 0 failed
- Quick fixes: 0 applied
- Blockers: 0 found

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page — Player/DM split | pass | Two cards: Play + Dungeon Master |
| 1.2 | Quick start — pick existing world | pass | World list, character created (fighter, human, STR 16), redirected to /play/:id, WS connected |
| 1.3 | Language toggle | pass | EN→RU switches all labels |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | NPC visible with Attack/Talk/Inspect buttons |
| 2.2 | Talk to NPC (rule-based) | pass | Player says text, NPC responds with canned reply ("Что будете заказывать?") |
| 2.3 | Wait and time advance | pass | Time 10:00 → 11:00 (1 hour) |
| 2.4 | Move between locations | pass | Moved to Market Square, new NPCs + merchant visible, paths updated |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | Combat started, initiative order shown, CombatPanel in left column, BattleMap CSS Grid in right column, budget display in action bar |
| 3.2 | Attack and damage | pass | d20+5 roll shown, damage applied, "ранен" status, critical hit displayed correctly |
| 3.3 | End turn and NPC response | pass | NPC used Health Potion (healed 8 HP), round advanced to 2 |
| 3.4 | Combat ends | pass | Enemy killed ("погибает"), "Бой окончен", sidebar returned to peaceful, LocationPanel restored |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Worlds tab | pass | Library worlds with Fork buttons shown |
| 6.2 | Fork world | pass | Fork dialog, new world with Fork+Delete buttons, toast "Мир форкнут" |
| 6.3 | Delete world | pass | Confirm dialog, world removed from list |
| 6.5 | Create session | pass | New session created with toast, appears in list |
| 6.6 | Spawn creature | pass | Monster spawned at market, visible in table as monster type |
| 6.7 | Edit creature HP | pass | HP changed to 25, reflected in table as 25/10 |
| 6.8 | Toggle brain type | pass | Toast "Сменить мозг", stays rule_based without LLM key — expected |
| 6.9 | Delete creature | pass | Confirm dialog, creature removed from table |
| 6.10 | Advance time | pass | 24h advanced, weather changes + squad events reported |
| 6.11 | Save and load | pass | Save created, load confirmed via dialog, state restored (D2 10:00) |

### Auto-discovered scenarios (Sprint 009 changes)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Dashboard 3-column layout | Phase 1 — dashboard grid | pass | Nearby, Character+Inventory, Location all visible simultaneously. No tabs needed. |
| Compact log strip + expand overlay | Phase 1 — log modes | pass | Log strip shows last events inline. Expand button opens overlay with "Журнал событий" heading and close button. |
| Log event formatting | Phase 2 — log formatting | pass | Events have icons (sword for attack, speech for say). Turn headers separate combat turns. Color-coded entries. |
| Action bar with budget display | Phase 3 — action bar redesign | pass | Budget line shows Actions/Bonus/Movement/Reaction counts. Core buttons visible. Cost-based styling (spent actions = buttons removed). |
| Consumable drawer button | Phase 3 — action drawers | pass | "1" button with potion icon visible in action bar (shows consumable count) |
| NPC inspect modal | Phase 4 — NPC inspect card | pass | Modal shows name, race+role, description from YAML, faction, Attack/Talk buttons |
| Combat layout restructure | Phase 5 — combat layout | pass | CombatPanel in left column (full height), BattleMap in right column (replaces LocationPanel during combat) |
| BattleMap CSS Grid | Phase 5 — interactive battlemap | pass | Grid renders with "@" for player, "1" for enemy. Reachable cells have cursor=pointer. Non-reachable cells are static. |
| Click-to-move | Phase 5 — click-to-move | pass | Clicked adjacent cell, player "@" moved, movement budget decreased 30ft→25ft, reachable cells re-computed |

## Quick Fixes

None needed.

## Findings

### Blockers

None.

### Minor

None.

## Log Analysis

- No errors or exceptions in backend logs
- No browser console errors (0 errors across all scenarios)
- Only log entry of note: expected "target too far" action_failed when trying to attack from 10ft (correctly blocked, info level)
