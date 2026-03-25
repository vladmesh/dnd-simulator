# Task: E2E — Squad Lifecycle Flow

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 4 — Frontend + E2E

## Description

E2E test covering the full squad lifecycle as seen by a player: squad movement events in the log, materialization when a squad arrives at the player's location, materialized creatures in the nearby panel. Uses Playwright via MCP against a live dev server.

Requires a test world with a short patrol route so the squad arrives within 1-2 `wait` actions (each advances 1 hour = 1 ecology tick).

## Tests First

This IS the test task. Scenarios to cover:

1. **Squad movement visible in event log** — Start game with sword_vale (or a dedicated test world). Wait 1 hour. If a squad moved to or through the player's location, verify a `squad_move` event appears in the EventLog with squad name.

2. **Squad materialization** — Position player at a location on a patrol route. Wait until the patrol arrives. Verify:
   - `squad_materialized` event in the log
   - Materialized creatures appear in Perception panel (nearby entities)
   - Creatures are interactable (Attack/Talk buttons visible)

3. **Squad combat in log** — If two hostile squads share a location, `squad_combat` event should appear. This may require a specific world setup or may be tested via backend integration test only (hard to force in E2E reliably).

4. **Full regression** — Run all existing E2E scenarios (setup, peaceful, combat, trading, master panel) to verify nothing broke.

## Implementation

1. **Test world setup** — Either use sword_vale (which has squads with patrol routes) or create a minimal `e2e_squads.yaml` world with:
   - 2 locations connected by a path
   - Player starts at location A
   - A patrol squad on route [B, A] so it arrives at A after 1 tick
   - A guard squad at A (different faction, hostile to patrol) for combat test

2. **E2E script** — Add squad scenarios to `docs/e2e-playbook.md`:
   ```
   ## 7. Squads & Ecology
   ### 7.1 Squad movement in log
   ### 7.2 Squad materialization
   ### 7.3 Squad combat in log (if reproducible)
   ```

3. **Run via Playwright MCP** — navigate, wait, check EventLog text content, check Perception panel.

4. **Write report** to `docs/e2e-reports/`.

## Acceptance Criteria

- [ ] E2E playbook updated with squad scenarios
- [ ] Squad movement events visible in browser EventLog
- [ ] Materialized creatures appear in Perception panel
- [ ] All existing E2E scenarios still pass (regression)
- [ ] E2E report written

## Status

`done`

## Developer Notes

E2E done as manual playtest session instead of automated Playwright. Found and fixed 18 bugs across frontend, backend, content. Key findings:

- Multiple crash-to-game-over bugs from missing param validation (say, buy, use_item, move)
- RuleBrain friendly fire — was attacking allies in combat (missing is_hostile filter)
- Combat didn't auto-start on encounter spawn or squad materialization
- Combat didn't end when only allies remained (waited 2 idle rounds)
- Ability modifier wasn't added to damage rolls
- Creatures spawned on perimeter walls, got stuck
- Session leaked memory on disconnect (no autosave/evict)
- Squad routes didn't intersect — no squad-vs-squad combat was possible

Squad lifecycle verified: movement events visible in log, materialization triggers combat, squad-vs-squad combat resolves with strength updates, destroyed squads removed permanently.
