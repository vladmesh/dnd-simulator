# Sprint 011 Status

**Sprint:** 011-class-mechanics-l1
**Phase:** 0 — Structured Dice & Roll Breakdown
**Updated:** 2026-03-28

## Current

Phase 0 added before Phase 1. Structured dice pipeline as foundation for GWF rerolls and clickable combat log. 3 tasks, strictly sequential. Ready to start task 1.

## Next Steps

- Task 1: `core/rolls.py` types + `rules/dice.py` refactor (`roll()` → `DiceResult`, `roll_d20()` → `D20Result`, `reroll_below`)
- Task 2: Thread structured results through checks → combat → combat_manager → event data
- Task 3: Frontend `RollBreakdown` component, expandable attack events
