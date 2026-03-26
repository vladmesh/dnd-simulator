# Task: Move WorldInspector from WorldPicker to MasterScreen

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 3.5 — Move Fork UI to Master Screen

## Description

WorldInspector (layer list + fork buttons) is currently on the player-facing WorldPicker on the setup screen. Players don't need to see or manage layers — they pick a world and play. Fork/inspect is a master concern.

Move WorldInspector to MasterScreen (`/master`), shown under the world selector for the currently selected world. Clean up WorldPicker to be player-focused (cards with name + description + "New Session" only).

## Tests First

### Unit tests (frontend build)

No new unit tests — this is a UI relocation. Verify TypeScript compiles and lint passes.

### What to verify manually

- WorldPicker has no "Layers" button or WorldInspector
- MasterScreen shows WorldInspector for the selected world
- Fork button works from MasterScreen
- Forked layer shows "Custom", fork button disappears

## Implementation

### 1. Clean up WorldPicker

Remove from `WorldPicker.tsx`:
- `WorldInspector` import
- `expandedWorld` state
- `ChevronDown`, `ChevronRight` imports
- "Layers" button and `{expandedWorld === world.id && <WorldInspector ... />}` render

### 2. Move WorldInspector to MasterScreen

In `MasterScreen.tsx`:
- Import `WorldInspector`
- Render `<WorldInspector worldId={selectedWorld} />` below the world selector row (only when `selectedWorld` is set)

### 3. Move i18n keys

Move layer/fork keys from `setup.json` to `master.json` (both `en` and `ru` locales):
- `view_layers`, `layers_load_error`, `fork_error`, `fork_btn`, `source_library`, `source_custom`
- `layer_geography`, `layer_politics`, `layer_settlements`, `layer_ecology`, `layer_entities`

Update `WorldInspector.tsx` to use `master` namespace instead of `setup`.

## Acceptance Criteria

- [ ] WorldPicker shows only world cards with "New Session" — no layer inspector
- [ ] MasterScreen shows layer inspector for selected world
- [ ] Fork works from MasterScreen
- [ ] TypeScript compiles, lint passes
- [ ] All backend tests pass

## Status

`done`

## Developer Notes

Straightforward relocation — no surprises. Removed WorldInspector, expandedWorld state, ChevronDown/ChevronRight from WorldPicker. Added WorldInspector import and render in MasterScreen below the world selector row. Moved 11 i18n keys (view_layers, layers_load_error, fork_error, fork_btn, source_library, source_custom, layer_*) from setup.json to master.json in both en and ru locales. Updated WorldInspector.tsx to use `master` namespace instead of `setup`.
