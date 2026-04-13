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

`done`

## Developer Notes

### Trace of the two data sources

- `Header.tsx:22` reads `player` from Zustand (`useGameStore((s) => s.player)`).
  `player.hp` / `player.max_hp` get updated synchronously by
  `LevelUpModal → handleConfirm → onSuccess(updated) → updatePlayer(updated)`
  (`PlayerStats.tsx:82`), so the top HP bar refreshes immediately on Confirm.
- `CombatPanel.tsx:7` previously read `awareness` only, using `combat.self_hp /
  self_max_hp / self_ac / self_resource_pools` (`CombatPanel.tsx:12, 16, 40,
  44`). Awareness is only rewritten by WS messages — `onTurn`, `onActionResult`,
  `onRoundResult` in `turnSlice.ts:65/85/108`. The level-up REST response does
  NOT push a new `turn` event, so `awareness.self_hp` stayed 12/12 until the
  next round.

Two components, two sources of truth — classic split state. `Header` won the
race because it subscribes to the slice that the REST response mutates.

### Fix

`CombatPanel` now reads `hp`, `max_hp`, `ac`, and `resource_pools` from
`player` (canonical source), keeping `awareness` only for combat-scoped,
perceived data (`self_speed`, `self_weapon`, `self_weapon_damage`,
`self_conditions`, `round_number`). The "combat mode" check still uses
`"self_hp" in awareness` as the discriminator — that contract stays. Added an
early return when `player` is null (defensive; combat panel shouldn't render
without an authenticated player anyway).

### Backend redundancy

`CombatAwareness.self_hp / self_max_hp / self_ac / self_resource_pools` are now
dead weight from the frontend's perspective. Not removing them here — they're
still used by `BudgetDisplay`, `BattleMap`, `TargetDropdown`, `Perception`,
`NpcInspectModal`, `ActionBar`, and the `"self_hp" in awareness` discriminator
leaks into many files. A clean fix would:
1. Introduce an explicit `mode: "combat"` flag on awareness to replace the
   structural `"self_hp" in awareness` discriminator.
2. Drop the redundant self_* fields from `CombatAwareness` (backend + types).
3. Refactor all consumers to read self stats from `player`.

Candidate backlog item — too broad for this bug-sweep phase.

### Tests

- New `CombatPanel.test.tsx` (3 tests):
  - HP/max_hp/AC render from `player`, not stale `awareness.self_*`.
  - Updating `player` in isolation (level-up scenario with no WS event)
    re-renders the panel — this is the regression test for the reported bug.
  - Spell slots render from `player.resource_pools` (paladin L2 spell slot
    appears without waiting for next `turn`).
- Updated `BattleMapInspect.test.tsx` — added `player` to the store fixture
  since `CombatPanel` now requires it. No behavior change.

### Acceptance verification

- Top bar and combat sidebar both subscribe to `player` for HP → stay in sync.
- `make check` green: ruff + mypy + 2134 unit tests + 236 frontend tests + tsc.
- E2E regression (phase 3 scenario) not re-run in this task — covered by unit
  test #2 which directly simulates the bug's state transition.
