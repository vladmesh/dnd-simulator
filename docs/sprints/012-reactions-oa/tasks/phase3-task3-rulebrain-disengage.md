# Task: RuleBrain Tactical Disengage

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 3 — Frontend + Content

## Description

RuleBrain currently uses FLEE at low HP, which now provokes opportunity attacks. Smart NPCs should Disengage before retreating when enemies are in melee reach.

Current behavior at low HP:
- 15% HP (25% if SCARED) → FLEE → movement provokes OA → NPC may die retreating
- 25% HP (35% if SCARED) → DODGE if enemy ≤ 5ft

New behavior: insert a Disengage check between DODGE and FLEE thresholds. When HP is low enough to want to retreat AND enemies are within melee reach:
- Use DISENGAGE (costs action) → sets `is_disengaging = True`
- Next call to `choose_action` in the same turn: MOVE away (uses movement, no OA)
- If no enemies in reach, skip straight to FLEE (no OA risk)

This means splitting the retreat into two actions within the multi-action turn loop. First call returns DISENGAGE, second call returns MOVE (away from nearest enemy). RuleBrain needs minimal state awareness — after using Disengage, the `is_disengaging` flag on the creature tells it to move away instead of attacking.

Also verify: RuleBrain `choose_reaction` (always OA) is still correct behavior. No changes needed there.

## Tests First

**Unit tests** (in `tests/unit/test_brain.py` or new `test_rulebrain_tactics.py`):
- RuleBrain with creature at 20% HP, enemy at 5ft reach → returns DISENGAGE (not FLEE, not ATTACK)
- RuleBrain with creature at 20% HP, `is_disengaging=True`, enemy at 5ft → returns MOVE away from enemy
- RuleBrain with creature at 20% HP, no enemies within 10ft → returns FLEE (no Disengage needed, nobody to OA)
- RuleBrain with creature at 80% HP, enemy at 5ft → returns ATTACK (not Disengage — HP is fine)
- RuleBrain with SCARED tag at 30% HP, enemy at 5ft → returns DISENGAGE (SCARED threshold is higher)
- RuleBrain choose_reaction still returns OA for LEAVING_REACH trigger (unchanged)

## Implementation

1. **`core/brain.py` — `_choose_combat_action`**: Add Disengage logic between DODGE check and FLEE check:
   - If `creature.is_disengaging` and `budget.movement_remaining > 0` → MOVE away from nearest enemy (retreat phase 2)
   - If HP below flee threshold AND any hostile within melee reach (≤ weapon reach) AND has action budget → DISENGAGE
   - Existing FLEE stays as fallback for when no enemies are in reach
2. Add helper to check "any hostile within reach" using awareness nearby list + distance.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] NPC with low HP and adjacent enemy uses Disengage → moves away without OA
- [ ] NPC with low HP and no adjacent enemies still uses FLEE directly
- [ ] High HP NPC behavior unchanged

## Status

`done`

## Developer Notes

- Restructured `_choose_combat_action` flee/dodge priority: now checks flee-without-enemies first, then disengage (covers both flee and dodge HP ranges when enemies in reach), then flee fallback (no action budget).
- Added `_move_away_from` static method using `calculate_away_direction` for retreat phase 2.
- Step 0 (top of combat logic): if `creature.is_disengaging` and has movement → move away from nearest hostile.
- 3 old tests updated (intentional contract change): `test_flee_when_critically_wounded` → `test_disengage_when_critically_wounded_enemy_in_reach`, `test_dodge_when_badly_hurt_and_in_reach` → `test_disengage_when_badly_hurt_and_in_reach`, `test_scared_npc_flees_earlier` → `test_scared_npc_disengages_when_enemy_in_reach`. All reflect the new tactical behavior: NPCs disengage instead of fleeing into OA or dodging in place.
