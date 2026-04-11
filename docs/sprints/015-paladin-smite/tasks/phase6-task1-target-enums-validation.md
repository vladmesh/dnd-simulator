# Task: TargetMode/TargetScope Enums + Validation

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 6 — Action Target Scope

## Description

Replace `ActionDef.targeted: bool` with `TargetMode` and `TargetScope` enums. Update all action registrations, validation, and serialization.

**New enums in `core/action_defs.py`:**

```python
class TargetMode(StrEnum):
    NONE = "none"       # no creature target (equip, say, wait, etc.)
    SELF = "self"       # target = caster, implicit (dodge, dash, second_wind)
    SINGLE = "single"   # pick 1 creature (attack, lay_on_hands)

class TargetScope(StrEnum):
    HOSTILE = "hostile"  # enemies only
    ALLY = "ally"        # allies + self
    ANY = "any"          # everyone + self
```

MULTI, POINT, DIRECTION deferred — not needed by any current action.

**ActionDef changes:**
- Remove `targeted: bool`
- Add `target_mode: TargetMode = TargetMode.NONE`
- Add `target_scope: TargetScope = TargetScope.HOSTILE` (only meaningful for SINGLE)
- Add property `targeted -> bool` = `mode == SINGLE` (backwards compat for any remaining callers)

**Registration mapping (all 20+ actions):**
- ATTACK, OPPORTUNITY_ATTACK → SINGLE / HOSTILE
- LAY_ON_HANDS → SINGLE / ALLY
- DODGE, DASH, DISENGAGE, FLEE, SECOND_WIND, LONG_REST, SHORT_REST, BLESS → SELF
- Everything else (IDLE, SAY, WAIT, MOVE, MOVE_TO, EQUIP/UNEQUIP variants, BUY, SELL, USE_ITEM, END_TURN, SKIP) → NONE

**Validation update (`rules/validation.py`):**
- `check_target_valid` uses `target_mode` instead of `targeted`
- New `check_target_scope`: for SINGLE mode, if scope is HOSTILE → target must be hostile; if ALLY → target must not be hostile (or is self); if ANY → any creature. Requires `combat_state` for side info or faction relation fallback.

**Serialization (`service/session.py`):**
- Add `target_mode` and `target_scope` to the action_info dict sent to frontend.

## Tests First

1. **Scope validation rejects wrong target type:** Paladin (ALLY faction) uses Lay on Hands (ALLY scope) on a hostile creature → `ValidationError("WRONG_TARGET_SCOPE", ...)`. Same creature attacks (HOSTILE scope) a friendly creature → `ValidationError("WRONG_TARGET_SCOPE", ...)`.
2. **Scope validation accepts correct target type:** Attack on hostile → passes. Lay on Hands on ally → passes. Lay on Hands on self → passes.
3. **Targeted property still works:** `get_action_def(ATTACK).targeted` is True, `get_action_def(DODGE).targeted` is False.
4. **Action probe with no target still passes:** `check_target_valid` and `check_target_scope` return None when `target_id` is absent (probe mode).
5. **Serialization includes target_mode/target_scope:** Build awareness, serialize, check that action_info dicts contain `"target_mode"` and `"target_scope"`.

## Implementation

1. Add `TargetMode`, `TargetScope` enums to `core/action_defs.py`.
2. Update `ActionDef`: remove `targeted: bool`, add `target_mode`/`target_scope`, add `targeted` property.
3. Update all 20+ `_reg()` calls with correct mode/scope.
4. Add `check_target_scope` to `rules/validation.py`, update `check_target_valid` to use `target_mode`.
5. Update `service/session.py` serialization to include new fields.
6. Fix any callers that reference the old `targeted` field directly (grep for `.targeted`).
7. Fix existing tests broken by the field change.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] All ActionDef registrations use TargetMode/TargetScope instead of `targeted: bool`
- [ ] Validation rejects hostile target for ALLY-scoped actions
- [ ] Validation rejects friendly target for HOSTILE-scoped actions
- [ ] Serialized action_info includes target_mode and target_scope

## Status

`done`

## Developer Notes

- `TargetMode` (NONE/SELF/SINGLE) and `TargetScope` (HOSTILE/ALLY/ANY) enums added to `core/action_defs.py`.
- `ActionDef.targeted` is now a property (`target_mode == SINGLE`), fully backwards-compatible.
- All 20+ action registrations updated with correct mode/scope.
- `check_target_scope` added to validation pipeline — uses combat sides when available, falls back to faction comparison, passes through when hostility is undetermined (no factions, no sides).
- Serialization in `service/session.py` sends `target_mode` and `target_scope` to frontend.
- Existing dispatcher tests passed without modification — scope check is permissive when no combat sides or factions exist.
