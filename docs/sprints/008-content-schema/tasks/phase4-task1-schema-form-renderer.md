# Task: Schema-Driven Form Renderer

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 4 — Frontend — Schema-Driven Forms + DM Restructure

## Description

Build a generic `SchemaForm` React component that takes a JSON Schema (from `/api/master/schemas/{entity_type}`) and renders a form with appropriate inputs for each field. This is the foundation for all entity editing UI.

The component must handle:

- **Primitives:** `string` → Input, `integer`/`number` → Input[type=number], `boolean` → checkbox
- **Enums:** `string` with `enum` array → Select dropdown with enum values
- **Nested objects:** `object` type → fieldset/section with recursively rendered fields
- **Arrays of objects:** `array` with `items: {type: object}` → repeatable sub-form (add/remove rows). Used for attacks, items, damage entries, etc.
- **Arrays of strings:** `array` with `items: {type: string}` → tag-like input or comma-separated
- **Cross-layer refs:** fields with `x-ref-type` annotation → Select dropdown, options fetched from `/api/master/worlds/{worldId}/refs/{refType}`
- **LocalizedText:** `object` with string values → single text input for current language (key = lang code)
- **Required vs optional:** required fields marked, optional fields can be left blank
- **Defaults:** pre-fill from `default` in schema

Also in this task:

- Add API client methods: `getSchemas()`, `getSchema(entityType)`, `getRefs(worldId, refType)`, entity CRUD (`listEntities`, `getEntity`, `createEntity`, `updateEntity`, `deleteEntity`), catalog CRUD (`listCatalog`, `getCatalogEntry`, etc.)
- Add TypeScript types for schema/refs/CRUD response shapes in `types/api.ts`

## Tests First

- **Unit tests** (vitest/react-testing-library): render `SchemaForm` with a mock JSON Schema containing string, number, enum, nested object, array, and x-ref-type fields. Verify correct input types are rendered, enum shows Select with options, ref field fetches and shows options.
- **Form submission:** fill fields → onSubmit callback receives correctly shaped data dict matching the schema structure.
- **Array fields:** add row → new sub-form appears, remove row → sub-form disappears, submitted data has correct array.
- **LocalizedText:** schema has `{"type": "object", "x-localized": true}` or detected by convention → renders as single text input, submits as `{"en": "value"}`.

## Implementation

1. `frontend/src/components/master/SchemaForm.tsx` — the generic form renderer. Uses react-hook-form for state management. Recursive rendering for nested objects. `useFieldArray` for arrays.
2. `frontend/src/components/master/RefSelect.tsx` — wrapper around Select that fetches ref options from API. Takes `worldId` + `refType`, caches results.
3. `frontend/src/transport/apiClient.ts` — add `api.master.getSchemas()`, `api.master.getSchema(type)`, `api.master.getRefs(worldId, refType)`, `api.master.listEntities(worldId, entityType)`, `api.master.getEntity(...)`, `api.master.createEntity(...)`, `api.master.updateEntity(...)`, `api.master.deleteEntity(...)`, `api.master.listCatalog(catalogType)`, `api.master.getCatalogEntry(...)`.
4. `frontend/src/types/api.ts` — types: `SchemaInfo`, `EntityEntry`, `RefOption`, `CatalogEntry`.

## Integration Tests

Run `make test-integration` after implementation. Add new integration tests if the existing `test_content_api.py` doesn't cover scenarios the frontend relies on (e.g. schema shape assumptions, refs response format). Verify no regressions.

## Acceptance Criteria

- [ ] Unit tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] `SchemaForm` renders correct input types for all JSON Schema field types
- [ ] Cross-layer ref fields show dropdown with options from refs API
- [ ] Array fields support add/remove with correct data shape
- [ ] API client has all CRUD + schema + refs methods typed
- [ ] `make test-integration` passes, new integration tests added if needed
- [ ] Existing tests still pass (`make check`)

## Status

`pending`
