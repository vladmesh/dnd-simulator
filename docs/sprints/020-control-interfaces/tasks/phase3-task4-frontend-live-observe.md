# Task: Frontend live observe stream

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 3 — Spectator-listener + disconnect-debounce

## Description

Wire the master `SessionView` to the task-3 spectator WS so DM and admin see a session's events **live** instead of only via the 5s REST snapshot poll. Today `SessionView` shows world/creatures/time/saves tabs fed by `api.master.getSession`; there is no event stream. Add a read-only live event feed driven by a spectator socket.

Scope:

- Add a "Live" tab (or panel) to `SessionView`, available to both DM and admin viewing a session. The existing `observe` flag still gates write controls (time/saves tabs); the live feed is read-only for everyone — it is an observation surface, not a control. There is no action bar in the master screen.
- On entering the session view, open a spectator WS (`?spectate=true`) to the session. Accumulate the `events` arrays from incoming `turn` / `action_result` / `round_result` messages into a scrolling feed, newest last. Render each `PerceivedEvent.description` (already localized server-side). Disconnect on unmount.
- Use a **fresh `WsClient` instance**, not the exported `wsClient` singleton — the singleton belongs to the player game screen, and a master observing must not clobber a player connection (or vice versa) if both live in one browser.

Keep it minimal. Do not reuse `game/EventLog.tsx` — it is coupled to the game store and the player awareness/breakdown UI. A thin feed rendering `event.description` lines (with the event-type as a subtle tag) is enough for this phase. Richer rendering can come later.

Projection-only: the frontend opens the spectator socket for DM/admin; the backend does not enforce who may connect (phase 1/2 decision).

## Tests First

Vitest, mocking the spectator WS the same way the game component tests mock `wsClient`. New `SessionView` (or a small `SessionEventFeed`) test:

- **Live events render read-only.** Mount the session live view in DM role; simulate the spectator socket delivering a `turn` message with two `events` (e.g. an attack and a move). Both event descriptions appear in the feed. No action button / action bar is rendered.
- **Admin sees the same live feed.** Same as above in admin role; the feed renders and write controls (time/saves tabs) remain absent (existing observe behavior unchanged).
- **Feed accumulates across messages.** Deliver a `turn` then an `action_result` with new events; the feed shows events from both, in arrival order, without dropping the earlier ones.
- **Socket lifecycle.** Mounting the live view connects the spectator socket with `spectate=true` for the right session id; unmounting disconnects it. (Assert against the mocked client's `connect`/`disconnect`.)

Keep existing `SessionView` tests green (world/creatures tabs, observe-mode control stripping).

## Implementation

- `transport/wsClient.ts`: let `WsClient.connect` take a spectate flag without disturbing the player signature, e.g. `connect(sessionId: string, opts?: { playerId?: string; spectate?: boolean })` (or an overload). When `spectate`, append `spectate=true` to the URL. Keep `user_id`/`role` propagation. The exported `wsClient` singleton and its current callers are unchanged.
- New `components/master/SessionLiveFeed.tsx` (thin): instantiates `new WsClient()`, connects with `{ spectate: true }` on mount for `sessionId`, subscribes via `onMessage`, collects `events` from `turn`/`action_result`/`round_result` into local state, renders a scrolling read-only list of `description` lines (+ a small event-type tag, reuse the `EventType` colour map only if trivially importable; otherwise plain). Disconnect + unsubscribe on unmount.
- `components/master/SessionView.tsx`: add a `live` tab for both roles and render `<SessionLiveFeed sessionId={sessionId} />`. Leave the world/creatures/time/saves tabs and the `observe` write-stripping untouched.
- i18n: add a `master:tab_live` label (and any empty-state string) to the locale catalogs; run `make messages` / translate / `make compile-messages` if backend strings change (these are frontend-only, so just the i18n JSON).

Gotchas:
- Don't route the spectator stream through the game `gameStore` — keep feed state local to the master component so it can't interfere with an actual play session in the same tab.
- The spectator socket reconnects via the existing `WsClient` backoff; that's fine for observation. On `4004` (session gone) it stops retrying — show an empty/closed state, don't crash.
- The 5s REST poll for world/creatures stays; the live feed is additive.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] DM and admin viewing a session see a live, read-only event feed fed by the spectator WS
- [ ] The feed accumulates events across `turn`/`action_result`/`round_result` messages
- [ ] Uses a dedicated `WsClient` instance (not the player singleton); no action controls in the master screen
- [ ] observe-mode write-control stripping and existing tabs unchanged

## Status

`pending`
