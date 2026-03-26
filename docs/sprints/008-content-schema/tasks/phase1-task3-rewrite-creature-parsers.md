# Task: Rewrite Creature, Monster, and Item Parsers

**Date:** 2026-03-26
**Sprint:** 008-content-schema
**Phase:** 1 — Pydantic Content Models + Parser Rewrite

## Description

Rewrite parsers in `content_loader/creatures.py`, `content_loader/monsters.py`, and `content_loader/items.py` to use Pydantic content models. This is the largest rewrite — NPC parsing alone has ~60 lines of hand-written dict extraction.

Functions to rewrite:

**items.py:**
- `parse_items()` — ItemContent model with type-specific sub-models (weapon, armor, shield, accessory, potion)
- `extract_all_equipped()` — stays as-is (operates on runtime Item, not content model)
- `_parse_weapon_def`, `_parse_armor_def`, `_parse_shield_def`, `_parse_accessory_def` — absorbed into Pydantic model validators

**creatures.py:**
- `parse_npc()` — NpcContent model, largest conversion
- `parse_player()` — PlayerContent model
- `parse_attacks()` — AttackContent model (shared)
- `parse_ability_scores()` — AbilityScoresContent model (shared)
- `parse_class_features()` — stays procedural (logic depends on class, not just data)
- `build_class_resource_pools()` — stays procedural (derived from class, not YAML data)
- `load_npcs()` — thin wrapper, uses parse_npc

**monsters.py:**
- `parse_monster_template()` — MonsterTemplateContent model
- `parse_encounters()` — EncounterEntryContent model
- `load_monsters()` — thin wrapper
- `parse_squad()` — SquadContent model
- `load_squads()` — thin wrapper

Each rewritten function follows the same pattern as task 2: yaml dict → model_validate → convert to runtime dataclass.

## Tests First

Unit tests in `tests/unit/test_content_parsers_creatures.py`:

1. **Round-trip: NPC with full equipment.** Create NPC dict with weapon, armor, shield, items, attacks, ability scores, memory, class features → parse via NpcContent → convert to Npc → verify all fields. Compare with current parse_npc output for same input.
2. **Round-trip: NPC with minimal fields.** `{name: "Peasant"}` → defaults applied correctly (race=HUMAN, hp=4, ac=10, role=COMMONER, ai="rule_based").
3. **Round-trip: monster templates.** Load sword_vale monsters.yaml → MonsterTemplateContent for each → convert → fields match current load_monsters output.
4. **Round-trip: squads.** Same for squads.yaml.
5. **Round-trip: items.** Parse a weapon, armor, shield, potion, accessory → model_dump → re-validate → identical.
6. **Validation error on bad NPC data.** NPC with `race: "robot"` → ValidationError. NPC with `class: "jedi"` → ValidationError.
7. **Validation error on bad item type.** Item with `type: "spaceship"` → ValidationError.
8. **Player parse matches current behavior.** Parse player dict through PlayerContent → convert → same result as current parse_player.
9. **sword_vale full load.** `GameService.start_game("sword_vale")` → session works, NPCs present with correct stats/equipment/attacks. This is the final integration gate — everything goes through the new parsers.

## Implementation

1. Rewrite `items.py`: replace `_parse_weapon_def` etc. with WeaponDefContent/ArmorDefContent Pydantic models. `parse_items()` uses `ItemContent.model_validate()`. Keep `extract_all_equipped` unchanged.
2. Rewrite `creatures.py`: `parse_npc()` uses `NpcContent.model_validate()` + `_to_npc()` converter. `parse_player()` uses `PlayerContent.model_validate()` + `_to_player()`. Keep `parse_class_features` and `build_class_resource_pools` as procedural helpers (they contain logic, not just data mapping).
3. Rewrite `monsters.py`: `parse_monster_template()` uses `MonsterTemplateContent.model_validate()`, `parse_squad()` uses `SquadContent.model_validate()`.
4. Run `make check` — all 1240+ tests must pass.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] No hand-written dict extraction remains in creatures.py, monsters.py, items.py parse functions
- [ ] Bad content data produces clear Pydantic ValidationError
- [ ] sword_vale loads identically (NPCs, monsters, items all correct)
- [ ] JSON Schema for NpcContent/ItemContent/MonsterTemplateContent contains all enum values

## Status

`done`

## Developer Notes

All three parser files rewritten to use Pydantic content models:

- **items.py**: `_parse_weapon_def`, `_parse_armor_def`, `_parse_shield_def`, `_parse_accessory_def` replaced by
  `_to_weapon_def`, `_to_armor_def`, `_to_shield_def`, `_to_accessory_def` that take validated `ItemContent`.
  `parse_items` now does `ItemContent.model_validate(idata)` → `_to_item(model, i)`. `extract_all_equipped` unchanged.
- **creatures.py**: `parse_npc` does `NpcContent.model_validate` → `_to_npc`. `parse_player` does `PlayerContent.model_validate`
  → `_to_player`. Added `lang` parameter to `parse_player` (was missing — name was never resolved). `parse_class_features`
  and `build_class_resource_pools` stay procedural as planned. `parse_attacks` and `parse_ability_scores` kept as
  backward-compatible wrappers using Pydantic models internally.
- **monsters.py**: `parse_monster_template` does `MonsterTemplateContent.model_validate` → `_to_monster_template`.
  `parse_squad` does `SquadContent.model_validate` → `_to_squad`. `parse_encounters` validates each entry via
  `EncounterEntryContent.model_validate`.
- **schemas.py changes**: Added `LocalizedText` coercing validator (accepts plain string or dict). Added `modifiers`
  field to `ItemContent` (was missing — accessory modifiers weren't being parsed). Added `id`, `current_hp`, `speed`
  to `PlayerContent`.
- **Adapter fix**: `routes_player.py` and `routes_master.py` now use `model_dump(exclude_none=True)` — API schema
  sends `None` for optional fields, Pydantic content models correctly reject explicit `None` for fields with defaults.
  This is the clean fix: transport layer strips None, domain layer validates strictly.
