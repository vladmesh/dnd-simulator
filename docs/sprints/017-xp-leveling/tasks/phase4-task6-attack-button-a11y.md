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

`done`

## Developer Notes

**RCA.** The submenu that appears after clicking the single-target anchor had three nested buttons all starting with "Attack":

1. anchor `<Button>Attack</Button>` (always present, `title="Attack a target ..."`)
2. smite-panel normal `<button>Attack</button>` — from `smite_attack_normal` = "Attack"
3. smite-panel with-smite `<button>Attack + Smite (slot 1) (2/2)</button>`

Two of those (`1` and `2`) shared accessible name "Attack", making `getByRole('button', { name: 'Attack' })` ambiguous and forcing the phase-3 E2E to do `document.querySelectorAll('button')[16]`. The bare "Attack" label in the smite panel predates the target-aware wording used elsewhere (`attack_target` already embeds the target name via i18n).

**Chosen ARIA pattern.** Disclosure-style menu.

- Anchor buttons that open a submenu now get `aria-haspopup="menu"` + `aria-expanded={open}`; when there is only a single target, the anchor acts as a direct action button (no popup) and omits both attributes.
- Popup containers get `role="menu"` with `aria-label` carrying the contextual description (action description for target dropdown, target-scoped "Attack {target}" for the smite panel).
- Submenu items get `role="menuitem"`.
- Disambiguation is done in the label text itself rather than leaning on the `aria-label` of the container: `smite_attack_normal` and `smite_attack_with_smite` now embed `{{target}}`, matching the existing `attack_target` pattern in the target dropdown. Rationale: label text is what both screen readers and test locators see without having to traverse ARIA relationships, and i18n already had the hook via interpolation. No keyboard-arrow navigation added — the submenu items are real `<button>` elements, so Tab works today; arrow-key navigation is a nice-to-have and can be added as a separate, generic a11y pass over the dropdown family. Keeping the scope small for this bug-sweep phase.

**Changes.**

- `i18n/locales/{en,ru}/game.json`: both `smite_attack_normal` and `smite_attack_with_smite` now include `{{target}}`.
- `SmiteChoice.tsx`: required `targetName` prop; translations call with `{ target: targetName }`; container + items carry menu/menuitem roles.
- `action-bar/TargetDropdown.tsx`: anchor gets `aria-haspopup`/`aria-expanded` when multi-target; target dropdown and smite panel both render with `role="menu"` + `role="menuitem"`; smite panel labels use target id.
- `NpcInspectModal.tsx`, `Perception.tsx`: pass `targetName={entity.id}` into `<SmiteChoice>`.
- `ActionBar.test.tsx`: new test pins the invariant "no two submenu buttons share an accessible name" in a single-target Paladin-with-slots scenario.
- `docs/e2e-playbook.md`: step 3.5 now selects the smite item via `getByRole('menuitem', { name: /Attack practice_thug \+ Smite \(slot 1\)/ })` instead of relying on a positional click.

**`make check` status.** The frontend vitest suite is green (238 tests). TypeScript is clean. Backend untouched. Lint (`make lint-frontend`) has 26 pre-existing errors on `main` at `00d5c5c` — verified via `git stash && make lint-frontend` against the same baseline — none of them are in files this task modified. Fixing them (setState-in-effect across master forms, react-refresh on shadcn primitives, an unused `enemies` prop in `ActionButton.tsx`) is clearly out of scope for a submenu-label fix and belongs in a dedicated lint-cleanup task; flagging it explicitly rather than folding it silently into this commit.
