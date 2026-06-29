# Task: Frontend role routing + worldbuilder/DM lens projection

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 2 — Three-lens projection of `/api/master/*`

## Description

Route each role into its lens and project the master screen for the two write-capable roles. Projection only — the backend stays open; the lens changes what the UI scopes and offers.

1. **Route by role.** The landing page already sets identity (`userId`, `role`) into the store (phase 1). The master entry now leads into the role's lens. `MasterScreen` reads `role` from the store and branches. A header on the master area shows the current identity + role. `null`/unknown role falls back to the current full screen (so existing behavior and tests stay green).

2. **Worldbuilder lens** — authoring scoped to own worlds:
   - Only the Worlds tab (no Sessions tab — worldbuilder has no live session per the brainstorm grid).
   - World list scoped to `creator === userId` via the new `?creator=` backend param (task 1).
   - Can create / assemble / fork / edit / delete its own worlds (existing controls).

3. **DM lens** — authoring + live session + hot-controls:
   - Worlds tab scoped to own worlds (same `?creator=` scope).
   - Sessions tab showing the DM's own sessions (filter on `created_by === userId`, using the field task 1 adds).
   - Full manage / New Session / hot-controls (current behavior), creating sessions from its own worlds.

## Tests First

Component-level (vitest + testing-library), mocking `api.master`:

- **Worldbuilder sees only own worlds, no live.** Store role `worldbuilder`, userId `alice`. `api.master.getWorlds` is called with the creator scope and returns alice's worlds only → rendered list shows alice's worlds; the Sessions tab is absent.
- **DM sees own worlds + own sessions + manage.** Store role `dm`, userId `dana`. Worlds tab + Sessions tab both present; "New Session" and per-session "Manage" controls present; the sessions list is filtered to entries whose `created_by === "dana"` (seed the mock with a mix of `dana` and `other` sessions, assert only dana's render).
- **Routing.** From the landing page with role `worldbuilder` set, activating the master entry navigates into the worldbuilder lens (assert the worldbuilder projection renders, e.g. no Sessions tab).
- **Fallback stays green.** Rendering `MasterScreen` with no role behaves like today (both tabs, all worlds) — keep `MasterScreen.test.tsx` passing (update it to set a role explicitly if needed).

## Implementation

- `frontend/src/types/api.ts` — add `created_by: string` to `SessionListItem`.
- `frontend/src/transport/apiClient.ts` — `api.master.getWorlds` accepts an optional `creator` arg, appended as `?creator=`.
- `frontend/src/components/master/MasterScreen.tsx` — read `role`/`userId` from the store; branch the projection:
  - worldbuilder: render Worlds tab only, fetch worlds with `creator=userId`.
  - dm: Worlds (creator-scoped) + Sessions (client-filter `created_by === userId`) + existing controls.
  - fallback (null/unknown): current full behavior.
  - Add an identity/role line to the header.
- `frontend/src/components/LandingPage.tsx` — the master card/link leads to the master lens for worldbuilder/dm/admin (player → play). Keep it a plain route to `/master`; the screen self-selects the lens from the store.
- i18n: add any new labels (lens header, role chips) to `frontend/src/components/master/` locale JSON via the existing `master`/`common` namespaces.

Gotchas: scope worlds at the request level (`?creator=`) for worldbuilder/DM, but keep the unfiltered fetch for the fallback. Session filtering is client-side on `created_by`. Don't remove any backend capability — admin (task 3) reuses the same screen with a different branch.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Worldbuilder lens: Worlds-only, scoped to `creator === userId`
- [ ] DM lens: own worlds + own sessions (`created_by`) + full manage/hot-controls
- [ ] Landing routes role into the correct lens; null role falls back to current screen

## Status

`pending`
