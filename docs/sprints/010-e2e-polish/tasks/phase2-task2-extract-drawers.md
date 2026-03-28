# Task: Extract drawer sections into standalone components

**Date:** 2026-03-28
**Sprint:** 010-e2e-polish
**Phase:** 2 — ActionBar Decomposition

## Description

The three drawer blocks in ActionBar (consumables, class features, inventory) are each 20-40 lines of inline JSX with their own visibility logic and click handlers. Extract each into a dedicated component that owns its ActionDrawer usage and content rendering.

Target:
```
components/game/action-bar/
  ConsumableDrawer.tsx    — consumable items drawer (potions, scrolls, bombs)
  ClassFeatureDrawer.tsx  — class feature actions drawer (second_wind, etc.)
  InventoryDrawer.tsx     — equip/unequip weapon drawer (combat only)
```

Each component receives the minimal props it needs (actions, items, budget state, send callback, open/toggle state). The `openDropdown` state stays in ActionBar since it coordinates mutual exclusion across all drawers/dropdowns.

## Tests First

Write tests for each extracted drawer component in isolation. These verify the same behavior currently covered by ActionBar.test.tsx drawer suites, but targeted at the new components:

1. **ConsumableDrawer** — renders item count badge; clicking item sends `use_item` with correct `item_id`; respects disabled state when budget depleted
2. **ClassFeatureDrawer** — renders feature count; clicking feature sends action; shows cost badge (bonus_action styling)
3. **InventoryDrawer** — renders in combat mode; clicking equip option sends `equip` with `item_id`; does not render when no equip actions

These are product-level: "player clicks potion in drawer → use_item action sent with that potion's ID". Not "ConsumableDrawer calls onSend prop".

## Implementation

1. Create ConsumableDrawer.tsx — extract lines 268-291 from ActionBar, parameterize
2. Create ClassFeatureDrawer.tsx — extract lines 293-320
3. Create InventoryDrawer.tsx — extract lines 322-359
4. Update ActionBar.tsx to import and render these three components
5. Pass openDropdown/setOpenDropdown coordination as props
6. Existing ActionBar.test.tsx drawer suites should still pass (DOM structure unchanged)
7. `make check` green

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing ActionBar.test.tsx tests still pass (`make check`)
- [ ] Each drawer component < 150 lines
- [ ] ActionBar.tsx drawer section reduced to ~3 component renders

## Status

`pending`
