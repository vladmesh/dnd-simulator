# Task: processLogEntries Transform

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 2 — Log Formatting

## Description

Create a pure transform function `processLogEntries(entries: LogEntry[]): DisplayEntry[]` that converts raw log entries into display-ready entries with icons, turn headers, and aggregated moves. Sync frontend `EventType` with backend (add missing types). Move `EVENT_COLORS` out of EventLog into this module alongside an `EVENT_ICONS` mapping.

## Tests First

Scenarios to cover:

1. **Icon mapping**: every EventType produces a DisplayEntry with the correct icon identifier (e.g. `entity_attack` → `"swords"`, `entity_say` → `"message-circle"`, `entity_move` → `"footprints"`, `entity_died` → `"skull"`, `combat_started` → `"flame"`, `weather_changed` → `"cloud-sun"`)
2. **Move aggregation**: 3 consecutive `entity_move` events from the same `actor_id` with `distance_ft` in data (5, 10, 10) → single `AggregatedMoveEntry` with total 25 ft and 3 sub-entries preserved
3. **Move aggregation breaks on actor change**: move A, move A, move B → aggregated(A, 2 moves), regular(B)
4. **Move aggregation breaks on non-move event**: move A, attack A, move A → regular move, attack, regular move (no aggregation across interruption)
5. **Dash included in aggregation**: `entity_move` then `entity_dash` from same actor → single aggregated entry
6. **Single move not aggregated**: lone `entity_move` stays as regular entry, not wrapped in aggregation
7. **Turn headers in combat**: events with actor_ids [A, A, B, B, A] → turn header before first A group, before B group, before second A group
8. **No turn headers for null actor_id**: `weather_changed` (no actor_id) between combat events doesn't produce a turn header
9. **No turn headers outside combat**: peaceful events with changing actor_ids don't get turn headers (turn headers only appear between `combat_started` and `combat_ended`)
10. **Color mapping**: every EventType maps to a Tailwind color class string

## Implementation

After tests are red:

- Create `frontend/src/lib/logProcessing.ts`
- Define `DisplayEntry` discriminated union: `{ kind: "event", entry: LogEntry, icon: string, colorClass: string }` | `{ kind: "turn_header", actorId: string, actorName: string }` | `{ kind: "aggregated_move", actorId: string, actorName: string, totalDistanceFt: number, entries: LogEntry[], icon: string, colorClass: string }`
- `EVENT_ICONS: Record<EventType, string>` — lucide-react icon names
- `EVENT_COLORS: Record<EventType, string>` — moved from EventLog.tsx
- `processLogEntries()` — single pass: track combat state (toggle on combat_started/combat_ended), track last actor_id for turn headers, accumulate consecutive moves for aggregation
- Add missing EventType values to `frontend/src/types/game.ts`: `entity_disengage`, `entity_second_wind`, `entity_equip`, `entity_unequip`, `entity_buy`, `entity_sell`, `encounter_spawned`

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Every EventType has an icon and color mapping (no fallback to "default" needed)
- [ ] Aggregation handles edge cases (single move, mixed actors, dash+move)
- [ ] Turn headers only appear within combat sequences

## Status

`pending`
