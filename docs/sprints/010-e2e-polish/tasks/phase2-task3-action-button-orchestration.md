# Task: Extract ActionButton, finalize orchestration

**Date:** 2026-03-28
**Sprint:** 010-e2e-polish
**Phase:** 2 — ActionBar Decomposition

## Description

The `renderAction()` function (lines 112-241) is the heaviest piece remaining in ActionBar. It handles four rendering modes: target dropdown, directional dropdown, say-with-text-input, and simple button. Extract this into an `ActionButton` component that takes an action and renders the appropriate UI.

Also extract the "say" action's text input into a `SayAction` component (it has its own state: `sayOpen`, `sayText`, `sayInputRef`).

Target:
```
components/game/action-bar/
  ActionButton.tsx  — dispatches to TargetDropdown, DirectionalDropdown, SayAction, or plain Button
  SayAction.tsx     — say text input with submit handling
```

After this task, ActionBar.tsx should be pure orchestration:
- Read store state
- Filter/categorize actions
- Render: core actions (via ActionButton), drawers (via extracted drawer components), end turn button
- Manage openDropdown state

**ActionBar.tsx must be < 150 lines.**

## Tests First

1. **ActionButton** — given an attack action with enemies, renders target selection; given a say action, renders text input; given a simple action, renders plain button; disabled when cost depleted
2. **SayAction** — typing text and pressing Enter sends `say` action with message param; empty text does not send; Escape closes input

Product-level: "player types 'Hello' in say box and presses Enter → say action sent with message 'Hello'". Not "SayAction calls onSend when form submitted".

## Implementation

1. Create SayAction.tsx — extract say-specific state and JSX from renderAction
2. Create ActionButton.tsx — wraps the rendering dispatch logic: checks params → picks TargetDropdown, DirectionalDropdown, SayAction, or Button
3. Update ActionBar.tsx to use ActionButton for each action in core/other groups
4. Remove `renderAction`, `sayOpen`, `sayText`, `sayInputRef` state from ActionBar
5. Verify ActionBar.tsx is < 150 lines of orchestration
6. All existing tests green, `make check` passes

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing ActionBar.test.tsx tests still pass (`make check`)
- [ ] ActionButton.tsx < 150 lines
- [ ] SayAction.tsx < 150 lines
- [ ] **ActionBar.tsx < 150 lines** (orchestration only)
- [ ] Visually identical action bar (same DOM structure, same data attributes)

## Status

`done`

## Developer Notes

Extracted `ActionButton` (99 lines) and `SayAction` (72 lines) from `ActionBar`. `ActionButton` dispatches to `TargetDropdown`, `DirectionalDropdown`, `SayAction`, or plain `Button` based on action params. `SayAction` owns its own `sayOpen`/`sayText` state.

ActionBar reduced from 285 → 140 lines: pure orchestration (store reads, action filtering, layout). Removed the `containerRef`/`useEffect` for Escape handling and the `useRef` for say input — both now live in child components. The `onKeyDown` handler on the container div still handles Escape for dropdown state.

All 136 frontend tests pass, all 1452 backend tests pass. No test modifications needed — pure refactor.
