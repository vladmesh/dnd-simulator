# Task: Entity CRUD API Endpoints

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 3 — Entity CRUD API + JSON Schema

## Description

REST API endpoints for entity-level CRUD — both world layer entities and catalog entries. New router `routes_content.py` to keep routes_master.py from growing further. Service-layer methods wrap the content_loader CRUD from task 1.

### URL structure

**World layer entities** (NPC, region, location, nation, settlement, squad, monster_template):
```
GET    /api/master/worlds/{world_id}/entities/{entity_type}              → list
GET    /api/master/worlds/{world_id}/entities/{entity_type}/{entity_id}  → get
POST   /api/master/worlds/{world_id}/entities/{entity_type}/{entity_id}  → create
PUT    /api/master/worlds/{world_id}/entities/{entity_type}/{entity_id}  → update
DELETE /api/master/worlds/{world_id}/entities/{entity_type}/{entity_id}  → delete
```

**Catalog entries** (monster_catalog, item_catalog):
```
GET    /api/master/catalogs/{catalog_type}              → list
GET    /api/master/catalogs/{catalog_type}/{entry_id}   → get
POST   /api/master/catalogs/{catalog_type}/{entry_id}   → create
PUT    /api/master/catalogs/{catalog_type}/{entry_id}   → update
DELETE /api/master/catalogs/{catalog_type}/{entry_id}   → delete
```

`entity_type` and `catalog_type` are path params validated against `EntityType` enum.

### Key constraints

- **Library layers are read-only.** Creating/updating/deleting entities in a library layer returns 400 with "fork layer first" message. Listing and getting are fine.
- **Custom layers allow full CRUD.** The service resolves manifest → checks if layer is custom → proceeds or rejects.
- **Catalogs are always writable** (they live outside world directories).
- **Request body is raw entity JSON** matching the Pydantic content model (e.g., `NpcContent` fields). No wrapper — the body IS the entity.
- **Response body** for get/create/update: `{"id": "...", "data": {...}}` where data is the validated model dict.

### Key files

- **New:** `src/dnd_simulator/adapters/api/routes_content.py` — new router
- **Modified:** `src/dnd_simulator/adapters/api/app.py` — include new router
- **Modified:** `src/dnd_simulator/service/game_service.py` — add content CRUD methods
- **New:** `src/dnd_simulator/adapters/api/schemas.py` — add request/response models for entity CRUD

## Tests First

**Integration tests** in `tests/integration/test_content_api.py` (docker compose stack):

1. **Create NPC via API, read it back** — POST an NPC to a custom world's entities layer, GET it back, confirm fields match. Then start a session from that world and confirm the NPC appears in the game.

2. **List entities** — create 2 NPCs via API, GET list, confirm both present with correct IDs and data.

3. **Update entity** — create NPC, PUT with changed HP, GET confirms new HP. Other fields unchanged.

4. **Delete entity** — create NPC, DELETE, GET returns 404. Other entities in the same layer unaffected.

5. **Library layer rejects writes** — POST/PUT/DELETE on a library-backed layer returns 400.

6. **Catalog CRUD round-trip** — POST a new monster to catalog, GET it, PUT to update, DELETE to remove.

7. **Validation error** — POST NPC with invalid `race` value → 422 with validation details.

8. **404 on missing** — GET nonexistent entity → 404. GET from nonexistent world → 404.

## Implementation

1. Add service methods to `game_service.py`:
   - `list_entities(world_id, entity_type)` — resolve manifest, find layer path, call CRUD
   - `get_entity(world_id, entity_type, entity_id)` — same + single entity
   - `create_entity(world_id, entity_type, entity_id, data)` — check custom layer, call CRUD
   - `update_entity(world_id, entity_type, entity_id, data)` — check custom layer, call CRUD
   - `delete_entity(world_id, entity_type, entity_id)` — check custom layer, call CRUD
   - Same pattern for catalog methods (no custom-layer check needed)

2. Create `routes_content.py` with both entity and catalog endpoint groups. Register in `app.py`.

3. Response model: `EntityResponse(id=str, data=dict)` for single, `list[EntityResponse]` for list. Keep it generic — the schema endpoint (task 3) tells the frontend what fields exist.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] All 5 CRUD operations work for world entities
- [ ] All 5 CRUD operations work for catalog entries
- [ ] Library layers reject writes with clear error message
- [ ] Validation errors return 422 with Pydantic details
- [ ] Creating NPC via API → starting session → NPC visible in game

## Status

`pending`
