# Task: Fix action bar display issues (raw names, cost labels, drawer clarity)

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 1 — Bug Sweep

## Description

Multiple frontend display bugs in the action bar:

1. **Raw snake_case action names** — `lay_on_hands`, `long_rest`, `short_rest` displayed as-is instead of localized labels. Missing i18n keys in `frontend/src/i18n/locales/{en,ru}/game.json`.

2. **Raw `bonus_action` in cost tooltip** — `costLabel()` in `ActionButton.tsx:24` falls back to raw string when `game:cost_bonus_action` key is missing.

3. **Mystery "3" button** — This is actually the InventoryDrawer count (`ActionDrawer.tsx:27`) showing 3 available equip/unequip actions. Not a bug per se, but drawers need title tooltips so users understand what the number means.

4. **`lay_on_hands` not in CLASS_FEATURE_ACTIONS** — `actionCategories.ts:5` only has `["second_wind", "bless"]`. Paladin's Lay on Hands falls into `other` group instead of the class features drawer.

## Tests First

No unit tests for i18n key presence — verify manually via E2E. But write a quick check:
1. Assert all ActionType values that have `CLASS_FEATURE_ACTIONS` categorization are in the frontend i18n keys (snapshot test or lint).
2. Verify `categorizeActions()` puts `lay_on_hands` in classFeatures after the fix.

## Implementation

1. **Add missing i18n keys** to `frontend/src/i18n/locales/en/game.json`:
   - `"lay_on_hands": "Lay on Hands"`
   - `"long_rest": "Long Rest"`
   - `"short_rest": "Short Rest"`
   - `"cost_action": "Action"`
   - `"cost_bonus_action": "Bonus Action"`
   - `"cost_reaction": "Reaction"`
   - `"cost_movement": "Movement"`
   - `"cost_free": "Free"`

2. **Add Russian translations** to `frontend/src/i18n/locales/ru/game.json`:
   - `"lay_on_hands": "Наложение рук"`
   - `"long_rest": "Длинный отдых"`
   - `"short_rest": "Короткий отдых"`
   - `"cost_action": "Действие"`
   - `"cost_bonus_action": "Бонусное действие"`
   - `"cost_reaction": "Реакция"`
   - `"cost_movement": "Передвижение"`
   - `"cost_free": "Бесплатно"`

3. **Add `lay_on_hands` to CLASS_FEATURE_ACTIONS** in `actionCategories.ts:5`.

4. **Add title attributes to drawer buttons** in `ActionDrawer.tsx` — tooltip explaining what the count means (e.g. "Class Features (1)", "Inventory (3)").

## Acceptance Criteria

- [ ] `lay_on_hands` shows as "Lay on Hands" / "Наложение рук"
- [ ] `long_rest`, `short_rest` show localized labels
- [ ] Cost type "bonus_action" shows as "Bonus Action" / "Бонусное действие"
- [ ] Drawer buttons have descriptive title tooltips
- [ ] `lay_on_hands` appears in class features drawer, not in main bar
- [ ] Existing tests still pass (`make check`)

## Status

`pending`
