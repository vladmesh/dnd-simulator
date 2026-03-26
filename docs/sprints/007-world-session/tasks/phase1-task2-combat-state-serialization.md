# Task: Serialize Combat State (Mid-Combat Save/Load)

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 1 — Save/Load Completeness

## Description

Serialize active combats so the game can save and restore mid-fight. Currently all combat state (initiative order, round number, battle map positions, walls) is lost on save — creatures keep `in_combat=True` but the actual CombatState is gone.

Serialize in `EntitiesLayer.get_state()`:
- All active combats from `CombatManager._combats`
- Per combat: location_id, turn_order, round_number, rounds_without_attack
- BattleMap: width, height, positions (entity_id → {x, y}), inner walls (list of {x1, y1, x2, y2})

Restore in `EntitiesLayer.load_state()`:
- Reconstruct CombatState + BattleMap from saved data
- Inject into CombatManager (needs a method like `restore_combat(location_id, combat_state)`)

## Tests First

1. **Empty combat round-trip** — No active combats. Save → load → no combats. Baseline.
2. **Mid-combat round-trip** — Start combat between 2 creatures at a location. Advance to round 3. Save → load → assert: same turn_order, round_number=3, both creatures positioned on map at same coordinates, `in_combat=True`.
3. **Battle map walls preserved** — Combat on a map with inner walls. Save → load → walls still block movement (test `is_step_blocked` returns same results).
4. **Multiple simultaneous combats** — Two combats at different locations. Save → load → both restored independently.

## Implementation

- Add `CombatManager.get_combats_state() → dict` and `CombatManager.load_combats_state(data)`.
- In `EntitiesLayer.get_state()`: include `"combats": self._combat.get_combats_state()`.
- In `EntitiesLayer.load_state()`: call `self._combat.load_combats_state(state.get("combats", {}))`.
- BattleMap reconstruction: create BattleMap with saved width/height/walls, then set_position for each entity. Skip `place_randomly` — positions are explicit.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Mid-combat save/load preserves initiative order, round number, positions, walls
- [ ] Multiple simultaneous combats survive round-trip

## Status

`pending`
