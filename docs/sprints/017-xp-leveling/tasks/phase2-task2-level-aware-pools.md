# Task: Level-aware resource pools (Paladin L1 fix + Action Surge pool)

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 2 — Level-up mechanics + Paladin L2 fix

## Description

Make `build_class_resource_pools(char_class, level)` emit pools gated by class level
per PHB, fixing the sprint-015 shortcut that gave Paladins spell slots at L1.

Level → pool rules:

- Fighter L1+: `second_wind` (1/short rest).
- Fighter L2+: `second_wind` AND `action_surge` (new pool: 1 use, reset on short rest).
  The pool must exist at L2; the action/handler to consume it lands in task 3.
- Paladin L1: `lay_on_hands` only (5 × level uses). NO spell slots. Matches PHB.
- Paladin L2+: `lay_on_hands` AND spell slots from `_SPELL_SLOT_TABLES[PALADIN]`.
  Remove the L1 entry from the table (or re-anchor so L1 yields no slots).
- Rogue: no pools at any level (Cunning Action is a cost override, no state).

The spell-slot-table comment in `_SPELL_SLOT_TABLES` still references a sprint-015
TODO; remove the comment and the L1 entry.

## Tests First

Product-level scenarios — prefer integration-style where cheap, unit where pure:

- **Paladin L1 has no spell slots**: `build_class_resource_pools(PALADIN, level=1)`
  produces exactly one pool with id `lay_on_hands`, max_uses=5, reset_on=LONG_REST.
  No pool id starts with `spell_slot_`.
- **Paladin L2 has slots**: `build_class_resource_pools(PALADIN, level=2)` produces
  `lay_on_hands` (max_uses=10) plus a level-1 spell-slot pool with 2 uses
  (`spell_slot_pool_id(1)`).
- **Fighter L1 has only second_wind**: one pool, id `second_wind`, no `action_surge`.
- **Fighter L2 gets action_surge**: two pools — `second_wind` and `action_surge`
  (1 use, SHORT_REST).
- **Rogue any level has no pools**: `build_class_resource_pools(ROGUE, 1)` and
  `build_class_resource_pools(ROGUE, 2)` return `[]`.
- **Divine Smite end-to-end blocked at L1**: full integration (live docker) — create
  a Paladin L1, equip longsword, attack a dummy with `smite=1`. The response must
  be a validation error (HTTP 200 with rejected action, or whatever pattern existing
  smite tests use). Then level up to L2 (manually construct or via task 4's endpoint
  if ordering allows — otherwise just verify the unit path: a Paladin L2 with slots
  passes `validate_smite` and consumes the slot on hit).

## Implementation

1. Edit `content_loader/creatures.py` `build_class_resource_pools`:
   - Replace `_SPELL_SLOT_TABLES[PALADIN]`: drop L1 key. L2 keeps `{1: 2}`.
   - Remove the sprint-015 TODO comment.
   - Add Fighter branch: `if level >= 2: append action_surge pool`.
2. Ensure `lay_on_hands` max scales with level (already does: `5 * level`).
3. Define the Action Surge pool id as a constant (e.g. in `rules/resources.py`
   alongside `spell_slot_pool_id`) or keep the literal in `creatures.py` — pick
   whichever matches the existing Second Wind pattern (literal string today).
4. Update existing Paladin fixtures / integration tests that assume L1 has a
   spell slot — most existing tests should be flipped to L2 Paladins for smite
   scenarios. The "no smite at L1" path is new.

## Acceptance Criteria

- [ ] New tests written and RED
- [ ] Implementation GREEN
- [ ] `make check` passes (existing Paladin smite tests updated to L2)
- [ ] `_SPELL_SLOT_TABLES[PALADIN]` no longer has an L1 entry; sprint-015 TODO
      comment removed
- [ ] Fighter L2 character has exactly `second_wind` + `action_surge` pools
- [ ] Paladin L1 character has exactly `lay_on_hands` (5 uses), no slots

## Status

`done`

## Developer Notes

- Removed L1 entry from `_SPELL_SLOT_TABLES[PALADIN]` and the sprint-015 TODO comment; L2 keeps `{1: 2}`.
- Added Fighter L2+ `action_surge` pool (1 use, SHORT_REST) in `build_class_resource_pools`.
- Rogue already returned `[]` (no branch) — covered by new test.
- Kept action_surge id as a literal string to match the existing `second_wind` pattern.
- Updated `test_level1_one_spell_slot` → `test_level1_has_no_spell_slots` in `test_paladin_infra.py`.
- `_paladin(level=1)` in `test_divine_smite.py` still builds a pool directly (not via `build_class_resource_pools`), so it's unaffected. `validate_smite` already blocks L1 regardless of slot presence.
- `test_divine_smite_combat.py`, WS smite integration tests, arena YAML paladin: unaffected — none depended on L1 auto-granting a slot.
