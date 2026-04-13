# Task: Wire level-up modal into dashboard

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 3 — Level-up UI + E2E

## Description

Integrate `LevelUpModal` into the live game dashboard.

- In `PlayerStats`, when `player.level_up_available === true`, render a visible "Level up" button next to the level indicator (not only the modal — player may want to postpone).
- Auto-open the modal the first time `level_up_available` flips from false → true within a session (e.g. immediately after a kill grants XP across the threshold). User can close; button stays available for manual reopen.
- On modal `onSuccess`, update Zustand player slice with the returned `PlayerStatus` and close the modal. Subsequent WS updates should converge on the same state.
- No regression to existing panel: level, HP, AC, gold continue to render.

## Tests First

Vitest + RTL.

Product-level scenarios:

1. **With `level_up_available: false` there is no "Level up" button in `PlayerStats`.**
2. **When `level_up_available` becomes true, the button appears and the modal auto-opens once.** Closing and re-rendering with still-true flag does NOT auto-reopen (only transition triggers it).
3. **Clicking "Level up" after manual close reopens the modal.**
4. **After successful level-up API response, the Zustand store reflects `level: 2`, `level_up_available: false`, updated HP and resource pools,** the modal closes, and the button disappears.
5. **If the API fails, the store is not mutated and the modal stays open with the error shown** (leans on task 1's error handling).

Mock `apiClient.levelUp`. Use the existing test harness for `gameStore` (see `drawers.test.tsx` for store-touching patterns).

## Implementation

- Edit: `frontend/src/components/game/PlayerStats.tsx` — add level-up button; owns local `open` state and previous-flag ref for transition detection.
- Edit: `frontend/src/store/slices/playerSlice.ts` — ensure `updatePlayer(partial)` can merge a full `PlayerStatus` (should already). No new actions needed.
- Extend: `frontend/src/components/game/__tests__/PlayerStats.test.tsx` (create if missing) with scenarios above.
- No backend changes. No new files beyond the optional test file.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] `make check` passes; frontend tests pass
- [ ] Manual smoke: running `make serve` + `make frontend`, kill a CR-low mob, see XP bar cross threshold, modal pops up, choosing Dueling for Paladin persists through WS reconnect
- [ ] No console errors on modal open/close

## Status

`done`

## Developer Notes

- Auto-open uses the React "previous-state during render" pattern (ref + setState in render body) instead of useEffect. ESLint's `react-hooks/set-state-in-effect` flagged the original useEffect approach; this is the official recommended alternative.
- `PlayerStats` now subscribes to `sessionId` via the store directly — no prop drilling.
- Test isolation note: when the dialog is open, base-ui marks the rest of the page `aria-hidden`/`inert`, so the level-up button is not findable by `getByRole` while the modal is up. The auto-open test asserts the button visibility *after* closing the modal.
- Added `levelup_button` translation key to en/ru `game.json`.
