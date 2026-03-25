# Task: Frontend Squad Event Rendering

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 4 — Frontend + E2E

## Description

Frontend `EventType` union and `EventLog` component don't know about squad events. Add the new event types and assign them distinct visual styling so squad activity is visible in the game log.

Materialized squad creatures are regular `Creature` entities with `active=True` — they already appear in `nearby` via `PeacefulAwareness.nearby` / `CombatAwareness.nearby`. No changes to Perception or CombatPanel needed.

## Tests First

No unit tests for frontend in this project — verification is visual via E2E (Task 3). Instead, validate by:

1. **TypeScript compiles** — `squad_move`, `squad_combat`, `squad_materialized`, `squad_dematerialized` are valid `EventType` values. No `tsc` errors.

2. **EventLog renders squad events with correct colors** — manually confirmed during E2E, or via a snapshot/component test if one exists.

## Implementation

1. **`frontend/src/types/game.ts`** — add to `EventType` union:
   ```typescript
   | "squad_move"
   | "squad_combat"
   | "squad_materialized"
   | "squad_dematerialized"
   ```

2. **`frontend/src/components/game/EventLog.tsx`** — add color mappings:
   - `squad_move` → muted (routine movement, like `entity_move`)
   - `squad_combat` → orange-400 (notable, like `combat_started`)
   - `squad_materialized` → yellow-400 (warning — creatures appearing)
   - `squad_dematerialized` → muted (departure, low priority)

## Acceptance Criteria

- [ ] `EventType` includes all four squad event types
- [ ] EventLog renders squad events with distinct colors
- [ ] `tsc` compiles without errors
- [ ] No changes to Perception or CombatPanel (materialized creatures use existing entity flow)

## Status

`done`

## Developer Notes

Minimal change — 4 event types added to the union, 4 color mappings added. tsc clean. No changes to Perception/CombatPanel as planned.
