# Task: Cunning Action Cost Choice (Backend + Frontend)

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 3 — Cunning Action Choice & SA Faction Check

## Description

Rogue's Cunning Action lets them use Dash/Disengage as a bonus action instead of an action. The backend cost infrastructure (`action_cost()` + `cost_mode` param + `CostOverride`) already works. The session serializer already emits `cost_options` on actions with overrides. But:

1. DASH/DISENGAGE ActionDefs lack a `cost_mode` ParamDef — brains can't pass it.
2. Frontend `ClassFeatureDrawer` and `ActionButton` ignore `cost_options` — no UI to pick cost.
3. RuleBrain doesn't know about cost_mode — when a rogue wants to Dash as bonus action, it can't.

Wire end-to-end: add ParamDef, update frontend to show cost choice, teach RuleBrain to prefer bonus_action cost when available.

## Tests First

**Backend:**
1. **Rogue Dash as bonus action** — Rogue with Cunning Action sends `dash` with `cost_mode=bonus_action`. Budget deducts bonus action, not action. Movement budget increases by speed.
2. **Rogue Dash as regular action** — Same rogue sends `dash` with `cost_mode=action` (or no cost_mode). Budget deducts action as normal.
3. **Non-rogue Dash rejects cost_mode** — Fighter sends `dash` with `cost_mode=bonus_action`. Raises error (no override available).
4. **Rogue Disengage as bonus action** — Rogue sends `disengage` with `cost_mode=bonus_action`. Budget deducts bonus action.
5. **RuleBrain prefers bonus action Dash** — Rogue RuleBrain with both action and bonus_action available chooses Dash with `cost_mode=bonus_action`.

**Frontend:**
6. **Dash button shows cost options for Rogue** — When action has `cost_options`, button offers both costs. Clicking sends the selected `cost_mode` param.
7. **Dash button is simple for Fighter** — When action has no `cost_options`, button behaves as before (single click, no choice).

## Implementation

1. **ParamDef on DASH/DISENGAGE** (`core/action_defs.py`): Add `ParamDef("cost_mode", "string", "Cost variant: action or bonus_action", required=False)` to both DASH and DISENGAGE ActionDef params.

2. **Frontend cost choice** (`ActionButton.tsx` or `ClassFeatureDrawer.tsx`): When `action.cost_options` is present and has >1 entries, render a split button or dropdown. On click, send `cost_mode` param matching the selected option's `cost_type`.

3. **RuleBrain cost_mode** (`core/brain.py`): When RuleBrain picks DASH or DISENGAGE for a creature with cost overrides, set `cost_mode=bonus_action` to conserve the regular action for attacks.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Rogue can Dash/Disengage as bonus action via cost_mode param
- [ ] Frontend shows cost choice on actions with cost_options
- [ ] RuleBrain uses bonus_action cost when available
- [ ] Non-rogues unaffected — no cost_mode, no UI change

## Status

`pending`
