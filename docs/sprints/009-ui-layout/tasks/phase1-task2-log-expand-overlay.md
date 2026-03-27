# Task: Log Expand Overlay

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 1 — Dashboard Layout + Compact Log

## Description

Add an expand/collapse mechanism to the compact log strip from task 1. When expanded, the full event log renders as an overlay on top of the dashboard with the existing virtualized renderer.

**Compact strip:** Shows an expand button (▼ or "Show log"). Clicking it opens the overlay.

**Overlay:** Full-viewport overlay (below header, above action bar) with semi-transparent backdrop. Contains the full EventLog with virtualization, auto-scroll to bottom. Close via:
- Close button (✕) in overlay header
- Escape key
- Click on backdrop

The overlay is a simple portal or absolutely-positioned div — no routing, no modals library.

## Tests First

Vitest component tests:

1. **Expand button present in compact log:** Render GameScreen — the compact log strip contains a button to expand.
2. **Clicking expand shows overlay with full log:** Click the expand button — an overlay appears containing all log entries (not just the last N). The overlay covers the panel grid area.
3. **Close overlay via button:** With overlay open, click the close button — overlay disappears, compact log strip is visible again.
4. **Close overlay via Escape:** With overlay open, press Escape — overlay closes.

## Implementation

- `EventLog.tsx`: when `compact` mode, render an expand button (chevron-down icon from lucide-react).
- New `LogOverlay.tsx` component (or inline in EventLog): absolutely positioned div covering the grid area. Uses the non-compact EventLog (virtualized) inside. Has a header with "Event Log" title and close button.
- State: `logExpanded` boolean in GameScreen (local state, not store — it's pure UI).
- Backdrop: `bg-background/80 backdrop-blur-sm` for readability.
- Escape handler: `useEffect` with `keydown` listener when overlay is open.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Compact log has visible expand button
- [x] Overlay shows full virtualized log
- [x] Overlay closes via button, Escape, and backdrop click
- [x] Overlay does not affect ActionBar or Header visibility

## Status

`done`

## Developer Notes

Created `LogOverlay.tsx` — absolutely positioned over the panel grid area (inside a `relative` wrapper). Uses the non-compact `EventLog` with full virtualization. ChevronDown expand button added to compact log strip. Overlay has backdrop blur, Escape/close-button/backdrop-click dismiss. i18n keys added for "Event Log" / "Журнал событий". 4 new tests cover expand button presence, overlay open, close via button, close via Escape.
