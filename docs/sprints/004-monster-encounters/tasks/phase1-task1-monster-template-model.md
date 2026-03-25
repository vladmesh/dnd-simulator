# Task: MonsterTemplate + EncounterTable Models & YAML Loading

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 1 — Spawn Foundation

## Description

Create `MonsterTemplate` frozen dataclass — the blueprint for spawning monster Creatures. Create `EncounterTable` model — maps locations to possible encounters (template refs, chance, count range). Add a `monsters.yaml` file to the directory-format world loader. No runtime behavior yet — just data models and parsing.

MonsterTemplate lives in `core/monster.py`. It stores: name (i18n), hp, ac, speed, ability scores, attacks, CR. It does NOT extend Entity/Creature — it's a template used to instantiate Creatures at spawn time.

EncounterTable lives alongside MonsterTemplate. Structure: location_id → list of EncounterEntry (template_id, chance 0.0–1.0, count_min, count_max). A location can have multiple entries (e.g. 30% goblins, 10% wolves).

YAML format (`monsters.yaml` in world directory):

```yaml
templates:
  goblin:
    name: {en: Goblin, ru: Гоблин}
    hp: 7
    ac: 15
    speed: 30
    ability_scores: {str: 8, dex: 14, con: 10, int: 10, wis: 8, cha: 8}
    attacks:
      - name: scimitar
        ability: dex
        damage:
          - dice: "1d6"
            type: slashing
    cr: 0.25

encounters:
  dark_forest_path:
    - template: goblin
      chance: 0.3
      count: [1, 3]
```

Content loader: add `parse_monsters(data, lang)` to parse templates, `parse_encounters(data, known_templates)` to parse encounter tables. Wire into directory-format loader (`_load_dir`). Store on World or pass to EntitiesLayer during construction.

## Tests First

1. Parse a well-formed monster template YAML → MonsterTemplate with correct hp, ac, speed, attacks, ability_scores, CR, i18n name.
2. Parse encounter table → EncounterEntry list with correct template ref, chance, count range.
3. A monster template with attacks produces valid Attack objects (same format as NPC attacks).
4. Full directory-format world load with `monsters.yaml` present → templates and encounters accessible.
5. Missing `monsters.yaml` → empty templates/encounters (not an error — worlds without monsters are valid).

## Implementation

- `src/dnd_simulator/core/monster.py` — MonsterTemplate, EncounterEntry, EncounterTable frozen dataclasses
- `src/dnd_simulator/content_loader.py` — `parse_monster_template()`, `parse_encounters()`, wire into `_load_dir()`
- Storage: templates + encounters on World (new fields) or returned separately and injected into EntitiesLayer
- Reuse existing `parse_attacks()` logic from NPC parsing for monster attacks
- `content/worlds/sword_vale/monsters.yaml` — 2-3 test templates (goblin, wolf) + 1 encounter table entry for an existing dangerous location

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] MonsterTemplate is a frozen dataclass with all D&D-relevant fields
- [ ] EncounterTable correctly maps location_id → entries
- [ ] YAML parsing handles i18n names via `resolve_text()`
- [ ] Worlds without `monsters.yaml` load without error

## Status

`done`

## Developer Notes

Straightforward implementation. MonsterTemplate in `core/monster.py` with Attack reuse from existing `parse_attacks()`. EncounterEntry alongside it. Content loader gets `parse_monster_template()`, `parse_encounters()`, and `load_monsters()`. Sword Vale gets 3 templates (goblin, wolf, bandit) and 2 encounter locations (deep forest, mountain pass). Not yet wired into GameService/EntitiesLayer — that happens in task 2 when the spawn engine needs them.
