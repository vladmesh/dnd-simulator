# Task: Integration Test — Full Fighter & Rogue Combat Turns

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 4 — Content & Tests

## Description

**This MUST be integration tests on a live docker compose stack (backend + test client).** Not unit tests, not E2E/Playwright. Tests hit the real API, use real content loading, real game state, real combat pipeline. The only thing mocked is dice randomness — if the system doesn't support deterministic dice in integration tests (e.g. battle map positions are random), add that capability first (seed or override mechanism).

Tests verify complete combat turns for class-featured characters through the full HTTP chain: API request → GameService → Round → ActionDispatcher → combat rules → damage → response.

## Tests First

**Fighter full turn:**
- Fighter (Defense style, chain_mail, shield, longsword) starts turn. Effective AC = chain_mail(16) + shield(+2) + defense(+1) = 19. TurnBudget has 1 action, 1 bonus_action, 30ft movement.
- Fighter attacks goblin: hit resolves with proficiency + STR mod. Damage applied to target HP.
- Fighter uses Second Wind (bonus action): heals 1d10+level, resource consumed. Second attempt in same rest fails (resource exhausted).
- After short rest, Second Wind resource resets.

**Rogue full turn:**
- Rogue (rapier, studded_leather) in combat with ally adjacent to target. ActionProvider offers DASH with cost_options (action, bonus_action).
- Rogue uses Cunning Action DASH as bonus_action (budget: bonus_action consumed, action still available).
- Rogue attacks with rapier: sneak attack triggers (ally adjacent), damage includes sneak attack dice.
- Rogue attacks again — no action budget left, rejected.

**Mixed combat scenario:**
- Fighter and Rogue vs goblin. Fighter attacks (no sneak attack — wrong class). Rogue attacks same goblin with ally (Fighter) adjacent — sneak attack triggers because Fighter's faction is allied.

## Implementation

- Tests go in `tests/integration/` — run via `make test-integration` on live docker compose stack
- If dice/positioning randomness prevents deterministic assertions: add a seed or override mechanism (e.g. env var `DND_DICE_SEED`, or a test-only API endpoint to fix dice rolls). This is a prerequisite — do it first if needed.
- If battle map starting positions are random: add a way to set them deterministically (seed or explicit placement via API).
- Use real content (sword_vale world with the Fighter/Rogue NPCs from Task 1).
- Hit the REST/WebSocket API — no direct Python imports of game internals.
- Assert on API response payloads: HP changes, damage breakdowns, budget decrements, resource states.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Tests run on live stack via `make test-integration` (NOT unit tests, NOT E2E)
- [ ] Dice randomness is controllable for deterministic assertions
- [ ] Fighter: AC composition + attack + Second Wind + resource lifecycle
- [ ] Rogue: Cunning Action as bonus + attack with sneak attack + budget enforcement
- [ ] Cross-class: faction-aware sneak attack with Fighter ally

## Status

`pending`
