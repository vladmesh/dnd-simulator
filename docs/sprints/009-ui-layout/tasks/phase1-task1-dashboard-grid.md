# Task: Dashboard Grid Layout

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 1 — Dashboard Layout + Compact Log

## Description

Replace the current 2-column layout (EventLog flex-1 | SidebarTabs w-72) with a dashboard layout where all panels are visible simultaneously:

```
┌─────────────────────────────────────────────────────┐
│  Header (unchanged)                                  │
├─────────────────────────────────────────────────────┤
│  Compact Log: last 3-5 events, single strip          │
├─────────────────┬──────────────┬────────────────────┤
│  Nearby         │  Character   │  Location           │
│  (Perception    │  (PlayerStats│  (LocationPanel)    │
│   + TradePanel) │   w/ Invent.)│                     │
├─────────────────┴──────────────┴────────────────────┤
│  ActionBar (unchanged)                               │
└─────────────────────────────────────────────────────┘
```

Specific changes:

1. **GameScreen.tsx** — replace the flex row (log + sidebar) with a vertical stack: header → compact log → 3-col grid → action bar. The grid takes `flex-1 min-h-0` so it fills available space without page scroll.
2. **EventLog.tsx** — add a `compact` mode: renders last N events as a simple list (no virtualization). Keep the existing full mode for use in the overlay (task 2). In compact mode: `max-h-24 overflow-y-auto`, auto-scroll to bottom, `text-xs`.
3. **Remove SidebarTabs** — delete the component. Panels render directly in grid cells.
4. **Panel grid** — 3 equal columns. Each cell gets `overflow-y-auto min-h-0` so individual panels scroll independently. On screens < 1024px, stack vertically (responsive fallback).
5. **Combat mode** — for now, combat keeps the same 3-col layout. BattleMap + CombatPanel go into the left column replacing Perception. Combat layout redesign is a separate sprint.

## Tests First

Vitest component tests:

1. **All panels visible simultaneously:** Render GameScreen with a game state that has nearby entities, player stats, and location paths. Assert that Perception, PlayerStats, and LocationPanel are all in the DOM at the same time (no tab switching needed).
2. **Compact log shows recent events:** Render GameScreen with 10 log entries. The compact log strip shows the last few entries. Earlier entries are not visible (they'll be in the overlay added in task 2).
3. **No SidebarTabs in DOM:** Render GameScreen — assert SidebarTabs component is not rendered.
4. **Combat panels replace nearby column:** Enter combat state — BattleMap and CombatPanel render in the left column. Perception moves out or merges into CombatPanel's enemy list.

## Implementation

- `GameScreen.tsx`: restructure JSX. Use CSS grid (`grid grid-cols-3`) for the panel area. Compact log above the grid. ActionBar stays at bottom.
- `EventLog.tsx`: accept a `compact?: boolean` prop. When compact, slice the last N entries and render without virtualizer. When not compact, use existing virtualized renderer.
- Delete `SidebarTabs.tsx`.
- Panel columns: left = Perception + TradePanel (peaceful) or BattleMap + CombatPanel (combat), center = PlayerStats (includes InventoryPanel), right = LocationPanel.
- Each column: `overflow-y-auto` with flex constraints so they share vertical space.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] All three panels visible simultaneously — no tabs
- [ ] Compact log shows last few events in a strip
- [ ] Page does not scroll — panels scroll individually
- [ ] Works on screens ≥ 1024px
- [ ] Combat mode renders BattleMap + CombatPanel in left column

## Status

`pending`
