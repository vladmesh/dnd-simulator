# Task: Long Rest & Short Rest Actions

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 1 — Spell Slots as ResourcePool

## Description

Add Long Rest and Short Rest as proper game actions. Currently `reset_resources()` exists in `rules/resources.py` but is never called in production — resource pools can be depleted but never recovered.

Long Rest (D&D 5e): resets all resource pools (both SHORT_REST and LONG_REST types), heals creature to full HP, advances game time by 8 hours. Short Rest: resets only SHORT_REST pools (e.g. Second Wind), advances time by 1 hour. Both are available only outside combat.

Key files to modify:
- `core/action.py` — add ActionType.LONG_REST, ActionType.SHORT_REST
- `core/action_defs.py` — ActionDef entries (action cost, not in combat)
- `rules/handlers/` — new `rest.py` handler module
- `rules/action_provider.py` — offer rest actions when out of combat
- Register handlers in `service/action_dispatcher.py`

## Tests First

Scenarios for `tests/unit/test_rest.py`:

1. **Long rest resets all resource pools.** Create a Fighter with depleted `second_wind` pool (SHORT_REST) and a creature with depleted `spell_slot_1` pool (LONG_REST). Long rest → both pools restored to max_uses.
2. **Short rest resets only SHORT_REST pools.** Creature with depleted second_wind (SHORT_REST) and spell_slot_1 (LONG_REST). Short rest → second_wind restored, spell_slot_1 still depleted.
3. **Long rest heals to full HP.** Creature at 5/20 HP. Long rest → HP = max_hp.
4. **Short rest does NOT heal.** Creature at 5/20 HP. Short rest → HP still 5.
5. **Rest blocked in combat.** Creature with `in_combat=True`. Action validation rejects rest action.
6. **Rest advances game time.** Long rest advances 8 hours (28800 seconds). Short rest advances 1 hour (3600 seconds). Verify via ActionResult or world time change.
7. **Action provider offers rest out of combat.** Creature not in combat → LONG_REST and SHORT_REST in available actions.
8. **Action provider hides rest in combat.** Creature in combat → no rest actions.

## Implementation

1. Add `LONG_REST = "long_rest"` and `SHORT_REST = "short_rest"` to ActionType enum.
2. Add ActionDef entries: action cost, `combat_only=False`, `non_combat_only=True` (or equivalent — check how `wait` handles this).
3. Create `rules/handlers/rest.py` with `handle_long_rest` and `handle_short_rest`. Both call `reset_resources()` from `rules/resources.py`. Long rest also calls `creature.heal(creature.max_hp)`. Both emit a rest event and set `wake_at_seconds` for time advancement (same pattern as `wait` handler).
4. Add `RestActionProvider` to `rules/action_provider.py` — offers rest when `not creature.in_combat`.
5. Register handlers in action_dispatcher.
6. Add i18n strings for rest events.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Long rest resets all pools + heals to full + advances 8 hours
- [ ] Short rest resets SHORT_REST pools only + advances 1 hour
- [ ] Rest blocked during combat
- [ ] Fighter's Second Wind recoverable via short rest in a real game flow

## Status

`pending`
