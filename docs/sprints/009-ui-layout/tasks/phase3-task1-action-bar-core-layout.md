# Task: Action Bar Core Layout + Cost Styling

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 3 — Action Bar Redesign + Potions

## Description

Restructure ActionBar from a flat list of all actions into a grouped layout with visual cost-type distinction. Backend sends `cost_type` per action so the frontend can style buttons by resource cost.

**Backend change:** `_awareness_to_dict` in `service/session.py` currently only sends `cost_type` when a creature has cost overrides (Cunning Action). Add `cost_type` to every action's info dict — the frontend needs it to style all buttons.

**Frontend changes:**

1. Add `cost_type` field to `ActionInfo` type (`types/game.ts`)
2. Create `categorizeActions()` pure utility (`lib/actionCategories.ts`) that takes `ActionInfo[]` + `ItemInfo[]` and returns groups:
   - **core**: attack, dodge, dash, disengage, flee, end_turn — always visible as buttons
   - **consumables**: items from `available_items` where `type === "potion"` (and future scroll/bomb types) — goes to drawer in task 2
   - **classFeatures**: second_wind, bless (and future class actions) — goes to drawer in task 2
   - **inventory**: equip/unequip variants — goes to drawer in task 2
   - **other**: say, wait, move — keep current rendering (text input, simple button, directional dropdown)
3. Restructure ActionBar to render groups in order: budget → core buttons → other → (drawer buttons from task 2) → end_turn
4. Style buttons by `cost_type`:
   - `action` — default (current secondary variant)
   - `bonus_action` — distinct accent style (amber/yellow tint or border)
   - `free` — ghost/subtle
   - `movement` — keep secondary
   - Depleted (budget shows 0 for that type) — muted/gray with visual indicator

Existing interaction patterns (target dropdown for attack, directional dropdown for move/dash, text input for say) are preserved — they just render in the correct group now.

## Tests First

**Backend** (`tests/unit/test_session_awareness.py` or similar):
- Action info dict for a basic creature includes `cost_type` field on every action (e.g., attack → "action", dodge → "action", say → "free")
- Creature with Rogue features: dash action has `cost_options` AND `cost_type` (base cost is "action", override is "bonus_action")

**Frontend** (`frontend/src/lib/__tests__/actionCategories.test.ts`):
- Given a combat action set (attack, dodge, dash, disengage, move, end_turn, use_item, equip, second_wind, say), categorizeActions returns correct buckets
- Given peaceful action set (say, wait, idle, use_item, equip), categorizeActions returns correct buckets
- Empty available_actions → all groups empty
- Unknown action names fall into "other" (forward-compatible)

**Frontend** (`frontend/src/components/game/__tests__/ActionBar.test.tsx`):
- Core combat buttons (attack, dodge, dash, disengage) render with correct data-cost-type attribute
- End turn always renders last
- Budget display present when budget exists in store
- Buttons with `cost_type: "bonus_action"` have distinct visual class
- When budget.actions === 0, action-cost buttons show depleted styling
- Existing behavior preserved: attack with single enemy sends action directly, attack with multiple enemies shows target dropdown

## Implementation

1. **Backend** — `service/session.py` line 74: add `"cost_type": ad.cost_type.value` to `action_info` dict
2. **Frontend type** — `types/game.ts`: add `cost_type?: string` to `ActionInfo`
3. **Utility** — new `lib/actionCategories.ts`: pure `categorizeActions(actions, items)` function returning `ActionGroups` type
4. **ActionBar** — refactor rendering loop: instead of iterating `available` flat, iterate `groups.core`, then `groups.other`, with `data-cost-type` attribute on buttons for styling. Drawers (task 2) get placeholder slots.
5. **CSS** — cost-type variants via Tailwind classes or `data-*` attribute selectors in the component

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Backend sends `cost_type` on every action in awareness
- [ ] Core buttons render in a distinct group, always visible
- [ ] Buttons visually differ by cost type (action vs bonus_action vs free)
- [ ] Depleted cost types show muted styling
- [ ] Attack target dropdown, move direction dropdown, say input all still work

## Status

`done`

## Developer Notes

Backend: added `"cost_type": ad.cost_type.value` to every action_info dict in `_awareness_to_dict`. One-line change.

Frontend:
- Added `cost_type?: string` to `ActionInfo` type
- Created `lib/actionCategories.ts` with `categorizeActions()` — pure function grouping actions into core/consumables/classFeatures/inventory/other/endTurn
- Restructured `ActionBar.tsx`: renders groups in order (core → other → consumables → classFeatures → inventory → endTurn last), adds `data-cost-type` and `data-depleted` attributes to all action buttons, bonus_action buttons get amber ring styling, depleted cost types get `data-depleted` attribute for CSS targeting
- All existing interaction patterns (target dropdown, directional dropdown, item dropdown, say input, wait) preserved unchanged
- Drawer slots for consumables/classFeatures/inventory are placeholders — task 2 will convert them
