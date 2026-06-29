# Task: Frontend identity/role selector + header propagation

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 1 — Identity & role keystone

## Description

Give the frontend a current-identity concept and send it on every backend call, so Phase 2's lens UI is testable through the browser. Minimal, no auth UI.

- **State — `frontend/src/store/slices/identitySlice.ts` (new):** `userId: string | null`, `role: "worldbuilder" | "dm" | "admin" | "player" | null`, `setIdentity(userId, role)`. Persist to `localStorage` and rehydrate on load (so a chosen identity survives refresh). Compose into `store/gameStore.ts` alongside the existing slices.
- **HTTP — `frontend/src/transport/apiClient.ts` (~L55):** in the single `request()` header block, inject `X-User-Id` and `X-Role` from the identity store when set. When unset, omit them (backend falls back to its default identity).
- **WS — `frontend/src/transport/wsClient.ts` (~L80):** append `user_id` / `role` query params to the WS URL when identity is set (mirrors the existing `player_id` param).
- **UI — `frontend/src/components/LandingPage.tsx`:** a small identity selector (username input + role dropdown/radios covering the four roles) wired to `setIdentity`. Keep it unobtrusive — it sits above/beside the existing Play / Dungeon Master cards. Add i18n strings (en + ru `.po`/json as the project does it).

Routing is unchanged this task — role still picks Play vs Master entry as today; Phase 2 differentiates the master UI by role.

## Tests First

Vitest, product-level (behavior, not field-existence):

- **Identity persists across reload:** after `setIdentity("alice", "dm")`, the store reports `userId="alice"`, `role="dm"`; simulating a reload (re-init store from localStorage) restores the same identity.
- **Requests carry identity:** with identity set to `("alice", "dm")`, an `apiClient` call issues a `fetch` whose headers include `X-User-Id: alice` and `X-Role: dm` (mock `fetch`, assert headers).
- **No identity → no identity headers:** with identity unset, an `apiClient` call sends neither `X-User-Id` nor `X-Role` (backend default applies).
- **Selector drives state:** rendering `LandingPage`, choosing a role + entering a username calls `setIdentity` with those values (mock the store action, assert call).

## Implementation

After red: add the slice (with persist), inject headers in the one `request()` wrapper, add WS query params, build the selector on `LandingPage`. Read identity from the store inside `apiClient`/`wsClient` (module-level store access, as other transport code does). Keep the diff centralized — no per-call header plumbing.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing frontend tests still pass (`make check`)
- [ ] Identity persists to localStorage and rehydrates
- [ ] Every HTTP call routes through the one wrapper and carries `X-User-Id`/`X-Role` when set
- [ ] WS URL carries `user_id`/`role` when set
- [ ] Selector on LandingPage sets identity; strings are i18n (en + ru)

## Status

`pending`
