# Task: Pydantic Content Model Definitions

**Date:** 2026-03-26
**Sprint:** 008-content-schema
**Phase:** 1 — Pydantic Content Models + Parser Rewrite

## Description

Create `content_loader/schemas.py` with Pydantic BaseModel classes for every content entity type. These models represent the YAML structure (not runtime state) — they are the single source of truth for field names, types, defaults, enums, and validation.

Models to define (grouped by future layer usage):

**Shared/nested:**
- `DamageComponentContent` (dice, type)
- `AttackContent` (name, ability, damage, reach, is_finesse)
- `AbilityScoresContent` (str, dex, con, int, wis, cha — all default 10)
- `ItemContent` (name, type, equipped, + type-specific sub-models)
- `WeaponDefContent`, `ArmorDefContent`, `ShieldDefContent`, `AccessoryDefContent`
- `NpcMemoryContent` (tags, recent, inner_state, current_conversation)

**Geography:**
- `ConnectionContent` (target, direction)
- `RegionContent` (name, terrain, latitude, longitude, elevation, water_proximity, connections, battle_map)
- `NeighborContent` (target, distance)
- `LocationContent` (name, region, settlement, description, neighbors)

**Politics:**
- `LeaderContent` (name, age, trait)
- `NationContent` (name, regions, wealth, military, stability, leader)

**Settlements:**
- `SettlementContent` (name, region, type, population, prosperity, defenses)

**Ecology:**
- `MonsterTemplateContent` (name, hp, ac, speed, ability_scores, attacks, cr, faction)
- `EncounterEntryContent` (template, chance, count)
- `SquadContent` (name, faction, type, behavior, start_location, route, territory, strength, max_strength, members, tick_interval)

**Entities:**
- `NpcContent` (name, race, class, role, start_location, settlement_id, faction, personality, hp, ac, speed, gold, ai, attacks, items, ability_scores, class_features, memory)
- `PlayerContent` (name, race, class, level, alignment, appearance, start_location, faction, hp, ac, gold, attacks, items, ability_scores)

Key design decisions:
- Field names match YAML keys (use `alias` where Python name differs, e.g. `char_class` with `alias="class"`)
- Enums used directly as types — Pydantic includes them in JSON Schema automatically
- Defaults match current parser defaults exactly (hp=4 for NPC, hp=10 for player, etc.)
- `model_config = ConfigDict(populate_by_name=True)` to allow both alias and field name
- Cross-layer ref fields annotated with `json_schema_extra={"x-ref": "locations"}` for future frontend dropdowns

## Tests First

Unit tests in `tests/unit/test_content_schemas.py`:

1. **Each model constructs from minimal dict.** Provide only required fields, verify defaults fill in correctly. E.g. `NpcContent(name="Guard")` → race=HUMAN, hp=4, ai="rule_based".
2. **Each model constructs from full dict.** Provide all fields with non-default values, verify all preserved.
3. **Enum validation rejects bad values.** `RegionContent(terrain="lava")` → ValidationError. `NpcContent(race="alien")` → ValidationError.
4. **JSON Schema contains enum values.** `RegionContent.model_json_schema()` has `terrain.enum` containing all TerrainType values. `NpcContent.model_json_schema()` has `race.enum` containing all Race values.
5. **JSON Schema contains defaults.** NpcContent schema shows `hp` default is 4, `race` default is "human".
6. **Alias works for "class" field.** `NpcContent.model_validate({"name": "X", "class": "fighter"})` → char_class=FIGHTER. Also works with `char_class` directly.
7. **Nested models validate.** NpcContent with `attacks: [{name: "Bite", ability: "str", damage: [{dice: "1d6", type: "piercing"}]}]` constructs correctly with typed nested AttackContent/DamageComponentContent.
8. **model_dump round-trip.** For each top-level model: construct from dict → model_dump(by_alias=True) → model_validate again → fields identical.

## Implementation

1. Create `src/dnd_simulator/content_loader/schemas.py`.
2. Define all models bottom-up (shared first, then layer-specific).
3. Use existing StrEnum types directly (import from core/character.py, geography/models.py, etc.).
4. Add `model_config = ConfigDict(populate_by_name=True)` on models with aliases.
5. Export key models from `content_loader/__init__.py`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] All ~20 content models defined with correct field types and defaults
- [ ] JSON Schema for each model contains enum values and defaults
- [ ] `by_alias` dump produces YAML-compatible dict (keys match YAML structure)

## Status

`done`

## Developer Notes

Created `content_loader/schemas.py` with ~20 Pydantic BaseModel classes covering all content entity types:
- Shared: DamageComponentContent, AttackContent, AbilityScoresContent, NpcMemoryContent, ItemContent
- Geography: ConnectionContent, NeighborContent, RegionContent, LocationContent
- Politics: LeaderContent, NationContent
- Settlements: SettlementContent
- Ecology: MonsterTemplateContent, EncounterEntryContent, SquadContent
- Entities: NpcContent, PlayerContent
- Item sub-models: WeaponDefContent, ArmorDefContent, ShieldDefContent, AccessoryDefContent

Key decisions:
- AbilityScoresContent uses aliases for `str` and `int` (Python reserved words) with `populate_by_name=True`.
  A `CoercedAbilityScores` annotated type ensures raw dicts always coerce to AbilityScoresContent for round-trip stability.
- ItemContent is a flat model matching YAML layout (type-specific fields mixed in), not a discriminated union — matches how items are structured in YAML.
- SquadContent.max_strength defaults to strength via model_post_init.
- Added pydantic mypy plugin to pyproject.toml to handle alias resolution in strict mode.
- All existing enums (Race, CharClass, TerrainType, etc.) used directly as field types — Pydantic includes them in JSON Schema automatically.
