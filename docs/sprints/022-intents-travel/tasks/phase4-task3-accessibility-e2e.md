# Task: Target accessibility and journey E2E

**Date:** 2026-07-11
**Sprint:** 022-intents-travel
**Phase:** 4 — Interruptible journeys and E2E closure

## Description

Make every visible Attack control identify its target in the accessibility tree, then validate the completed sprint through the real UI. The nearby list, NPC inspect modal, action-bar target menu, and smite choices must expose distinct localized names when several attack controls are present. Close `attack-buttons-accessible-names` only after a component test and browser scenario select the intended target by role and accessible name.

Run the phase E2E scenario through travel, save/load or reconnect, interruption at an intermediate location, and return of player control. Confirm the journey panel clears at interruption, the displayed location is the reached node, combat or scene UI is coherent, and a later status update does not replay progress. Use the normal phase report boundary; any non-trivial product failure becomes a finding rather than expanding this task beyond quick-fix scope.

## Tests First

- With two nearby targets and an open inspect modal, every Attack button has a unique localized accessible name containing its target; selecting one sends that target ID.
- Action-bar and smite menu items remain uniquely selectable by accessible name in both English and Russian.
- After an interrupted mid-route journey, the UI clears journey progress, shows the reached location, and exposes exactly one player action surface.

## Implementation

Add target-aware gettext strings or `aria-label` values to the remaining bare Attack controls in `Perception` and `NpcInspectModal`, reusing the existing action-bar target naming contract where possible. Update focused frontend tests and the backlog checkbox. Then execute the phase E2E checklist against a clean detached stack and write `docs/sprints/022-intents-travel/e2e/phase4-report.md`.

Likely files: `frontend/src/components/game/Perception.tsx`, `frontend/src/components/game/NpcInspectModal.tsx`, focused component tests, `frontend/src/i18n/locales/{en,ru}/game.json`, `docs/BACKLOG.md`, and the phase E2E report.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Every Attack control exposed at the same time has a unique target-aware accessible name in EN and RU.
- [ ] Browser automation selects the intended target without text or DOM-position ambiguity.
- [ ] Phase E2E covers a persisted or reconnected journey interrupted at an intermediate location and reports no blockers.
- [ ] `attack-buttons-accessible-names` is marked complete only after the browser scenario passes.

## Status

`pending`
