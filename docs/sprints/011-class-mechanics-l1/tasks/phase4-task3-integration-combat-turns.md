# Task: Integration Test — Full Fighter & Rogue Combat Turns

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 4 — Content & Tests

## Description

Integration-level tests that verify complete combat turns for class-featured characters. These tests exercise the full chain: TurnBudget → ActionProvider → ActionDispatcher → combat rules → damage application → resource consumption.

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

- Create `tests/unit/test_combat_turns.py` (or integration/ if it needs full game state)
- Build minimal combat state: creatures, battle_map, combat_state with initiative
- Use `ActionDispatcher` or the handler functions directly to execute actions
- Mock dice for deterministic assertions
- Verify budget enforcement, resource tracking, damage application

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Fighter: AC composition + attack + Second Wind + resource lifecycle
- [ ] Rogue: Cunning Action as bonus + attack with sneak attack + budget enforcement
- [ ] Cross-class: faction-aware sneak attack with Fighter ally

## Status

`pending`
