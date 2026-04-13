# Task: Combat sidebar shows stale HP after level-up

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 4 — E2E follow-up bug sweep

## Symptom

In the phase 3 E2E, immediately after the level-up modal Confirm:
- Top header HP bar updated correctly: `12/12` → `20/20`.
- Combat sidebar `PlayerStats` panel kept showing `HP: 12/12` and `Weapon: longsword slash (1d8)` until the next round/turn cycle.

That's two components reading the same state from two different places (or one component caching). Either bug or an architectural smell — doesn't matter which once the user notices the inconsistency.

## Investigation scope

Document in Developer Notes:

1. **Where does the top-bar HP read from?** Find the component (likely `frontend/src/components/game/dashboard/Header.tsx` or `PlayerHpBar.tsx`). Trace its data source — Zustand selector, props, or direct hook?
2. **Where does the combat-sidebar `PlayerStats` read from?** Almost certainly a different selector or a stale-prop closure. Find it.
3. **What WS event delivers the post-level-up player state?** The level-up POST returns `PlayerStatus` REST-side, but does the WS push a `turn` or a dedicated event that updates the in-store player object? If only the level-up REST response carries the new max_hp, only callers that consume that response see the update — which would explain the symptom (top bar updated via that response handler, sidebar keeps last `turn` payload).
4. **Is there a single canonical "current player" piece of state?** If yes, both components should consume it. If no, that's the actual bug — fragmented sources of truth.

Reproduce the bug locally with the dev stack before any fix, so the regression test can be written deterministically.

## Possible directions

- **Single source of truth in store**: there's one `currentPlayer` slice in Zustand; both components subscribe to it; level-up REST response calls `setCurrentPlayer(updated)`. Top bar and sidebar always render the same HP. Likely the right answer.
- **Push a `player_updated` WS event** from backend after level-up so all clients re-read state via the same path. Cleaner if multiplayer is a concern; overkill if single-player.
- **Re-fetch `/status` after level-up** in any component that displays player stats. Quick, but brittle (forgets components, race-y).

Choose one and justify.

## Tests First

1. **Frontend unit (Vitest + RTL)**: render `PlayerStats` with a Zustand store fixture; dispatch a level-up state update; assert the panel re-renders with new HP.
2. **Frontend integration (mock WS)**: simulate level-up REST response handling; assert both top bar and sidebar reflect new HP within the same render cycle.
3. **E2E regression** (re-run phase 3 scenario): no `HP: 12/12` text visible after Confirm.

## Implementation

- Likely a 5–20 LoC change in the store + one or two component files. **Do not** add a `useEffect` that re-fetches after every render — that's papering over the architecture issue.
- Remove any local component state that mirrors player HP.
- If the level-up response handler currently does an ad-hoc `setMaxHp` call — replace with `setCurrentPlayer(response)` so all derived stats refresh at once.

## Acceptance Criteria

- [ ] Developer Notes contain the trace of both data sources with file:line refs
- [ ] One canonical current-player state; both components subscribe to it
- [ ] Phase 3 E2E shows updated HP in both top bar AND combat sidebar immediately after Confirm
- [ ] All existing frontend tests still pass
- [ ] `make check` green

## Status

`pending`
