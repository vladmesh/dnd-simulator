# Task: Frontend Clickable Roll Breakdown

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 0 — Structured Dice & Roll Breakdown

## Description

Make attack events in the combat log expandable. Clicking an attack log entry reveals a structured breakdown of the roll: d20 with advantage dice, each modifier with its source, and damage components with individual die faces and reroll indicators.

### UX Design

**Collapsed (default):** Same as now — icon + text description. But attack events get a subtle expand chevron or cursor hint.

**Expanded:** Below the text line, a compact breakdown panel:

```
  d20: [14]  +3 STR  +2 prof  = 19 vs AC 15   HIT
      (advantage: kept 14, dropped 7)

  Damage: 8
    1d8 slashing [6]           weapon
    1d6 piercing  [3] [5̶→5]   sneak attack     (strikethrough on rerolled original)
    +2                         dueling
```

Key UI decisions:
- Individual dice shown in `[brackets]` like physical dice
- Rerolled dice: show original with strikethrough, arrow, new value: `[1̶→5]`
- Both advantage d20s shown when relevant
- Modifier sources right-aligned or in muted text
- Compact — no more than 3-5 lines for a typical attack

### Scope

- Attack events only (`entity_attack`). Other event types remain as-is.
- TypeScript types for the structured event data (`AttackRollData`, `DamageComponentData`, `DieRollData`).
- No new API calls — all data already arrives in `event.data`.

## Tests First

**Playwright E2E (or component tests if faster):**
- Attack event row is clickable (has expand control)
- Clicking toggles expanded state
- Expanded view shows d20 natural value
- Expanded view shows modifier components with source labels
- Expanded view shows total vs AC
- Expanded view shows hit/miss indicator
- Expanded view shows damage components with dice faces
- When advantage: expanded view shows both d20 values with "kept"/"dropped" labels
- When no `dice_detail` in data (legacy events): expand shows basic info without dice faces (graceful degradation)
- Non-attack events are NOT expandable

## Implementation

1. **`frontend/src/types/game.ts`** — Add TypeScript interfaces:
   ```typescript
   interface DieRollData {
     sides: number
     result: number
     original?: number | null  // pre-reroll value
   }

   interface AttackRollData {
     natural: number
     d20?: DieRollData
     d20_alt?: DieRollData
     components: Array<{ source: string; value: number; dice: string }>
     total: number
     advantage: boolean
     disadvantage: boolean
   }

   interface DamageComponentData {
     source: string
     dice: string
     dice_detail?: DieRollData[]
     amount: number
     type: string
   }
   ```

2. **`frontend/src/components/game/RollBreakdown.tsx`** — New component:
   - `AttackBreakdown` — renders d20 section + damage section
   - `DieDisplay` — renders `[N]` with reroll indicator
   - `ModifierLine` — renders `+N source`
   - Styling: muted background, monospace, compact

3. **`frontend/src/components/game/EventLog.tsx`** — Modify `DisplayEntryRow` for `kind: "event"`:
   - Attack events: wrap in expandable container (same pattern as `aggregated_move`)
   - Track expanded state in parent (same `expandedMoves` → rename to `expandedEntries` or add `expandedAttacks`)
   - Non-attack events: unchanged

4. **`frontend/src/lib/logProcessing.ts`** — Potentially add helper to detect expandable events.

## Acceptance Criteria

- [ ] Tests written and RED
- [ ] Attack events expandable with click
- [ ] Expanded view shows d20 roll with face value
- [ ] Expanded view shows both d20s on advantage/disadvantage
- [ ] Expanded view shows each modifier with source label
- [ ] Expanded view shows damage components with individual dice faces
- [ ] Rerolled dice show original value with visual indicator
- [ ] Graceful degradation for events without `dice_detail`
- [ ] Non-attack events remain non-expandable
- [ ] `make check` green (frontend tests pass)

## Status

`pending`
