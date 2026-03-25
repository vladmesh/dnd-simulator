# Task: Faction-Aware Hostile AI

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 2 — Generalize Encounters + Hostile AI

## Description

RuleBrain becomes faction-aware. In peaceful mode, if a hostile creature is nearby, the brain initiates an attack — triggering combat. In combat mode, faction hostility boosts target scoring.

Two parts:

**1. Enrich awareness with hostility info.** `NearbyEntity` gets an `is_hostile: bool` field. The awareness builder in `EntitiesLayer.build_peaceful_awareness` / `build_nearby_entities` queries `PoliticsLayer.get_faction_relation(a, b)` via `query_fn` to determine hostility between the creature and each neighbor. Two creatures with the same `faction_id` → friendly. Different factions → look up relation. No faction → neutral.

**2. RuleBrain hostile response.** In `_peaceful_action`: if any nearby entity is hostile, return ATTACK targeting the nearest hostile. This naturally triggers combat via the existing attack resolution path. In `_pick_target` (combat): add a faction hostility score bonus (similar to `hated_ids` but from faction data — pass hostile IDs into scoring).

## Tests First

Scenarios:

1. **Orc guard meets kingdom soldier in peaceful mode → attacks.** Two creatures from hostile factions at the same location. RuleBrain returns ATTACK action targeting the enemy.
2. **Two kingdom guards meet → no attack.** Same faction, peaceful coexistence. RuleBrain returns END_TURN.
3. **Neutral factions meet → no attack.** Creature from faction A and creature from faction B with NEUTRAL relation. No attack.
4. **Hostile creature prioritized in combat target scoring.** In combat with mixed enemies (some hostile-faction, some neutral-dragged-in), hostile-faction targets score higher.
5. **Creature without faction_id is neutral to everyone.** A creature with `faction_id=None` doesn't trigger hostility and isn't targeted preferentially.
6. **NearbyEntity.is_hostile is correctly set by awareness builder.** Build awareness for a creature at a location with hostile and friendly neighbors — verify flags.

## Implementation

- Add `is_hostile: bool = False` to `NearbyEntity` dataclass
- In `build_nearby_entities`: accept `query_fn`, query faction relation for each pair, set `is_hostile`
- In `RuleBrain._peaceful_action`: check `awareness.nearby` for hostile entities, return ATTACK if found
- In `RuleBrain._choose_combat_action` / `_pick_target`: accept hostile faction IDs, add score bonus
- Thread `query_fn` through to awareness building (Round already has it)

## Acceptance Criteria

- [ ] Tests written and RED
- [ ] Implementation makes tests GREEN
- [ ] `make check` passes
- [ ] Hostile factions auto-attack on sight in peaceful mode
- [ ] Same/friendly factions coexist peacefully
- [ ] Combat target scoring prefers faction enemies

## Status

`pending`
