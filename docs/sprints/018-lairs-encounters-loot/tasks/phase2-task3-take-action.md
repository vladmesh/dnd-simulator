# Task: `take` action — provider, validation, handler, awareness, loot UI

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 2 — Лут и контейнеры

## Description

Wire a `take` action that moves **all** loot (items + gold) from a lootable holder in the actor's location to the actor, in one action, and surface it to the player. Take-all semantics; an optional `item_id` for selective taking is out of scope (deferred).

Concrete changes (full action pipeline: registry → provider → validation → handler → awareness → UI):

1. **`ActionType.TAKE` + `ActionDef`** (`core/action_defs.py`). `target_mode=TargetMode.SINGLE`, `target_scope=TargetScope.ANY` (lootable status, not faction, gates the target — see validation below), `cost_type=CostType.ACTION`, `combat_mode=PEACEFUL_ONLY` (loot after the fight, keeps combat balance out of scope), `provider_managed=True` (only the loot provider offers it), param `target_id` (string, required). Model after the `LAY_ON_HANDS` entry (`core/action_defs.py:477-492`).

2. **`LootActionProvider`** (`rules/action_provider.py`, next to `MerchantActionProvider` at `:134-150`). Offers `TAKE` when ≥1 lootable `InventoryHolder` is at the actor's location. Takes a `get_nearby_lootables(creature)` callback, wired in `service/action_dispatcher.py:create_dispatcher` (`:198-203`) the same way `_build_nearby_merchants_fn(world)` feeds `MerchantActionProvider`.

3. **`check_lootable_target`** (`rules/validation.py`, after `check_target_valid` in `_CHECKS`). Target must exist, be in the same location as the actor, be an `InventoryHolder`, and be `is_lootable(target)`. `TAKE` must bypass the faction `check_target_scope` the same way the HOSTILE-attack exception already does — a corpse/container has no useful faction relation.

4. **`handle_take`** (new `rules/handlers/loot.py`). Resolve the target holder via `ctx.get_entity`; `transfer_items(src=target, dst=actor, items=list(target.inventory), gold=target.gold)` (Task 1 primitive); emit `EventType.ENTITY_TAKE` with actor id, target id, taken item names, and gold. Register in `create_dispatcher` (`service/action_dispatcher.py:158-203`). Add the `ENTITY_TAKE` event type.

5. **Awareness.** Surface lootable holders so the player can target them. In the peaceful awareness builder (`layers/entities/awareness_builder.py`, `build_nearby_entities`), include lootable holders in `nearby` with a `lootable` flag and their visible contents (item names + gold), and make sure `available_actions` carries `TAKE` when the provider offers it. Serialize the loot contents in the awareness→dict path (`service/session.py:59-101`) so the client can render them.

6. **Loot UI** (frontend). Minimal panel modeled on `frontend/src/components/game/TradePanel.tsx`: when a lootable target is present and `take` is available, show a "Loot" affordance listing the target and its contents; submit `{type:"action", name:"take", params:{target_id}}` over WS (same path as other actions). Wire into `ActionBar`/`action-bar` rendering and `actionCategories.ts`.

## Tests First

Integration, product-level (mirror `tests/integration/test_lairs.py` structure):

- **Loot a corpse.** A dead NPC at the player's location holds a longsword and 50 gold. Player `take` targeting the corpse → player inventory gains the longsword, player gold +50; corpse inventory empty and gold 0; an `ENTITY_TAKE` event is emitted.
- **Loot a container.** An open `Container` with two potions at the player's location → player `take` moves both potions to the player; container empty.
- **A living creature is not lootable.** `take` targeting a living goblin is rejected by validation; the goblin keeps its inventory.
- **Availability gating.** With no lootable holder at the location, `take` is absent from `available_actions`; with one present (out of combat), `take` is offered.
- **Wrong location rejected.** `take` targeting a corpse in a different location returns a validation error and moves nothing.

## Implementation

- Registry/provider/validation/handler/event as above. Keep the validation check ordering: `check_lootable_target` after `check_target_valid`, and ensure `TAKE` short-circuits the faction scope check.
- The provider only signals availability (no `target_id`); per-target legality is `check_lootable_target`'s job.
- Reuse `transfer_items` and `is_lootable` from Task 1; do not re-implement transfer logic in the handler.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `take` transfers all items + gold from a lootable holder to the actor and empties the source
- [ ] Provider gates availability on a lootable holder being present; validation rejects living / wrong-location / non-lootable targets
- [ ] Lootable holders + their contents appear in awareness; frontend loot panel can issue `take`

## Status

`done`

## Developer Notes

Full action pipeline wired end to end, reusing the Task 1/2 substrate (`transfer_items`, `is_lootable`, `Container`).

- **Registry/event:** `ActionType.TAKE` (`core/action.py`), `EventType.ENTITY_TAKE` (`core/models.py`), `ActionDef` for TAKE (`core/action_defs.py`) — `SINGLE`/`ANY`/`ACTION`/`PEACEFUL_ONLY`/`provider_managed`, required `target_id`.
- **Provider:** `LootActionProvider` + `NearbyLootablesFn` (`rules/action_provider.py`), wired via `_build_nearby_lootables_fn` in `create_dispatcher`. The lookup keys on location + `is_lootable` and deliberately ignores `active`, because corpses are dormant after death (activation_manager sets dead creatures `active=False`).
- **Validation:** new `check_lootable_target` (after `check_target_valid` in `_CHECKS`). TAKE short-circuits both `check_target_valid` (would reject corpses as TARGET_DEAD and containers as non-Creature) and `check_target_scope` (a corpse/container has no useful faction relation). Codes: TARGET_NOT_FOUND / TARGET_WRONG_LOCATION / TARGET_NOT_LOOTABLE.
- **Handler:** `handle_take` (`rules/handlers/loot.py`) — take-all of items + gold via `transfer_items`, emits `ENTITY_TAKE`. Selective `item_id` taking deferred per task scope.
- **Awareness:** `build_nearby_entities` now surfaces lootable holders even when dormant, with `lootable` / `loot_items` (reusing `ItemInfo`/`describe_item`) / `loot_gold` added to `NearbyEntity`. Living creatures get `lootable=False`. Serialization is automatic via `dataclasses.asdict` (verified the dict carries the loot fields) — no manual change needed in `session.py`. Added `_perceive_take` so the event log renders looting instead of the generic fallback.
- **Frontend:** `LootPanel.tsx` (modeled on `TradePanel`) lists lootable holders + contents and issues `take {target_id}` over WS; rendered in the peaceful column of `GameScreen`. `take` added to `ActionBar`'s `ALWAYS_HIDDEN` (same treatment as buy/sell — the panel owns it, so no `actionCategories.ts` change was needed). i18n keys `loot`/`take_all`/`loot_empty` (en + ru). Mocked `LootPanel` in the GameScreen layout test.
- **Tests:** `tests/unit/test_take_loot.py` (12 — handler corpse/container, validation rejects living/wrong-location/closed, provider gating incl. combat, full dispatch) and `tests/unit/test_loot_awareness.py` (4 — lootable holders surface, living/closed do not). Unit-level but drive the real validation chain, handler, dispatcher, and awareness builder. Integration scenarios in the task brief land at `/close-phase`.
