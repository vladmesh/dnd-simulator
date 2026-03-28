# Phase 3 E2E Report

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 3 — Cunning Action Choice & SA Faction Check

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Rogue Dash shows cost choice dropdown | Two options: cost_action, cost_bonus_action (cunning action) | Exactly as expected — dropdown with both options | pass |
| Rogue Disengage shows cost choice dropdown | Same two cost options | Correctly shows cost_action and cost_bonus_action | pass |
| Rogue Dash as bonus action consumes bonus, preserves action | Bonus: 0, Actions: 1, Movement: 60ft | Bonus: 0, Actions: 1, Movement: 60ft | pass |
| Rogue can still Attack after bonus-action Dash | Attack button available, action budget = 1 | Attack available, returned "target too far" (correct — out of reach) | pass |
| Fighter Dash has NO cost choice | Only directional options (toward/from target) | Correctly shows direction choice, no cost options | pass |
| Fighter Disengage has NO cost choice indicator | Plain button, no dropdown icon | Plain button with no img icon | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | Both rogue and fighter sessions loaded correctly |
| Basic combat | pass | Attack logged with structured dice: [d20(N)+mod=total vs AC], hit/miss |
| Battle map | pass | Reachable cells rendered, movement budget doubled after Dash |
| Budget display | pass | Actions, Bonus, Movement, Reaction all correct |
| Character panel | pass | Race, class, level, AC, ability scores displayed |
| Second Wind button (Fighter) | pass | Resource button "1" visible for Fighter |

## Quick Fixes Applied

- None needed

## Log Analysis

- No ERROR or CRITICAL entries in session logs for either test session
- No tracebacks or unhandled exceptions

## Blockers

- None

## Minor Issues

- Cost option labels show internal keys (`cost_action`, `cost_bonus_action`) rather than user-friendly labels ("Action", "Bonus Action") — cosmetic, candidate for backlog
