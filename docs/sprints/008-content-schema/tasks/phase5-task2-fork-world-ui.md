# Task: Fork World + Create World UI on Master

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 5 — DM World Management

## Description

Master can fork an existing world (full copy with new name), rename it, edit it, and delete it.

**Worlds tab changes:**

- Each world card gets a "Fork" button (copies the world via `POST /api/master/worlds/{id}/fork`).
- After fork: dialog/inline form for new world ID and name. On submit → world appears in the list.
- Forked worlds show "Delete" button. Base worlds do not.
- Clicking a forked world card → opens `WorldEditor` in edit mode.
- Clicking a base world card → opens `WorldEditor` in read-only mode (view only).

**Frontend API client:**

- Add `forkWorld(worldId, data: { new_world_id, new_world_name? })` method — calls existing backend endpoint.
- Add `deleteWorld(worldId)` method — calls existing backend endpoint.

**Backend enrichment:**

- `getWorlds` response: add `editable: bool` field to `WorldListItem`. True if the world directory contains a manifest with at least one custom layer (i.e., it's a fork). Or simpler: true if the world is NOT in the base worlds set. The backend already has `_BASE_WORLDS` — use that.

## Tests First

- **Fork button:** render Worlds tab → each world card has a "Fork" button. Click fork → dialog appears with ID/name inputs.
- **Fork submission:** fill fork dialog, submit → `api.master.forkWorld` called with correct params, world list refreshes, new world appears.
- **Delete button:** forked (editable) world shows delete button. Base world does not.
- **Delete action:** click delete on forked world → confirmation → `api.master.deleteWorld` called, world removed from list.
- **Read-only vs editable:** click base world → WorldEditor opens with readOnly=true. Click forked world → WorldEditor opens with readOnly=false.
- **Backend:** `GET /api/master/worlds` returns `editable` field. Base worlds → `editable: false`. Forked worlds → `editable: true`.

## Implementation

1. Backend: add `editable` field to world list response. In `get_worlds()`, check if world_id is in `_BASE_WORLDS` → `editable = False`, otherwise `True`.
2. Frontend types: add `editable: boolean` to `WorldListItem`.
3. Frontend API client: add `forkWorld`, `deleteWorld` methods.
4. `MasterScreen` Worlds tab: fork button on cards, fork dialog (inline or modal), delete button on editable worlds only, read-only/editable routing to WorldEditor.
5. i18n keys for fork dialog, delete confirmation, etc.

## Acceptance Criteria

- [ ] Unit tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Fork creates a full world copy with new ID/name
- [ ] Forked world is fully editable in WorldEditor
- [ ] Base worlds open in read-only mode
- [ ] Delete works on forked worlds, blocked on base worlds
- [ ] `editable` field in API response
- [ ] `make check` passes

## Status

`pending`
