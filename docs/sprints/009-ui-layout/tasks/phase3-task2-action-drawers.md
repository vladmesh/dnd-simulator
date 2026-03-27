# Task: Consumable, Class Feature, and Inventory Drawers

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 3 — Action Bar Redesign + Potions

## Description

Add popup drawers to the action bar for grouped actions: consumables (potions, scrolls, bombs), class features (Second Wind, Bless), and inventory management (equip/unequip). Each drawer is a single toggle button on the action bar that opens a popup above it showing the available actions in that category.

**Design rationale:** Individual potion buttons don't scale — 3 potions + 2 scrolls + a bomb = 6 extra buttons. A single "Items" drawer keeps the bar clean regardless of inventory size, with 1 extra click cost. Same logic for equip/unequip (6+ action types) and class features.

**Drawer UI pattern:**
- Toggle button on the action bar with icon + count badge (e.g., "🧪 3" for 3 consumables)
- Click opens a popup anchored above the button (same pattern as existing dropdowns, but wider)
- Each item in the popup is a button: click = execute action immediately (use_item with item_id, second_wind, equip with weapon_id, etc.)
- Items show name + brief description (e.g., "Healing Potion — heals 2d4+2 HP")
- Popup closes on action dispatch, outside click, or Escape
- Only one drawer open at a time (opening one closes others + any core action dropdowns)

**Three drawers:**

1. **Consumables** — available when `categorizeActions().consumables` is non-empty. Each entry is an item from `available_items` that's a consumable. Click sends `use_item` with `item_id`. Shows item name and description.

2. **Class Features** — available when `categorizeActions().classFeatures` is non-empty. Each entry is an action (Second Wind, Bless, etc.). Shows action name, description, and cost type. For actions with `cost_options` (Cunning Action: Dash as bonus action), show the alternative cost option.

3. **Inventory** — available when `categorizeActions().inventory` is non-empty. Shows equip/unequip actions. Weapons show weapon name + stats. Armor/shield show name + AC. Reuses existing weapon dropdown logic but in the drawer popup instead of inline.

**Button visibility:** Drawer buttons only render when their category has items. Empty category = no button. In peaceful mode, InventoryPanel handles equip/unequip, so the inventory drawer only appears in combat.

## Tests First

**Frontend** (`frontend/src/components/game/__tests__/ActionBar.test.tsx`, extending from task 1):

- When available_items has 2 potions, a consumable drawer button renders with count "2"
- Clicking the consumable drawer button opens a popup showing both potion names
- Clicking a potion in the popup sends `use_item` with the correct `item_id`
- Popup closes after action is sent
- When available_items is empty, no consumable drawer button renders
- When second_wind is in available_actions, class features drawer button renders
- Clicking Second Wind in the class features popup sends `second_wind` action
- Opening consumable drawer closes class features drawer (and vice versa)
- Opening a drawer closes any open core action dropdown (attack target dropdown, etc.)
- Escape closes open drawer
- In peaceful mode, inventory drawer does not render (InventoryPanel handles equip/unequip)
- In combat mode with equip action available + weapons in items, inventory drawer renders

## Implementation

1. **ActionDrawer component** — generic `ActionDrawer` component: `{ icon, label, count, children, isOpen, onToggle }`. Renders the toggle button + popup container. Reuse across all three drawers.
2. **ConsumableDrawer** — filters `available_items` for consumables (type = potion, and future types). Maps each to a button that sends `use_item`.
3. **ClassFeatureDrawer** — maps `groups.classFeatures` actions to buttons. Shows cost type badge. Handles `cost_options` display for multi-cost actions.
4. **InventoryDrawer** — maps `groups.inventory` actions to buttons. Reuses weapon/armor selection logic from current ActionBar (the existing equip dropdown code moves here).
5. **ActionBar integration** — after core buttons and "other" group, render the three drawer buttons in a visually separated section (divider or gap). Coordinate open state: only one drawer/dropdown open at a time.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Consumable drawer shows all consumable items, 1 click = use
- [ ] Class feature drawer shows available class abilities with cost type
- [ ] Inventory drawer shows equip/unequip options in combat
- [ ] Only one drawer/dropdown open at a time
- [ ] Empty categories don't render drawer buttons
- [ ] Drawers close on action, outside click, and Escape
- [ ] Works for Fighter (Second Wind in class features) and Rogue (no class feature drawer if no resource-based abilities available)

## Status

`pending`
