# Task: InventoryHolder substrate, `is_lootable`, `transfer_items` primitive

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 2 — Лут и контейнеры

## Description

Build the shared substrate the rest of the phase stands on: a uniform inventory/gold holder, a derived "lootable" state, and a single item-transfer primitive that trade is refactored onto.

Concrete changes:

1. **Move `gold` to `Creature`.** Today `gold: int = 0` lives on `Character` (`core/character.py:274`); `inventory` is already on base `Creature`. Move `gold` up to `Creature` (`core/character.py:206-237`) so every creature is a uniform holder and bare monster `Creature`s (from `MonsterTemplate.spawn`, `core/monster.py:25-29`) get `gold == 0` by default. Remove the now-duplicate field from `Character`. Default `0` keeps save-load backward compatible.

2. **`InventoryHolder` Protocol.** New `@runtime_checkable` Protocol (house style per `core/creature_host.py:23-93`) declaring `inventory: list[Item]` and `gold: int`. Place in `core/` (e.g. `core/loot.py`). `Character`, bare `Creature`, and the future `Container` (Task 2) all satisfy it structurally.

3. **`is_lootable` derived state.** Pure function in `rules/` (e.g. `rules/loot.py`): `is_lootable(entity) -> bool` — a dead `Creature` (`not creature.is_alive`, see `core/character.py:245`) is lootable; an open `Container` (Task 2) is lootable; everything else is not. Keep it pure and centralized (rules-as-functions principle); no method on the model.

4. **`transfer_items` primitive.** New pure function (e.g. `rules/inventory.py`): `transfer_items(*, src: InventoryHolder, dst: InventoryHolder, items: list[Item], gold: int = 0) -> None` — removes each item from `src.inventory`, appends to `dst.inventory`, moves `gold` from `src` to `dst`. No validation, no pricing, no consent — just the move. Refactor `rules/trade.py` `execute_buy` / `execute_sell` (`rules/trade.py:54-71`) to call it (item moves seller→buyer, gold buyer→seller). Pricing/consent gates stay in `validate_buy`/`validate_sell`.

## Tests First

Product-level behavior to pin down before implementing:

- **Transfer moves items and gold both ways.** Holder A has [sword, shield, potion] and 30 gold; B has [] and 10 gold. `transfer_items(src=A, dst=B, items=[sword, potion], gold=30)` → A has [shield] and 0 gold; B has [sword, potion] and 40 gold.
- **Buying still works through the shared primitive.** Player with 100 gold buys a 50gp potion from a merchant: potion moves merchant→player, player gold 100→50, merchant gold +50. (Exercises trade on top of `transfer_items` — existing trade tests must stay green.)
- **Selling is symmetric.** Player sells a 20gp dagger to a merchant: dagger moves player→merchant, player gold +20, merchant gold −20.
- **Bare monster Creature is a holder.** A `MonsterTemplate.spawn`-ed goblin has `gold == 0` and can receive gold via `transfer_items` (substrate is uniform, not Character-only).
- **`is_lootable`:** a living creature is not lootable; the same creature after `take_damage` to 0 HP is lootable.

## Implementation

- `core/character.py`: move `gold` field from `Character` to `Creature`; check the `Character` constructor / any `gold=`-positional call sites and `to_full_save_data` still round-trip.
- `core/loot.py`: `InventoryHolder` Protocol.
- `rules/inventory.py`: `transfer_items`.
- `rules/loot.py`: `is_lootable`.
- `rules/trade.py`: rewrite `execute_buy`/`execute_sell` bodies to delegate to `transfer_items`; keep signatures and validators untouched so callers (`rules/handlers/trade.py`) don't change.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`) — trade tests green via the refactor
- [ ] `gold` lives on `Creature`; bare monsters default to 0; save/load round-trips
- [ ] `InventoryHolder` Protocol and pure `is_lootable` exist; `transfer_items` is the single transfer path used by trade

## Status

`done`

## Developer Notes

- `gold` moved from `Character` to `Creature` (`core/character.py`); all call sites are keyword (`gold=`), so no positional breakage. `Npc`/`PlayerCharacter` inherit it unchanged; bare monster `Creature`s now default to `gold == 0`.
- `InventoryHolder` Protocol in `core/loot.py`; `transfer_items` in `rules/inventory.py`; `is_lootable` in `rules/loot.py`.
- `is_lootable` implements only the Creature (dead corpse) arm this task; the open-`Container` arm is added in Task 2 (planned that way).
- Trade refactor: `execute_buy`/`execute_sell` both collapse to `transfer_items(src=seller, dst=buyer, items=[item], gold=-price)` — buy and sell were already mirror images, so they share one call. Validators and handler signatures untouched.
- Tests: added `tests/unit/test_inventory.py` (transfer both directions, gold-only, items-only, bare-monster holder) and `tests/unit/test_loot.py` (living vs dead). Buy/sell behavior is guarded by the existing `test_trade.py` / `test_trade_handlers.py` (still green) rather than duplicated.
- `make check` green: backend 2198 passed, tsc clean, vitest 238 passed. The 2 eslint warnings in `SchemaForm.tsx` are pre-existing and unrelated.
