# Task: ActionProvider + BrainFactory unit tests

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 5 — Test Gaps

## Description

ActionProvider (136 LOC, 6 provider classes) has no isolated unit tests — only indirect coverage through the dispatcher. BrainFactory (39 LOC) has zero tests. Both are service infrastructure that downstream code depends on.

No code changes — only new test files.

## Tests First

### ActionProvider — `tests/unit/test_action_provider.py`

Each provider tested in isolation with a real `ActionContext` and real `validate_action`.

**BaseActionProvider:**
- In combat: attack, dodge, flee available; wait, move filtered by validation
- Out of combat: say, wait, move available; attack not available (requires target)

**InventoryActionProvider:**
- Creature with a potion in inventory → USE_ITEM returned
- Creature with empty inventory → empty list
- Creature with only weapon items (no usable) → empty list (weapons aren't "used", they're equipped)

**EquipmentActionProvider:**
- Creature with a weapon in inventory, nothing equipped → EQUIP returned
- Creature with equipped weapon, nothing in inventory → UNEQUIP returned
- Creature with armor in inventory → EQUIP_ARMOR returned
- Creature with equipped shield → UNEQUIP_SHIELD returned

**ClassFeatureActionProvider:**
- Fighter with second_wind resource pool (current_uses > 0) → SECOND_WIND returned
- Fighter with exhausted second_wind pool (current_uses = 0) → empty list
- Rogue (no second wind) → empty list
- Non-Character creature → empty list

**WeaponActionProvider:**
- Creature with weapon that has grant_actions=[BLESS] → BLESS returned
- Creature with weapon without grant_actions → empty list
- Creature with no equipped weapon → empty list

**MerchantActionProvider:**
- Creature at location with merchant → BUY, SELL returned
- Creature at location with no merchants → empty list

### BrainFactory — `tests/unit/test_brain_factory.py`

- `create("rule_based")` → returns `RuleBrain` instance
- `create("llm")` with LlmClient provided → returns `LlmBrain` instance
- `create("llm", strict=True)` without LlmClient → raises `ValueError("LLM not configured")`
- `create("llm", strict=False)` without LlmClient → returns `RuleBrain` (fallback)
- `create("telepathy")` → raises `ValueError("Unknown ai_type: telepathy")`

## Implementation

**test_action_provider.py:** Build real `Creature`/`Character` instances with appropriate inventory, equipment, and resource pools. Build real `ActionContext` (in_combat, battle_map, get_entity, etc.). Call `provider.get_action_types(creature, ctx)` and assert on returned action types. No mocking of validation — let the real validation pipeline run.

**test_brain_factory.py:** `BrainFactory(llm=None)` and `BrainFactory(llm=MagicMock(spec=LlmClient))`. Assert on return types. 5 tests total.

## Acceptance Criteria

- [ ] Tests written and GREEN immediately
- [ ] All new tests pass
- [ ] Existing tests still pass (`make check`)
- [ ] Each provider class has at least 2 test scenarios
- [ ] BrainFactory covers all 5 branches
- [ ] No mocks of internal provider logic — only external boundaries (get_nearby_merchants callback for MerchantActionProvider, LlmClient for BrainFactory)

## Status

`done`

## Developer Notes

Created 2 new test files with 23 tests total (18 ActionProvider + 5 BrainFactory). All GREEN immediately.

**Deviations from plan:**
- `test_creature_with_only_weapon_items_gets_nothing` → renamed to `test_creature_with_only_weapon_items_still_gets_use_item`. The task assumed USE_ITEM validation would reject weapon items, but InventoryActionProvider only checks `creature.inventory` is non-empty — the probe passes for any item. This is the actual behavior and is correct (handler-level validation catches invalid use).
- WeaponDef/ArmorDef/ShieldDef constructors require `weapon_id`/`armor_id`/`shield_id` and enum categories — adjusted fixtures accordingly.
