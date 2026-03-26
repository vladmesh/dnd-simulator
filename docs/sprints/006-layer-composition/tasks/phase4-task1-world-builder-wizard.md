# Task: World Builder Wizard Component

**Date:** 2026-03-26
**Sprint:** 006-layer-composition
**Phase:** 4 — World Assembly Frontend

## Description

Build a `WorldBuilder` wizard component that guides the user through assembling a world from library templates. The wizard flows through 5 layer selection steps (geography, politics, settlements, ecology, entities) plus a final "name your world" step, then calls the assemble API and creates a session.

Each step fetches available templates for that layer type from `GET /api/master/library/{layer_type}`. Steps 2-5 pass the selected geography as `?geography=X` for compatibility filtering. The user picks one template per step. The final step collects world id, name, description, then POSTs to `/api/master/worlds/assemble` followed by `/api/master/sessions`.

Also add the required API client methods and TypeScript types for library templates and world assembly.

## Tests First

This phase uses integration tests (backend + frontend running in docker compose) rather than unit tests, since the frontend has no test runner set up.

Integration test scenarios (added to `tests/integration/test_library_and_assembly.py`):

1. **Full assembly flow via API** — call library endpoints for each layer type in sequence (geography unfiltered, politics/settlements/ecology/entities filtered by selected geography), verify each returns templates. Then assemble a world, create a session from it, verify session starts. This mirrors what the UI will do.

2. **Compatibility cascade** — select geography "test_geo", request politics with `?geography=test_geo`, verify only compatible templates appear. Request with `?geography=nonexistent`, verify empty results.

These tests already partially exist from Phase 3. We add the cascade/sequence test to verify the multi-step flow the UI depends on.

## Implementation

### TypeScript types (`frontend/src/types/api.ts`)

Add:
- `TemplateListItem` — `{ slug, name, layer_type, version, description, tags, requires_geography }`
- `AssembleWorldRequest` — `{ id, name, description, layer_selections, default_player_faction }`

### API client methods (`frontend/src/transport/apiClient.ts`)

Add to `master` namespace:
- `getLibraryTemplates(layerType, geography?)` — `GET /api/master/library/{layerType}` with optional `?geography=`
- `assembleWorld(data)` — `POST /api/master/worlds/assemble`

### WorldBuilder component (`frontend/src/components/setup/WorldBuilder.tsx`)

Multi-step wizard with internal state:
- `step` enum: `geography | politics | settlements | ecology | entities | details | done`
- `selections` record: maps layer type to selected template slug
- `worldMeta`: id, name, description

Each layer step:
- Fetches templates on mount (geography: unfiltered; others: filtered by `selections.geography`)
- Displays template cards with name, description, tags
- Clicking a template selects it and advances to the next step

Details step:
- Text inputs for world id (slug), name, description
- "Create World" button calls `assembleWorld()` then `createSession()`, returns session_id via `onWorldAssembled(sessionId)` callback

Navigation: back button to go to previous step. No skip — all 5 layers required.

### i18n strings

Add keys to `setup.json` (en + ru) for the wizard: step labels, button text, field labels, error messages.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `TemplateListItem` and `AssembleWorldRequest` types added
- [ ] API client has `getLibraryTemplates()` and `assembleWorld()` methods
- [ ] WorldBuilder wizard renders 5 layer steps + details step
- [ ] Each step fetches and displays templates from the library API
- [ ] Steps 2-5 filter by selected geography
- [ ] Back navigation works between steps
- [ ] Final step assembles world and creates session

## Status

`done`

## Developer Notes

Implementation straightforward, no surprises. Also fixed two pre-existing TS build errors: unused `Awareness` import in ActionBar.tsx and missing `conditions` field in `PatchCreatureRequest` type. Added 2 new integration tests (wizard flow sequence + compatibility cascade for all upper layers). Frontend builds clean — the WorldBuilder wizard handles the full 6-step flow (5 layers + details), with compatibility filtering on steps 2-5. The `DetailsForm` sanitizes world ID input to match the backend's `^[a-z0-9_]+$` pattern.
