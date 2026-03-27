# Task: Entity CRUD UI + Catalog Browser

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 4 — Frontend — Schema-Driven Forms + DM Restructure

## Description

Replace the YAML textarea (`LayerEditor`) with structured entity editing. Build two components:

**EntityListEditor** — the main editing interface for world layer entities:
- Takes `worldId` + `entityType` (e.g. "npc", "region", "squad")
- Fetches entity list from CRUD API, shows as a table (id, name, key fields)
- Click row → opens edit dialog with `SchemaForm` pre-filled with entity data
- "Add" button → opens create dialog with empty `SchemaForm`
- Delete button per row (with confirmation)
- Save → calls create/update API, refreshes list
- Read-only mode for library layers (no add/edit/delete buttons)

**CatalogBrowser** — browse global monster/item catalogs:
- Tab or section for monsters, tab for items
- Lists catalog entries in a table (id, name, key stats)
- Click → view detail in a read-only SchemaForm or formatted card
- No create/edit/delete for now (catalog editing deferred)

**Catalog Picker** (for ecology layer):
- When editing ecology layer, a "Pick from catalog" button next to monster_templates
- Opens CatalogBrowser in a dialog
- Select a monster → creates a monster_template entry with `base: {monster_id}` in the world
- No override form — just reference the catalog entry

**LayerEditor migration:**
- In `WorldInspector` / layer editing flow, replace YAML textarea with EntityListEditor for layers that have entity types
- Layer → entity type mapping: geography → region + location, politics → nation, settlements → settlement, entities → npc, ecology → squad + monster_template

## Tests First

- **EntityListEditor:** render with mock API responses → table shows entities. Click "Add" → SchemaForm dialog opens. Fill and submit → createEntity API called with correct data. Click entity → edit dialog with pre-filled data. Save → updateEntity called. Delete → deleteEntity called after confirmation.
- **CatalogBrowser:** render → fetches and shows catalog entries. Click entry → shows detail view.
- **Catalog Picker:** open picker in ecology context → select monster → createEntity called with `{base: "monster_id"}` payload.
- **Read-only mode:** library layer → no add/edit/delete buttons rendered.

## Implementation

1. `frontend/src/components/master/EntityListEditor.tsx` — table + CRUD dialogs using SchemaForm
2. `frontend/src/components/master/CatalogBrowser.tsx` — catalog list + detail view
3. `frontend/src/components/master/CatalogPicker.tsx` — dialog wrapper around CatalogBrowser for picking entries
4. Update `WorldInspector.tsx` (or wherever layer editing is triggered) — route to EntityListEditor instead of LayerEditor based on layer type
5. Keep `LayerEditor.tsx` around but it should no longer be the primary editing path

## Integration Tests

Run `make test-integration` after implementation. Add integration tests that exercise the entity CRUD flow end-to-end: create entity via API → verify it appears in list endpoint → update → verify changes → delete → verify gone. Test catalog list endpoint returns expected entries. Verify no regressions.

## Acceptance Criteria

- [x] Unit tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] EntityListEditor shows entity table, supports create/edit/delete via SchemaForm
- [x] CatalogBrowser lists monster and item catalogs
- [x] Catalog Picker adds monster_template with `base` reference to world
- [x] Library layers show read-only (no mutation buttons)
- [x] YAML textarea no longer the primary editor for entity-bearing layers
- [x] `make test-integration` passes, new integration tests added if needed
- [x] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Three new components: EntityListEditor (table + inline create/edit panel using SchemaForm), CatalogBrowser (table + detail view), CatalogPicker (thin wrapper with pick mode). WorldInspector now routes entity-bearing layers to EntityListEditor instead of LayerEditor, with a LAYER_ENTITY_TYPES mapping. Ecology layer gets a "Pick from catalog" button for monster_template entries.

Used inline expand/collapse panel instead of Dialog for the editor — base-ui Dialog portals don't render in jsdom, and inline editing is better UX for this embedded context anyway. SchemaForm label/input elements work correctly but testing-library's `getByLabelText` struggles with base-ui Input primitive; tests use direct DOM queries (`form.querySelectorAll`) instead.

Integration tests not modified — existing `test_content_api.py` already covers full entity CRUD lifecycle (create/read/update/delete) and catalog CRUD. 84 integration tests pass, 1407 unit tests pass, 31 frontend tests pass.
