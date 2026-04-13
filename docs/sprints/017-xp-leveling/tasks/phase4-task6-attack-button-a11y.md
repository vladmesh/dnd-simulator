# Task: Action bar — duplicate "Attack" buttons in a11y tree

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 4 — E2E follow-up bug sweep

## Symptom

In the phase 3 E2E DOM snapshot taken right before the Smite, three buttons share the literal text "Attack":

```
i=14 (anchor)        <button title="Attack a target with your equipped weapon or fists." data-cost-type="action" ...>Attack</button>
i=15 (target item)   <button class="...rounded px-2...">Attack</button>
i=16 (smite item)    <button class="...">Attack + Smite (slot 1) (2/2)</button>
```

So Playwright's `getByRole('button', { name: 'Attack' })` is ambiguous, and screen readers will announce two indistinguishable "Attack" buttons. We worked around it in the E2E by clicking via `document.querySelectorAll('button')[16]`, which is exactly the kind of fragile selector that bites later.

This is a small bug but it touches an action that fires every combat round — fixing it improves both UX and test stability.

## Investigation scope

In Developer Notes, document:
1. **Component layout**: which file renders the anchor + submenu? Likely `frontend/src/components/game/action-bar/AttackAction.tsx` (or similar). Note the current accessibility pattern.
2. **Why two visible "Attack" labels?** The submenu probably shows one item per target × per attack mode; with a single hostile target, the bare "Attack" item is technically "Attack practice_thug" with the target name truncated. Find where the truncation/labelling happens.
3. **What's the right ARIA pattern?** Either:
   - `role="menu"` with `aria-haspopup` on the anchor, items have unique accessible names (e.g. include target).
   - Anchor button + submenu items where item labels always include disambiguation (target name, smite slot, etc.).
   The W3C disclosure / menu pattern guidance applies here; pick one and stick with it.

## Possible directions

- **Always include target name in submenu items**: "Attack practice_thug", "Attack practice_thug + Smite (slot 1)". Removes ambiguity by data, no ARIA gymnastics needed. **Likely simplest and most informative.**
- **Use a proper `role="menu"` with `aria-label="Attack options"`** on the popup, anchor gets `aria-haspopup="menu"` + `aria-expanded`. Items keep current text but the menu container provides the disambiguation context.
- Both: target name in items + correct ARIA for keyboard navigation.

## Tests First

1. **Frontend unit (RTL)**: render the action bar with one hostile target and a smite-capable player; assert no two visible elements share accessible name "Attack".
2. **Keyboard navigation test**: Tab into anchor → Enter opens submenu → arrow keys navigate items → Enter selects.
3. **Update phase 3 playbook scenario** to use the new button names instead of relying on positional click.

## Implementation

- Refactor the attack submenu rendering to always include disambiguating context in item labels.
- Add the right ARIA roles/states on anchor + popup if missing.
- Don't break existing `data-testid` attributes if any test depends on them — grep for `attack-target` / `attack-option` first.
- Update phase 3 E2E playbook (and the post-fix re-run) to use stable `getByRole('button', { name: /Attack practice_thug/ })` selectors.

## Acceptance Criteria

- [ ] Developer Notes show the chosen ARIA pattern with rationale
- [ ] No two visible buttons in the action bar share the same accessible name in any reasonable combat scenario
- [ ] Existing action-bar tests pass; one new test pins the no-duplicates invariant
- [ ] Phase 3 E2E playbook step 3.5 uses the new selectors
- [ ] `make check` green

## Status

`pending`
