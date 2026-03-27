# Task: Tabbed Sidebar

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 1 — Fixed Viewport + Log Formatting

## Description

Replace the current right sidebar that switches wholesale between combat/peaceful panels with a tabbed layout. Tabs allow the player to switch between context panels manually while auto-selecting the most relevant tab on mode change.

**Tabs (peaceful mode):**
- **Nearby** (default) — Perception panel (NPC list with actions)
- **Location** — LocationPanel (current location, paths)
- **Character** — PlayerStats + InventoryPanel

**Tabs (combat mode):**
- **Map** (default) — BattleMap + CombatPanel
- **Nearby** — Perception (enemies with distance/direction)
- **Character** — PlayerStats + InventoryPanel

TradePanel stays where it is conceptually but moves into the Nearby tab — it only shows when merchants are present, so it fits naturally under the NPC list.

When mode changes (peaceful→combat or back), auto-select the default tab for that mode. User can manually switch tabs at any time.

## Tests First

This is a pure frontend task — tests are Playwright E2E:

1. **Tab switching in peaceful mode:** Load game, sidebar has 3 tabs, clicking each tab shows the corresponding panel content. Default tab is "Nearby".
2. **Tab switching in combat mode:** Enter combat, sidebar shows Map/Nearby/Character tabs. Default is "Map". BattleMap is visible.
3. **Auto-switch on mode change:** Start in peaceful (Nearby tab), enter combat → Map tab auto-selected. Combat ends → Nearby tab auto-selected.
4. **Trade panel in Nearby tab:** When merchant is nearby in peaceful mode, TradePanel is visible within the Nearby tab below the NPC list.

## Implementation

- Create a `SidebarTabs` component wrapping the existing panels with a tab bar.
- Use a simple state-driven tab system (no library needed — just active tab state + conditional render).
- Tab bar: compact, horizontal, at the top of the sidebar. Use `text-xs uppercase` styling consistent with existing sidebar headers.
- `GameScreen.tsx`: replace the current `{isCombat ? (...) : (...)}` conditional with `<SidebarTabs />`.
- Wire mode changes to reset the active tab via `useEffect` on `mode`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Sidebar has tabs in both peaceful and combat modes
- [ ] Tab auto-switches on mode change
- [ ] TradePanel lives within Nearby tab

## Status

`done`

## Developer Notes

Created `SidebarTabs` component that manages tab state independently for peaceful and combat modes. Peaceful mode: Nearby (Perception + TradePanel) / Location / Character tabs. Combat mode: Map (BattleMap + CombatPanel) / Nearby / Character tabs. `useEffect` on `isCombat` resets to default tab on mode change. GameScreen simplified — no longer imports individual sidebar panels, just renders `<SidebarTabs />`. All existing i18n keys reused (no new translations needed). 9 component tests cover tab switching, defaults, and auto-switch on mode change.
