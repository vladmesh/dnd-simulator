# Task: Master Restructure + Main Page

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 4 — Frontend — Schema-Driven Forms + DM Restructure

## Description

Restructure the `/master` page and the main page (`/`) for a cleaner DM workflow.

**Master page — two tabs:**

1. **Worlds tab** — list all worlds (cards with name, description, complete status). Actions: create new world, delete world, open world editor. World editor: layer stepper — step through geography → politics → settlements → ecology → entities. Each step shows EntityListEditor for that layer's entity types. Ecology step also has CatalogPicker for adding monsters from catalog. Navigation: back/next between steps, skip steps. Shows layer source badge (library/custom) with fork button for library layers.

2. **Sessions tab** — existing session list + management (moved from current MasterScreen). Create session from world, manage/delete sessions. Link to SessionView for detailed controls.

**Main page (`/`) — Player/DM split:**

- Two cards/buttons: "Play" and "Dungeon Master"
- "Play" → current setup flow (pick world → create character → play)
- "Dungeon Master" → `/master`
- Clean, simple entry point

**Route changes:**
- `/` → landing page with Player/DM choice
- `/play` → SetupScreen (current `/` behavior, renamed)
- `/master` → restructured MasterScreen with Worlds/Sessions tabs
- `/master/:sessionId` → SessionView (unchanged)

## Tests First

- **Master tabs:** render MasterScreen → two tabs visible (Worlds, Sessions). Switch tabs → correct content shown.
- **World editor stepper:** open world → stepper shows 5 layer steps. Navigate forward/back. Each step renders EntityListEditor for correct entity types. Ecology step has CatalogPicker.
- **Layer source:** library layer shows "fork" button, custom layer shows EntityListEditor in edit mode.
- **Main page:** render landing → two cards (Play, DM). Click Play → navigates to `/play`. Click DM → navigates to `/master`.
- **Route wiring:** `/play` renders SetupScreen, `/master` renders new MasterScreen, `/` renders landing.

## Implementation

1. `frontend/src/components/LandingPage.tsx` — new main page with Player/DM cards
2. Refactor `MasterScreen.tsx` — add Tabs (shadcn/ui Tabs component), Worlds tab with world list + world editor stepper, Sessions tab with existing session management
3. `frontend/src/components/master/WorldEditor.tsx` — layer stepper component. Steps derived from layer type list. Each step renders EntityListEditor for the layer's entity types. Ecology step includes CatalogPicker.
4. Update `App.tsx` routes — `/` → LandingPage, `/play` → SetupScreen, rest unchanged
5. Move session-related UI from current MasterScreen into Sessions tab

## Integration Tests

Run `make test-integration` after implementation. Run E2E smoke test (manual or Playwright) to verify: main page renders, DM flow reaches world editor, stepper navigates layers, entity editing works through the form UI. Add integration tests for any new API interactions introduced. Verify no regressions.

## Acceptance Criteria

- [ ] Unit tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] `/master` has Worlds and Sessions tabs
- [ ] World editor stepper navigates through all 5 layers
- [ ] Each stepper step shows EntityListEditor with correct entity types
- [ ] Ecology step has CatalogPicker for monster catalog
- [ ] Library layers show fork button, custom layers are editable
- [ ] Main page (`/`) shows Player/DM choice
- [ ] Routes updated: `/play` for player flow, `/master` for DM
- [ ] `make test-integration` passes, new integration tests added if needed
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Implemented as planned. Key decisions:

- `MasterScreen` refactored with shadcn Tabs (Worlds/Sessions). Worlds tab shows world cards, clicking opens `WorldEditor` stepper. Sessions tab has existing session management (world select, create, list, delete).
- `WorldEditor` is a new component with a step-per-layer navigation. Reuses `EntityListEditor` and `CatalogPicker` from prior tasks. Library layers show fork button, custom layers are editable. Ecology step has catalog picker when custom.
- `LandingPage` is a simple Play/DM choice screen at `/`.
- Routes: `/` → LandingPage, `/play` → SetupScreen (player flow), `/master` → MasterScreen, `/master/:sessionId` → SessionView.
- `WorldInspector` (in setup/) still exists and is used by the player-facing setup flow. `WorldEditor` is the DM-facing equivalent with stepper navigation — no code shared since UX is different (inspector = accordion, editor = stepper).
- Added `tabs` shadcn component (`@base-ui/react` tabs primitive).
- 10 new tests: 3 MasterScreen (tabs, world list, session switching), 4 WorldEditor (stepper, navigation, fork button, catalog picker), 3 LandingPage (render, navigation to /play, navigation to /master).
