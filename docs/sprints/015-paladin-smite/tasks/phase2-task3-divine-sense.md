# Task: Divine Sense Action

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 2 — Paladin Class Foundation

## Description

Divine Sense: as a bonus action, detect celestial/fiend/undead creatures within 60 feet. Uses: 1 + CHA modifier per long rest. Requires adding `CreatureType` to the entity model.

Key changes:
- `CreatureType` enum in `core/character.py` (HUMANOID, BEAST, CELESTIAL, FIEND, UNDEAD, DRAGON, CONSTRUCT, etc.)
- `creature_type: CreatureType` field on `Creature` (default HUMANOID)
- Content loader + catalog schema support for creature_type on monsters and NPCs
- Existing monster catalogs updated (goblin → HUMANOID, wolf → BEAST, bandit → HUMANOID, guard → HUMANOID)
- `ActionType.DIVINE_SENSE` + ActionDef (cost_type=BONUS_ACTION, provider_managed=True)
- `handle_divine_sense()` handler — returns list of (creature_id, creature_type) for matching types within 60 feet
- Resource pool: "divine_sense" with max_uses = 1 + CHA modifier, long rest reset
- Action provider: offer when pool > 0

D&D 5e simplification: we skip consecrated/desecrated ground detection, focus on creature type detection only.

## Tests First

Scenarios (unit tests):

1. **CreatureType on creature** — Creature with creature_type=UNDEAD. Creature with default → HUMANOID.
2. **Divine Sense detects undead** — Paladin at location with UNDEAD creature within 60ft. Divine Sense → returns that creature's id and type. Pool decrements by 1.
3. **Divine Sense ignores humanoids** — Location has only HUMANOID creatures → returns empty list. Pool still spent.
4. **Multiple types** — Location has FIEND + BEAST + HUMANOID. Divine Sense → returns only FIEND (celestial/fiend/undead are detected).
5. **Pool exhaustion** — CHA modifier +2 → 3 uses. Use 3 times → pool empty, action not offered.
6. **Action provider** — Paladin with divine_sense pool > 0 sees DIVINE_SENSE. Pool 0 → not shown.
7. **Content loader** — Monster catalog with `creature_type: beast` loads correctly. NPC without creature_type → defaults to HUMANOID.
8. **Resource pool creation** — Paladin with CHA 16 (+3) gets divine_sense pool with max_uses=4 (1+3).

## Implementation

After tests are red:

1. Add `CreatureType` StrEnum to `core/character.py`
2. Add `creature_type: CreatureType = CreatureType.HUMANOID` to Creature
3. Update content loader schemas (NpcContent, monster catalog) to accept optional creature_type
4. Update monster catalog YAML files with creature_type
5. Update `build_class_resource_pools()` — Paladin gets divine_sense pool (needs CHA modifier → accept ability_scores or cha_mod parameter)
6. Add `DIVINE_SENSE = "divine_sense"` to ActionType
7. Register ActionDef (BONUS_ACTION, provider_managed, no target)
8. Write `handle_divine_sense()` — find creatures at same location, filter by type, return results via event
9. Add to ClassFeatureActionProvider
10. Update serialization (get_state/load_state) for creature_type field

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] CreatureType field on all creatures, defaults to HUMANOID
- [ ] Monster catalogs have correct creature_type
- [ ] Divine Sense detects celestial/fiend/undead only
- [ ] Pool = 1 + CHA mod, resets on long rest
- [ ] Serialization round-trips creature_type correctly

## Status

`pending`
