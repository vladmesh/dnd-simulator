# Task: Render DisplayEntry in EventLog

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 2 — Log Formatting

## Description

Update EventLog component to consume `DisplayEntry[]` from `processLogEntries()` instead of raw `LogEntry[]`. Render icons inline, turn headers as visual separators, and aggregated moves with expandable sub-entries. Adjust virtualizer for variable-height rows.

## Tests First

Scenarios to cover (Playwright E2E or component tests):

1. **Icons render**: attack event in log shows a sword icon element next to the description text
2. **Turn header renders**: in combat, a turn header separator appears between different creatures' turns showing the creature's name
3. **Aggregated move renders collapsed**: 3 consecutive goblin moves show as single "Goblin moved (25 ft)" line with an expand indicator
4. **Aggregated move expands**: clicking the expand indicator reveals the individual move descriptions
5. **Compact mode uses processing**: compact log strip shows icons and colors, aggregated moves collapsed
6. **Virtualization stable at 200+ entries**: full log with 200 mixed entries (including headers and aggregated moves) scrolls without layout glitches — virtualizer handles variable heights

## Implementation

After tests are red:

- Update `CompactLog` and `FullLog` to call `processLogEntries(log)` and iterate `DisplayEntry[]`
- Remove `EVENT_COLORS` import from EventLog (now lives in logProcessing)
- Render per `kind`:
  - `"event"` — icon (lucide-react component) + colored description (same as before but with icon)
  - `"turn_header"` — horizontal rule or styled div with actor name, distinct background, slightly taller
  - `"aggregated_move"` — collapsed: icon + summary text + chevron; expanded: sub-entries indented below
- Virtualizer: use `measureElement` for dynamic row heights (turn headers ~32px, regular ~24px, expanded aggregated varies)
- Aggregated move expand/collapse: local state per entry (useState or a Set of expanded IDs)

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] All event types show icons in both compact and full log
- [ ] Turn headers visually separate combat turns
- [ ] Aggregated moves collapse/expand correctly
- [ ] Virtualization works with 200+ entries including mixed types

## Status

`done`

## Developer Notes

Rewrote EventLog.tsx to consume `DisplayEntry[]` from `processLogEntries()`. Created `ICON_MAP` (string → LucideIcon component) for all 27 event types. `DisplayEntryRow` renders three variants: regular event (icon + colored text), turn header (horizontal rule with actor name), aggregated move (expandable with chevron toggle). Both CompactLog and FullLog use the same `DisplayEntryRow`. Virtualizer `estimateSize` is dynamic based on entry kind and expanded state. Removed old `EVENT_COLORS` from EventLog — now imported from `logProcessing.ts`.
