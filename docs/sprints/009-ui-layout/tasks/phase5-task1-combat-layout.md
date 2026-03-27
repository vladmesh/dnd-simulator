# Task: Combat Layout Restructure

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 5 — Combat Layout + Click-to-Move

## Description

Restructure the 3-column dashboard for combat mode: move BattleMap from the left column (where it sits above CombatPanel) into the right column (replacing LocationPanel). CombatPanel gets the full left column height. Still uses ASCII `<pre>` rendering — interactive grid is task 2.

**Changes:**
- `GameScreen.tsx`: in combat, right column renders `<BattleMap />` instead of `<LocationPanel />`
- `GameScreen.tsx`: left column in combat renders only `<CombatPanel />` (no BattleMap above it)
- `LocationPanel` stays visible in peaceful mode (no change)
- `BattleMap.tsx`: remove from left column import/usage in combat branch

## Tests First

Frontend layout — tested via E2E (Playwright). No unit tests for layout shuffling.

Scenarios to verify in E2E:
- In peaceful mode: left column = Perception + Trade, right column = Location with paths (unchanged)
- In combat mode: left column = CombatPanel only (enemies + self stats, full height), right column = ASCII BattleMap
- Transitioning from peaceful → combat (attack NPC): layout switches correctly
- Combat ends: layout returns to peaceful (Location panel back in right column)

## Implementation

1. Edit `GameScreen.tsx` — restructure the conditional rendering:
   - Left column combat branch: just `<CombatPanel />`
   - Right column: `{isCombat ? <BattleMap /> : <LocationPanel />}`
2. No changes to BattleMap or CombatPanel component internals

This is a ~10-line change in one file.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] In combat: BattleMap in right column, CombatPanel in full left column
- [ ] In peaceful: LocationPanel in right column (unchanged)
- [ ] No scrolling needed to see enemies list in combat

## Status

`done`

## Developer Notes

Straightforward layout swap in GameScreen.tsx. Left column in combat now renders only CombatPanel (no BattleMap above it). Right column conditionally renders BattleMap in combat or LocationPanel in peaceful. Updated existing combat test that expected LocationPanel to stay visible; added a new test verifying BattleMap and CombatPanel are in separate columns. No old tests broken — one was updated to reflect the intentional contract change (LocationPanel hidden during combat).
