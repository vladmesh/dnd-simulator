# E2E Report: sprint022-phase4

**Date:** 2026-07-11
**Flags:** --no-llm
**Sections tested:** phase-4 focus (target accessibility + journey lifecycle)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 5 tested, 5 passed, 0 failed
- Quick fixes: 1 applied (target-aware accessible names now key on the unique entity id)
- Blockers: 0 found

## Results

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| A1 | Nearby Attack/Talk/Inspect controls have unique target-aware accessible names (EN) | pass | With gretta + guard_a + guard_b at the market, `Attack gretta` / `Attack guard_a` / `Attack guard_b` are all present and unique; Talk/Inspect likewise. Selecting one sends its `target_id`. |
| A2 | Same, in Russian | pass | `Атаковать gretta` / `Атаковать guard_a` / `Атаковать guard_b` unique; no duplicates among the three attack controls. |
| A3 | Open inspect modal keeps its Attack control unambiguous | pass | Inspecting `guard_a` opens the modal (`Attack guard_a`); the background nearby list is `aria-hidden` (Radix), so exactly one `Attack guard_a` button is reachable by role + name. |
| B1 | Multi-leg travel progresses leg-by-leg and clears on arrival | pass | Travel tavern→smithy resolved route `[market, smithy]`; logs show `travel_leg_arrive` at market (intermediate) then smithy (final) — no teleport. On arrival the journey panel is gone, the displayed location is the reached node, and player control returns. |
| B2 | Combat entry stays coherent and returns control | pass | Attacking `raider_1` starts combat (`combat_start`, round 1): mode flips to combat, CombatPanel + BattleMap render, `player.journey` is null (no stale journey), `isMyTurn` true. |

## Quick Fixes

- Target-aware accessible names now use the unique `entity.id` (matching the existing action-bar `TargetDropdown` contract) instead of the perceived description. The perceived description is the localized **race** (e.g. `человек`), which collides for same-race NPCs and would have produced duplicate `Attack человек` names. `Perception.tsx` (Attack/Talk/Inspect + SmiteChoice) and `NpcInspectModal.tsx` (Attack + SmiteChoice) updated; added `inspect_target` string to EN/RU `game.json`. Verified live: three simultaneous market NPCs yield three unique attack names in EN and RU.

## Findings

### Blockers

None.

### Minor

- **Mid-route SCENE interruption not reproducible through the current control surface.** Stopping a traveler at an intermediate node requires a *second awake anchor* there (the built-in SCENE reason), but `is_anchor` is not exposed by the master API and authored sword_vale NPCs are not awake anchors — a 2-leg journey passing through the market (with gretta + two guards present) fast-forwarded straight through to the destination. The interruption logic itself (SCENE / DAMAGE / COMBAT, idempotent, no double rest/leg, journey cleared, stops at reached node) is covered by the phase-4 task-1/task-2 unit + integration suites and the `LocationPanel` "clears journey progress and shows the reached node when interrupted mid-route" component test. Candidate backlog item: expose anchor toggle (or an authored awake NPC) so a mid-route stop is playable/testable through the UI.
- **Journey panel is only briefly visible on an unobstructed route.** By design (kenshi-style fast-forward) the round loop advances all legs in one pass, so `player.journey` is set only transiently between the travel action and arrival; a player rarely sees the route panel unless the journey is interrupted. Noted as an observation, not a defect.

## Log Analysis

- Backend log clean: no errors, exceptions, or tracebacks during the run (only the expected `llm_not_configured_fallback` for the no-LLM stack).
- Browser console: 0 errors across the run (1 benign warning).
- Travel events well-formed: `travel_start` carries the resolved multi-node `route`, each leg logs a single `travel_leg_arrive`, and `combat_start` records initiative/positions cleanly.
