# Task: BattleMap click-to-inspect + faction display

**Date:** 2026-03-28
**Sprint:** 010-e2e-polish
**Phase:** 1 — E2E UX Fixes

## Description

Three related changes that make the battle map the primary combat UI:

1. **Click occupied cell → creature inspect.** Currently clicking an occupied BattleMap cell does nothing (`isClickable` requires `!entity`). Change: clicking an occupied cell opens NpcInspectModal for that creature. Player's own cell is excluded (no self-inspect).
2. **Faction display name.** NpcInspectModal shows raw `faction_id` ("kingdom") instead of the display name ("Королевство Серебрянка"). The awareness data likely doesn't carry the display name — either add it to the awareness payload or resolve it frontend-side from settlement/faction data already in the store.
3. **Remove combatants list from CombatPanel.** The "Enemies" section (lines 70-121 of CombatPanel.tsx) listing combat participants is redundant now that the map is interactive. Remove it — the map becomes the only way to see who's in combat.

Key files:
- `frontend/src/components/game/BattleMap.tsx` — click handler, `isClickable` logic
- `frontend/src/components/game/NpcInspectModal.tsx` — faction display (line ~102)
- `frontend/src/components/game/CombatPanel.tsx` — enemies list to remove
- Backend: awareness payload may need `faction_name` added (check `perception.py` or `session.py`)

## Tests First

1. **Click occupied cell opens inspect modal.** Render BattleMap with player at (0,0) and enemy at (1,0). Click cell (1,0). Assert NpcInspectModal opens with the enemy's data.
2. **Click player's own cell does nothing.** Click cell (0,0). Assert no modal opens.
3. **Faction shows display name.** Render NpcInspectModal with a nearby entity that has `faction_id: "kingdom"` and `faction_name: "Королевство Серебрянка"`. Assert the modal displays the name, not the ID.
4. **CombatPanel has no enemies list.** Render CombatPanel in combat mode. Assert the "Enemies" section is absent.

## Implementation

1. **BattleMap.tsx:** Add an `onEntityClick(entityId)` callback. In the cell click handler, if the cell has an entity (and it's not the player), call `onEntityClick` instead of move. Make occupied enemy cells have `cursor-pointer`.
2. **GameScreen.tsx or CombatPanel.tsx:** Wire `onEntityClick` to open NpcInspectModal with the clicked entity's data from awareness.
3. **NpcInspectModal.tsx:** Display `faction_name` if available, fall back to `faction_id`. If neither — hide the faction line.
4. **Backend (if needed):** Add `faction_name` to the perceived nearby entity data in `perception.py` or the awareness builder.
5. **CombatPanel.tsx:** Remove the enemies list section. Keep initiative order display, round counter, and any other non-redundant combat info.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Clicking enemy on BattleMap opens inspect modal with correct creature data
- [ ] Clicking player's cell does not open modal
- [ ] Faction shows human-readable name, not raw ID
- [ ] CombatPanel no longer lists individual enemies

## Status

`done`

## Developer Notes

Implementation followed the plan closely. Key decisions:

- **BattleMap gets `onEntityClick` prop** — keeps the map component focused on grid rendering, modal state managed by GameScreen.
- **CombatPanel enemies list removed entirely** — the map is now the sole combat entity browser. CombatPanel retains round counter and self-stats only.
- **Faction name resolution is backend-side** — added `FACTION_NAME` query to politics layer, `faction_name` field to `NearbyEntity` dataclass. `load_factions` now returns `FactionData` (relations + localized names). The existing `test_load_factions_from_yaml` and `test_load_factions_missing_file` tests updated to match the new return type (intentional contract change).
- **NpcInspectModal** displays `faction_name` with fallback to `faction_id`.
