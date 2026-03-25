# Task: Factions — faction_id + Faction Relations

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters (living world pivot)
**Phase:** 1 — Data Foundation

## Description

Add `faction_id` to Creature and MonsterTemplate. Add a faction relations system to PoliticsLayer: `get_faction_relation(a, b) → HOSTILE | NEUTRAL | FRIENDLY`. Load faction definitions and relations from `factions.yaml`.

Factions are NOT nations. Nations are political entities (Silverhold). Factions are broader allegiance groups: `kingdom`, `bandits`, `wildlife`, `goblin_tribe`, `orc_warband`. Some factions align with nations (kingdom guards serve Silverhold), but others are independent. Nation-to-nation `DiplomaticStatus` (WAR, PEACE, etc.) stays separate — it drives politics mechanics. Faction relations drive creature-level hostility.

**Faction relation semantics:**
- HOSTILE: attack on sight (when active), abstract combat (when squads)
- NEUTRAL: ignore each other
- FRIENDLY: allies (shared targets in combat, sneak attack adjacency)

Default relation (not specified in YAML) = NEUTRAL.

**YAML format** (`factions.yaml` in world directory):
```yaml
kingdom:
  name: {en: Kingdom Forces, ru: Силы Королевства}
  relations:
    bandits: hostile
    goblin_tribe: hostile
    wildlife: neutral
bandits:
  name: {en: Bandits, ru: Бандиты}
  relations:
    kingdom: hostile
    wildlife: neutral
wildlife:
  name: {en: Wildlife, ru: Дикие звери}
goblin_tribe:
  name: {en: Goblin Tribe, ru: Племя гоблинов}
  relations:
    kingdom: hostile
```

**Content changes:**
- NPCs in `npcs.yaml` get `faction: kingdom` (guards, smiths, etc.)
- Monster templates in `monsters.yaml` get `faction: wildlife` or `faction: goblin_tribe`
- Settlement NPCs without explicit faction get auto-assigned based on their settlement's nation → faction mapping (a `nation_factions:` section in factions.yaml, e.g. `silverhold: kingdom`)

## Tests First

1. Two creatures with faction_id `kingdom` and `bandits`, faction relation is HOSTILE → `get_faction_relation("kingdom", "bandits")` returns HOSTILE.
2. Two creatures from the same faction → relation is FRIENDLY.
3. Unspecified relation pair → defaults to NEUTRAL.
4. Faction relation is symmetric: `get_faction_relation("bandits", "kingdom")` == `get_faction_relation("kingdom", "bandits")`.
5. Parse `factions.yaml` → PoliticsLayer has correct faction relations loaded.
6. Parse NPC with `faction: kingdom` from YAML → creature has `faction_id = "kingdom"`.
7. Parse MonsterTemplate with `faction: wildlife` → template has `faction_id = "wildlife"`.
8. MonsterTemplate.spawn() propagates faction_id to the spawned Creature.
9. World without `factions.yaml` → empty faction relations, no crash.

## Implementation

- `core/character.py` — add `faction_id: str = ""` to Creature (inherited by Character, Npc, PlayerCharacter)
- `core/monster.py` — add `faction_id: str = ""` to MonsterTemplate; `spawn()` copies it to Creature
- `layers/politics/models.py` — add `FactionRelation` enum (HOSTILE, NEUTRAL, FRIENDLY)
- `layers/politics/layer.py` — add `_faction_relations: dict[tuple[str, str], FactionRelation]`, `get_faction_relation()` method, new query type `FACTION_RELATION`
- `content_loader.py` — `load_factions()` function, parse `faction:` field in NPC and monster YAML
- `content/worlds/sword_vale/factions.yaml` — faction definitions for Sword Vale
- Update `npcs.yaml` and `monsters.yaml` with faction fields

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Faction relations queryable on PoliticsLayer
- [ ] faction_id on Creature and MonsterTemplate, parsed from YAML
- [ ] Spawn propagates faction_id from template to creature
- [ ] Default relation = NEUTRAL for unspecified pairs

## Status

`pending`
