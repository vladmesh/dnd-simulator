# Task: Admin read-only park lens + inline creature inventory

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 2 — Three-lens projection of `/api/master/*`

## Description

The third lens, plus the one real remaining piece of `master-panel-creature-inventory`.

1. **Admin park lens** — read-only cross-session / cross-world observation:
   - All sessions regardless of `created_by`, across all worlds; all worlds read-only.
   - No create / assemble / fork / edit / delete; no New Session; no hot-controls. Observation only — admin watches the park without touching the fiction (brainstorm: "Админка ≈ DM минус нудж плюс техника").
   - Attribution / tech columns visible: `created_by`, in-game `time`, world (the fields task 1 surfaces).
   - `SessionView` (`/master/:sessionId`) opens read-only for admin: hot-control write actions (spawn / patch / delete / give-item / brain / time-advance / save controls) are hidden or disabled; observation panes (world overview, creature list, event log) remain.

2. **Inline creature inventory in observation.** The read-only creature observation list shows each creature's items + equipped weapon inline. The data is already on `CreatureResponse` (`inventory`, `equipped_weapon`) — this renders it in the `CreatureList` rows (and/or `WorldOverview` entity rows) so DM/admin observers see items at a glance, not only inside the edit dialog. This is the remaining gap of the already-delivered `master-panel-creature-inventory` (backend since sprint 007, edit-dialog rendering since sprint 007).

## Tests First

Component-level (vitest + testing-library), mocking `api.master`:

- **Admin sees the whole park, read-only.** Store role `admin`. `api.master.getSessions` returns sessions from multiple `created_by` values → all render (no `created_by` filter). No "New Session" button; world cards have no delete / fork / edit-write affordance; `created_by` and `time` are shown.
- **Admin SessionView is observation-only.** Render `SessionView`/creatures pane in admin mode → spawn / patch / delete / give-item controls are absent; the creature list and event log still render.
- **Inline inventory.** Render the creature observation list with a creature whose `inventory` has named items and a set `equipped_weapon` → the item names and the equipped weapon's attack name render inline in the row (not only in an opened dialog). A creature with empty inventory renders without items and without error.

## Implementation

- `frontend/src/components/master/MasterScreen.tsx` — add the `admin` branch: unfiltered worlds + sessions, strip all write controls, render `created_by` / `time` columns.
- `frontend/src/components/master/SessionView.tsx` — accept a read-only / observe mode (derived from `role === "admin"`); gate the write controls and pass the flag to child panes.
- `frontend/src/components/master/CreatureList.tsx` (and `WorldOverview.tsx` if it lists entities) — render inline inventory badges + equipped weapon for each creature row; hide spawn/edit/delete actions in observe mode.
- i18n: labels for the park view / observation mode in the `master` namespace.
- `docs/BACKLOG.md` — mark `master-panel-creature-inventory` resolved with a note: backend + edit-dialog shipped sprint 007; inline observation display added here.

Gotchas: reuse the existing observation components — admin is "DM minus writes plus breadth", not a new screen. Keep DM (task 2) write-capable; only the `admin` branch strips writes. Inline inventory uses data already present in `CreatureResponse`, so no backend change.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Admin lens: all sessions/worlds, read-only, attribution + clock shown, no write controls
- [ ] Admin `SessionView` is observation-only (hot-controls gated)
- [ ] Creature items + equipped weapon render inline in the observation list
- [ ] `master-panel-creature-inventory` marked resolved in BACKLOG

## Status

`pending`
