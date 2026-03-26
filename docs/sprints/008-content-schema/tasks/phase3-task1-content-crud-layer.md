# Task: Content CRUD Layer

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 3 — Entity CRUD API + JSON Schema

## Description

Generic CRUD operations for content entities — both world-layer entities (regions, locations, nations, settlements, NPCs, squads, monster templates) and catalog entries (monsters, items). All operations validate through Pydantic content models from Phase 1.

Two distinct storage patterns:

1. **Layer entities** — multiple entities in one YAML file, keyed by ID (e.g., `npcs.yaml` has `edgar: {...}, marta: {...}`). CRUD = read dict → modify → write back.
2. **Catalog entries** — one YAML file per entry (e.g., `catalogs/monsters/goblin.yaml`). CRUD = file-level create/read/update/delete.

Central piece: `EntityRegistry` — maps an `EntityType` enum to `(layer_type, yaml_section, pydantic_model)` for layer entities, and `(catalog_dir, pydantic_model)` for catalog entries. This registry is the single source of truth for "what entity types exist and where they live."

### Key files

- **New:** `src/dnd_simulator/content_loader/crud.py` — EntityRegistry + generic CRUD functions
- **Modified:** `src/dnd_simulator/content_loader/catalogs.py` — add write/delete helpers alongside existing `load_catalog`
- **Modified:** `src/dnd_simulator/content_loader/utils.py` — add `_write_yaml` helper

## Tests First

**Unit tests** in `tests/unit/test_content_crud.py`:

1. **Layer entity round-trip** — create an NPC in a temp world's `npcs.yaml` via `create_entity()`, then `get_entity()` returns it validated. The returned data matches what was written, including localized text fields.

2. **Layer entity list** — populate `npcs.yaml` with 3 NPCs, `list_entities("npc", world_path)` returns all 3 with correct IDs and validated data.

3. **Layer entity update** — create an NPC, then `update_entity()` changes its HP and personality. Re-read confirms the change. Other NPCs in the same file are untouched.

4. **Layer entity delete** — create 2 NPCs, delete one, confirm the file still has the other and the deleted one is gone.

5. **Duplicate ID on create raises** — creating an entity with an ID that already exists in the YAML raises `ValueError`.

6. **Validation on create/update** — passing invalid data (e.g., `race: "not_a_race"` for NPC) raises `ValidationError` and the file is NOT modified (no partial writes).

7. **Catalog entry round-trip** — create a monster in `catalogs/monsters/` via `create_catalog_entry()`, then `get_catalog_entry()` returns it validated.

8. **Catalog entry update + delete** — update a catalog entry's fields, re-read confirms. Delete removes the file.

9. **EntityRegistry coverage** — every `EntityType` enum value resolves to a valid registry entry with a real Pydantic model and correct layer/section mapping.

## Implementation

1. Add `_write_yaml(path, data)` to `utils.py` — dumps dict to YAML with `yaml.safe_dump(..., allow_unicode=True, sort_keys=False)`.

2. Create `crud.py` with:
   - `EntityType` enum: `REGION`, `LOCATION`, `NATION`, `SETTLEMENT`, `NPC`, `SQUAD`, `MONSTER_TEMPLATE`, `MONSTER_CATALOG`, `ITEM_CATALOG` (layer entities + catalog entries in one enum, distinguished by registry metadata).
   - `EntityRegistry` — frozen dataclass or dict mapping `EntityType` to `RegistryEntry(layer_type, section, schema)` for layer entities and `RegistryEntry(catalog_dir, schema)` for catalogs.
   - Generic CRUD functions for layer entities:
     - `list_entities(entity_type, world_path) → dict[str, T]`
     - `get_entity(entity_type, entity_id, world_path) → T`
     - `create_entity(entity_type, entity_id, data, world_path) → T`
     - `update_entity(entity_type, entity_id, data, world_path) → T`
     - `delete_entity(entity_type, entity_id, world_path) → None`
   - Generic CRUD for catalogs:
     - `list_catalog_entries(entity_type, content_root) → dict[str, T]`
     - `get_catalog_entry(entity_type, entry_id, content_root) → T`
     - `create_catalog_entry(entity_type, entry_id, data, content_root) → T`
     - `update_catalog_entry(entity_type, entry_id, data, content_root) → T`
     - `delete_catalog_entry(entity_type, entry_id, content_root) → None`

3. All write operations: validate via `schema.model_validate(data)` BEFORE touching the file. On validation failure, raise — no partial writes.

4. For layer entities, `world_path` points to the resolved layer directory (library or custom). CRUD writes are only allowed on custom layers — the functions should accept the path and the caller (service layer) enforces the library-vs-custom check.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `EntityType` enum covers all 9 entity types (7 layer + 2 catalog)
- [ ] `EntityRegistry` maps every type to correct layer/section/model
- [ ] All write operations validate before writing — invalid data never hits disk
- [ ] YAML files preserve existing entries on create/update/delete of other entries

## Status

`done`

## Developer Notes

Implementation was straightforward. Key decisions:

- Used `model_dump(mode="json", by_alias=True)` for serialization — `mode="python"` produces enum objects that `yaml.safe_dump` can't handle, while `mode="json"` gives plain strings.
- `RegistryEntry` has a `subsection` field for the monsters.yaml `templates` key — keeps the CRUD generic without special-casing.
- `_write_yaml` added to utils.py as specified. Uses `sort_keys=False` to preserve YAML key order.
- No changes to existing code beyond adding `_write_yaml` to utils.py. All existing tests pass unchanged.
