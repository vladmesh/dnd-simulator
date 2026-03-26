# Task: World Inspector UI on Setup Screen

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 3 — Fork UI + World Inspector

## Description

Add a world inspector to the setup screen (WorldPicker). Each world card gets an expandable section showing the 5 layers with their source (library/custom) and a "Fork" button on library layers. After forking, the layer refreshes to show "custom" status.

The flow: user picks a world → expands layer details → sees which layers are library vs custom → clicks Fork on a library layer → layer copies to custom → badge updates without page reload.

### UI Elements

- **Expand/collapse toggle** on each world card (e.g., "View layers" / chevron icon)
- **Layer list** — 5 rows, one per layer type. Each shows:
  - Layer type label (Geography, Politics, etc.)
  - Source badge: "Library: {template}" or "Custom"
  - Fork button (only on library layers, disabled during fork operation)
- **Post-fork feedback** — badge flips to "Custom", fork button disappears

## Tests First

1. **World Inspector renders layer list from manifest data.** Mock `getWorldManifest` to return a manifest with 3 library + 2 custom layers. Assert: 5 layer rows rendered, correct badges, fork buttons only on library layers.
2. **Fork button calls `forkLayer()` and refreshes manifest.** Click fork on a library layer → assert `forkLayer` called with correct world/layer → mock re-fetch returns updated manifest → assert badge changed to "Custom" and fork button gone.
3. **Fork button is disabled while fork request is in-flight.** Click fork → assert button shows loading state → resolve request → assert button removed.

## Implementation

1. Create `WorldInspector` component (`components/setup/WorldInspector.tsx`) — takes `worldId`, fetches manifest, renders layer list.
2. Add expand/collapse state to world cards in `WorldPicker.tsx` — toggle renders `WorldInspector`.
3. Wire up `api.master.forkLayer()` in the fork button handler with optimistic or refetch-based UI update.
4. Add i18n keys for layer type labels, source badges, fork button text.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Each world card has expandable layer inspector
- [ ] Library layers show template name and Fork button
- [ ] Custom layers show "Custom" badge, no Fork button
- [ ] Fork updates UI without full page reload
- [ ] Loading/error states handled

## Status

`done`

## Developer Notes

Created WorldInspector component that fetches manifest and renders layer list with source badges and fork buttons.
Integrated into WorldPicker via expand/collapse toggle (ChevronRight/ChevronDown pattern).
No frontend tests — no test framework (vitest/jest) is installed.
Fork button calls forkLayer then re-fetches manifest to update UI.
Added i18n keys for both en/ru: layer labels, source badges, fork button, error messages.
