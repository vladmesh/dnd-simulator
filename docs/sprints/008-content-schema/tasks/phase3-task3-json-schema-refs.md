# Task: JSON Schema + Layer-Refs Endpoints

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 3 — Entity CRUD API + JSON Schema

## Description

Two lightweight endpoints that complete the content editing API:

1. **JSON Schema endpoint** — returns the Pydantic-generated JSON Schema for any entity type. The frontend uses this to render forms dynamically — no hardcoded field lists on the client.

2. **Layer-refs endpoint** — returns ID+name pairs from a world's layers for cross-layer reference dropdowns. When creating an NPC, the frontend needs a list of locations (from geography) and settlements (from settlements layer). This endpoint provides that data.

### URL structure

```
GET /api/master/schemas/{entity_type}                              → JSON Schema
GET /api/master/worlds/{world_id}/refs/{ref_type}                  → cross-layer refs
GET /api/master/schemas                                            → list all available entity types
```

`ref_type` maps to a specific query: `locations` → geography locations, `regions` → geography regions, `settlements` → settlements layer, `nations` → politics nations, `factions` → unique faction values across entities. These are the fields that appear as foreign keys / dropdowns in other entity forms.

### JSON Schema specifics

Pydantic's `.model_json_schema()` already includes enum values as `enum` constraints, default values, field types, and descriptions. The endpoint just serves this with the right content type. But we need to enrich it:

- Add `x-ref-type` extension to fields that reference other entities (e.g., `start_location` on NPC gets `x-ref-type: locations`). This tells the frontend to render a dropdown and where to fetch options.
- Ensure `LocalizedText` serializes as `object` with a clear description, not the raw Annotated type.

### Key files

- **Modified:** `src/dnd_simulator/adapters/api/routes_content.py` — add schema + refs endpoints
- **Modified:** `src/dnd_simulator/content_loader/crud.py` — add schema generation helpers, ref-type metadata on registry
- **Modified:** `src/dnd_simulator/service/game_service.py` — add refs query method

## Tests First

**Unit tests** in `tests/unit/test_content_schema.py`:

1. **Schema for NPC contains all fields** — `get_entity_schema("npc")` returns a JSON Schema dict with properties for `name`, `race`, `class`, `role`, `start_location`, `hp`, `ac`, etc. Every field from `NpcContent` is present.

2. **Enum values in schema** — `race` property in NPC schema has `enum` with all `Race` values. `role` has all `NpcRole` values. No hardcoded strings — the enum constraint comes from the Pydantic model.

3. **Defaults in schema** — `hp` has `default: 4`, `ac` has `default: 10`, `ai` has `default: "rule_based"` — matching `NpcContent` field defaults.

4. **Cross-ref annotation** — `start_location` field in NPC schema has `x-ref-type: locations`. `settlement_id` has `x-ref-type: settlements`. `faction` has `x-ref-type: factions`.

5. **Schema list** — `list_entity_schemas()` returns all entity type names with their human-readable labels.

**Integration tests** in `tests/integration/test_content_api.py` (extend from task 2):

6. **Refs endpoint returns locations** — create a world with geography, GET `/refs/locations` returns location IDs with localized names.

7. **Refs endpoint returns settlements** — same pattern for settlements.

8. **Schema endpoint serves valid JSON Schema** — GET `/schemas/npc` returns JSON parseable as a JSON Schema with `type: object`, `properties`, and `required`.

## Implementation

1. Add `get_entity_schema(entity_type)` to `crud.py` — looks up registry, calls `schema.model_json_schema()`, enriches with `x-ref-type` annotations based on registry metadata.

2. Add ref-type metadata to `EntityRegistry` entries — a dict mapping field names to ref types (e.g., `{"start_location": "locations", "settlement_id": "settlements", "faction": "factions"}`).

3. Add `list_refs(world_id, ref_type)` to `game_service.py` — resolves which layer/section to query, reads entities, returns `[{"id": "...", "name": "..."}]` pairs. Uses content CRUD `list_entities` from task 1 + `resolve_text` for localized names.

4. Add endpoints to `routes_content.py`:
   - `GET /schemas` — list entity types
   - `GET /schemas/{entity_type}` — JSON Schema for one type
   - `GET /worlds/{world_id}/refs/{ref_type}` — cross-layer reference data

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] JSON Schema includes all enum values as constraints (not strings)
- [ ] JSON Schema includes default values from Pydantic models
- [ ] `x-ref-type` annotations present on cross-reference fields
- [ ] Refs endpoint returns ID+name pairs for locations, regions, settlements, nations, factions
- [ ] Schema endpoint returns valid JSON Schema (parseable by any JSON Schema library)

## Status

`pending`
