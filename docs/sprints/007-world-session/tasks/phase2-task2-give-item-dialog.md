# Task: Give Item Dialog UI

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 2 — Master Controls + Give Item UI

## Description

Add a "Give Item" button and dialog to the creature panel. When editing an existing creature, the master should be able to:

1. See what the creature currently has (inventory + equipped weapon/armor/shield) — read-only display.
2. Click "Give Item" to open a dialog.
3. Select item type (weapon / potion / armor / shield).
4. Fill in type-specific fields:
   - **Weapon:** weapon_id, attack_name, category (simple/martial), damage (dice + type), reach, ability override, is_magic, is_finesse.
   - **Potion:** heal_dice (e.g. "2d4+2").
   - **Armor / Shield:** deferred to backlog if schema doesn't exist yet — check `GiveItemRequest`.
5. Submit → calls `api.master.giveItem()` → refreshes creature detail → shows new item in inventory.

The dialog should be a new component `GiveItemDialog.tsx` in `frontend/src/components/master/`. It's opened from `CreatureForm` (edit mode only) or from `CreatureList` row actions.

## Tests First

No frontend test runner — this task is verified by:
- TypeScript compilation (`npm run build`)
- Manual smoke test: open creature edit → give weapon → see it in inventory
- E2E coverage in task 3

## Implementation

1. **`GiveItemDialog.tsx`** — Dialog component with:
   - Item type selector (tabs or dropdown).
   - Dynamic form fields based on selected type.
   - Name field (required for all types).
   - Submit calls `api.master.giveItem()`, shows toast on success/error.
2. **Inventory display in `CreatureForm`** — when editing, show a read-only section listing inventory items and equipped weapon/armor. Use the new fields from `CreatureResponse`.
3. **Entry point** — "Give Item" button in `CreatureForm` (edit mode) opens the dialog. Alternatively, a small icon button in `CreatureList` row actions.
4. **i18n** — add translation keys for new UI strings to the master namespace.

## Acceptance Criteria

- [ ] "Give Item" button visible when editing a creature
- [ ] Dialog shows correct fields for weapon vs potion
- [ ] Submitting a weapon creates it on the creature (visible in inventory after refresh)
- [ ] Submitting a potion creates it on the creature
- [ ] Inventory section shows current items and equipped weapon
- [ ] TypeScript compiles cleanly
- [ ] Existing tests still pass (`make check`)

## Status

`pending`
