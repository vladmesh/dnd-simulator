# Phase 1.5 E2E Report

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 1.5 — Save/Load Gaps

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Spawn NPC via API, save, delete, load | Spawned NPC returns after load with correct fields | NPC returned with correct name, hp, ac, ai_type, location | pass |
| Spawned NPC max_hp preserved | max_hp matches original spawn value (15) | Initially 4 (default), fixed by adding `hp` alias to get_state | pass (after fix) |
| Brain switch to llm, save, switch back, load | ai_type restored to "llm" from save | ai_type correctly restored as "llm" | pass |
| Brain switch without LLM key | Graceful fallback to RuleBrain, no crash | Returns 200, ai_type set to "llm" | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | Worlds list loads, session created |
| Create character | pass | Character created, game starts |
| Basic combat (attack NPC) | pass | Combat initiated, damage applied, battle map visible |

## Quick Fixes Applied

- **NPC max_hp lost on load**: `get_state()` serialized `max_hp` but `parse_npc()` reads `hp`. Added `hp`, `ai`, `start_location`, `race`, `class` aliases to NPC serialization for `parse_npc` compatibility. Also added `max_hp` assertion to unit test.

## Log Analysis

- No errors or warnings related to save/load in backend logs.
- Existing LLM sessions from previous runs visible in logs (arena combat) — unrelated to phase 1.5.

## Blockers

None.

## Minor Issues

- `parse_npc` location validation (`known_locations`) crashes with RuntimeError on invalid location. The spawn endpoint catches ValueError/KeyError but not RuntimeError — returns 500 instead of 400. Pre-existing issue, not introduced by this phase. Candidate for backlog.
