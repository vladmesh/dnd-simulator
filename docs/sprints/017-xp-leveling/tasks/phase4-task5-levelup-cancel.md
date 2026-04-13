# Task: Level-up modal Cancel — define and verify behavior

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 4 — E2E follow-up bug sweep

## Symptom

The level-up modal renders a `Cancel` button (visible in the phase 3 E2E DOM snapshot at `ref=e495`), but its contract is undocumented and uncovered by tests:

- Does it just close the modal and leave `level_up_available: true`?
- If yes — does the modal re-open on the next `turn` event, or only on the manual button in `PlayerStats`?
- Does it interact with the auto-open trigger (will it spam-reopen every turn until the player levels up)?

Phase 3 task 1 unit tests cover Cancel **only** at the component level (`Cancel fires onClose without calling the API`). The dashboard wiring (task 2) doesn't have an equivalent, so the user-visible behavior is whatever fell out of the wiring — which we never verified.

## Investigation scope

Before any code change, document in Developer Notes:

1. **What's the user intent for Cancel?** Two reasonable readings:
   - "Defer my level-up — I'll click the button when I'm ready." → state stays, manual button stays visible, auto-open does NOT re-fire on next turn (would be annoying).
   - "I made a mistake choosing Dueling, let me start over." → close with no commit; modal can be re-opened immediately.
   The two are not mutually exclusive but the auto-open behavior must not fight the user.
2. **Current behavior**: trace `LevelUpModal` close → store update path. Does anything mark the modal as "user-dismissed this turn"? If not, auto-open will re-fire on the next `turn` event and spam.
3. **Where is the "auto-open" trigger?** Probably a `useEffect` in `Dashboard` that watches `level_up_available`. Identify it.

Pick the policy in writing (recommend: **Cancel = defer, suppress auto-open until next combat ends or until the manual button is clicked**) and justify.

## Possible directions

- Add a `levelUpDismissed` boolean to the Zustand store; auto-open trigger checks `level_up_available && !levelUpDismissed`. Reset on combat-ended event or on manual click of the level-up button.
- Just suppress auto-open while `Dashboard` has the modal closed AND `levelUpDismissed` flag is true; flag clears on session reload / combat end.
- Track the dismissal in URL/route state — overkill for a transient flag.

## Tests First

1. **Frontend unit (RTL)**: open the modal → click Cancel → assert `onClose` called and parent state has `dismissed=true`.
2. **Frontend integration**: mount `Dashboard`, push a `turn` event with `level_up_available: true` → modal opens → Cancel → push another `turn` event with same flag → modal stays closed.
3. **Re-trigger**: click the manual `Level Up` button in `PlayerStats` after dismissal → modal opens.
4. **E2E**: append a step to phase 3 playbook scenario 3.5 that exercises Cancel → manual reopen → Confirm.

## Implementation

- Add `levelUpDismissed: boolean` to player slice (or session UI slice — ideally not on the player domain object).
- Wire Cancel button to set the flag; auto-open trigger to honor it; manual button click to clear it.
- Reset on combat-ended (so a new fight + new XP correctly re-arms auto-open if the player is still pending level).
- Update playbook scenario 3.5 with the new Cancel sub-flow.

## Acceptance Criteria

- [ ] Developer Notes contain the contract decision with rationale
- [ ] Cancel closes the modal, leaves `level_up_available=true`, suppresses auto-open until either combat ends or the manual button is clicked
- [ ] No regression: Confirm still works, Confirm still flips `level_up_available` to false
- [ ] Unit + E2E tests cover the Cancel → defer → manual reopen path
- [ ] `make check` green

## Status

`done`

## Developer Notes

**Contract decision:** Cancel = defer. Modal closes, `level_up_available` stays true, manual "Level Up" button remains visible in `PlayerStats`. Auto-open is suppressed until either (a) a `combat_ended` event is processed or (b) the user clicks the manual button. Rationale: "mistake choosing Dueling" is still supported — user can reopen anytime via the manual button — while simultaneously not spamming the modal on every `turn`/`round_result` while `level_up_available` is still true.

**Previous behavior** used a `prevFlagRef` in `PlayerStats` that auto-opened once on `false → true` transition and relied on component-local state. It did suppress re-open on subsequent updates with the same flag, but:
  - It was implicit — no documented contract.
  - After a Cancel, the modal would never re-auto-open, even after another combat cycle, unless `level_up_available` toggled off → on (which doesn't happen mid-sprint since the server doesn't clear the flag until the player actually levels up).

**Implementation:**
- Added `levelUpDismissed: boolean` (+ `setLevelUpDismissed`) to `playerSlice`. UI-only; not on `PlayerStatus` domain object.
- `turnSlice`: `onTurn` / `onActionResult` / `onRoundResult` now inspect the event list; any `combat_ended` event clears the dismiss flag.
- `PlayerStats`: modal open is now **derived** — `levelUpAvailable && !levelUpDismissed`. Cancel sets dismiss=true, Confirm success clears it, manual button click clears it. This removed the ref+useEffect dance and sidesteps the `react-hooks/set-state-in-effect` lint rule.

**Tests:**
- Updated `PlayerStats.test.tsx`: existing "no auto-reopen on same flag" now asserts `levelUpDismissed=true` post-Cancel. Added new test: combat_ended event fed through `onRoundResult` clears the flag and auto-reopens the modal.
- E2E playbook scenario 3.5 extended with the Cancel → manual reopen → Confirm sub-flow.

**Verified:** `make test-frontend typecheck-frontend` green (237 tests). `make test-unit` green (2134 tests). Backend lint/typecheck green. Frontend lint baseline unchanged (24 pre-existing errors on main, no new ones from this change).
