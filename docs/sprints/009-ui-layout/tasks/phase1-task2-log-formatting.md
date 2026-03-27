# Task: Log Formatting — Turn Headers, Colors, Movement Aggregation

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 1 — Fixed Viewport + Log Formatting

## Description

Transform the event log from a flat list of monochrome lines into a structured, readable combat narrative. Three changes:

### 1. Turn/Round headers in combat

When events arrive, detect "turn boundaries" — consecutive events from the same `actor_id` are one turn. Insert visual separators between turns: a small header with the creature name (e.g. "— Goblin 1 —"). Round boundaries (detected by `combat_started` / `combat_ended` events or round number changes) get a more prominent divider.

This is frontend-only grouping logic over the existing event stream — no backend changes.

### 2. Color coding + icons

Expand the existing `EVENT_COLORS` map to cover all event types and add Lucide icons:
- Attack (sword icon, red), damage numbers bold
- Movement (footsteps, muted), dodge/flee (yellow)
- Speech (message icon, blue)
- Healing/potion (heart icon, green)
- Combat start/end (crossed swords / checkmark, orange/green)
- Equipment (backpack, muted)
- Trade (coins, muted)
- Death (skull, bold red)

### 3. Movement aggregation

Consecutive `entity_move` events from the same `actor_id` should be collapsed into a single entry: "Goblin 1 moved (25 ft)" with a `<details>` expander showing individual steps. This is the biggest visual noise reducer in combat.

## Tests First

Playwright E2E:

1. **Turn headers visible in combat:** Start combat, play through a round. Log shows creature name headers separating different creatures' actions.
2. **Movement aggregation:** NPC moves multiple times in a turn. Log shows single aggregated movement entry, not 5 separate "moved 5 ft" lines.
3. **Aggregated entry expands:** Click/expand the aggregated movement entry → see individual steps.
4. **Color coding visible:** Attack events have red styling, movement is muted, speech is blue. (Check CSS classes or computed styles.)

## Implementation

- **Log processing layer:** Add a `processLogEntries()` function that transforms raw `LogEntry[]` into `DisplayEntry[]` — a richer type that includes turn headers, aggregated groups, and display metadata (icon, color class). This runs in a `useMemo` over the log array.
- **`DisplayEntry` types:** `{ type: "event", entry, colorClass, icon }` | `{ type: "turn_header", actorName }` | `{ type: "aggregated_move", totalFt, actorName, children: LogEntry[] }`.
- **Virtualizer integration:** The virtualizer now iterates over `DisplayEntry[]` instead of raw `LogEntry[]`. Turn headers and aggregated entries are separate virtual rows.
- **Icons:** Import from `lucide-react` (already a dependency). Render inline before the event text, size-3.
- **Aggregation logic:** Walk the log entries. When you see consecutive `entity_move` from the same `actor_id`, collect them. Extract distance from `data.distance_ft` field on the event (check backend sends this).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Turn headers appear between different creatures' turns in combat log
- [ ] Movement events are aggregated into single entries
- [ ] All event types have appropriate colors and icons
- [ ] Log remains performant with virtualizer (no regression on 200+ events)

## Status

`pending`
