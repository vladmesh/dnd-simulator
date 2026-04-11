# Task: Resource Pools in Awareness + Spell Slot UI

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 5 — Smite + Magic Weapon Combo + Polish

## Description

Spell slots (and other resource pools) are invisible to the player during combat. `CombatAwareness` has no resource pool data, so the frontend can't display it. This task adds resource pools to the awareness pipeline and renders spell slots in the CombatPanel.

Changes:
1. **`core/awareness.py`** — Add `self_resource_pools: tuple[ResourcePoolInfo, ...]` to `CombatAwareness`. Define a frozen `ResourcePoolInfo` dataclass (id, max_uses, current_uses).
2. **`layers/entities/awareness_builder.py`** — Populate `self_resource_pools` from `creature.resource_pools` in `build_combat_awareness()`.
3. **`service/session.py`** — `_awareness_to_dict` already uses `dataclasses.asdict`, so the new field serializes automatically. Also add `resource_pools` to `_player_to_dict` so the dashboard can show them outside combat too.
4. **Frontend `types/game.ts`** — Add `self_resource_pools` to `CombatAwareness` interface and `resource_pools` to the player info type.
5. **Frontend `CombatPanel.tsx`** — Render spell slot pools below self stats: show slot level, filled/empty circles for current/max uses.

## Tests First

1. **Unit: combat awareness includes resource pools for a Paladin with spell slots** — Build a level 2 Paladin Creature with spell_slot_1 pool (2 uses). Build combat awareness via AwarenessBuilder. Assert `awareness.self_resource_pools` contains one entry with id="spell_slot_1", max_uses=2, current_uses=2.

2. **Unit: combat awareness resource pools reflect spent slots** — Same setup but spend one slot (current_uses=1). Assert the awareness reflects current_uses=1.

3. **Unit: awareness serialization includes resource pools** — Call `_awareness_to_dict` on a CombatAwareness with resource pools. Assert the output dict has `self_resource_pools` as a list of dicts with correct keys.

4. **Unit: _player_to_dict includes resource pools** — Create a PlayerCharacter with resource pools. Call `_player_to_dict`. Assert the output has `resource_pools` key with correct pool data.

## Implementation

After tests are red:
- Add `ResourcePoolInfo` dataclass to `core/awareness.py`
- Add `self_resource_pools` field to `CombatAwareness`
- Update `AwarenessBuilder.build_combat_awareness()` to populate from `creature.resource_pools`
- Update `_player_to_dict` to include resource pools
- Frontend: update TS types, add spell slot rendering to CombatPanel

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Spell slots visible in CombatPanel during combat (visual check in E2E)
- [ ] Resource pools visible in player info dict

## Status

`done`

## Developer Notes

Added `ResourcePoolInfo` frozen dataclass to `core/awareness.py` and `self_resource_pools` field to `CombatAwareness`. AwarenessBuilder populates it from `creature.resource_pools`. `_awareness_to_dict` explicitly serializes to list of dicts (dataclasses.asdict converts tuples-of-dataclasses to tuples-of-dicts, not lists). `_player_to_dict` now includes `resource_pools` for dashboard display outside combat.

Frontend: `ResourcePoolInfo` TS interface, `self_resource_pools` on `CombatAwareness`, `resource_pools` on `PlayerStatus`. CombatPanel renders spell slot pools as filled/empty amber circles per level. Only spell_slot_* pools displayed (not lay_on_hands etc — those are actions, not visual resource displays).
