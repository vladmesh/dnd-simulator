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

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing frontend tests still pass (`make check`)
- [x] Identity persists to localStorage and rehydrates
- [x] Every HTTP call routes through the one wrapper and carries `X-User-Id`/`X-Role` when set
- [x] WS URL carries `user_id`/`role` when set
- [x] Selector on LandingPage sets identity; strings are i18n (en + ru)

## Status

`done`

## Developer Notes

- **Single source of truth = the zustand slice.** `identitySlice` holds `userId`/`role`; `setIdentity` writes through to `localStorage` (key `"identity"`, JSON `{userId, role}`) and the slice rehydrates from it at store creation via the exported `loadIdentity()`. No second mirror. `loadIdentity` validates the persisted role against `ROLES` so a corrupted/stale blob degrades to nulls rather than leaking a bad role into headers.
- **Transport reads the store, not localStorage.** `apiClient.request()` and `wsClient.doConnect()` both call `useGameStore.getState()` and inject only when set — HTTP as `X-User-Id`/`X-Role` headers, WS as `user_id`/`role` query params. The WS URL build was refactored from string-concat to `URLSearchParams` so `player_id` + the two identity params compose cleanly.
- **Import cycle note:** `wsClient` now imports `gameStore`, completing a `gameStore → connectionSlice → wsClient → gameStore` cycle. It's safe because the only `useGameStore` access is inside `doConnect()` (call time), never at module init — ESM live bindings are resolved by then. `make check` (tsc + eslint + vitest) is green, no circular-import breakage. `apiClient → gameStore` is acyclic (the store never imports apiClient).
- **Selector:** native `<select>` (not the Radix shadcn Select) for the role so `userEvent.selectOptions` drives it in tests; `Input` for the name. Both wired through one `apply()` that calls `setIdentity` on any change once the name is non-blank. Backend `Role` values (`worldbuilder`/`dm`/`admin`/`player`) are the option values verbatim, so header/param strings match `service/identity.Role` with no mapping.
- **Routing unchanged this task** — role still only labels the identity; Play vs Master entry is still the card click. Phase 2 differentiates the master UI by role.
- Backend WS endpoint still reads only `player_id` (Phase 3 consumes `user_id`/`role`); sending them now is forward-compatible and ignored.
