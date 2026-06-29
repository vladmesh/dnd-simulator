# Task: rules/ purity — provider I/O & statefulness

**Date:** 2026-06-30
**Sprint:** 020-thermo-sweep
**Phase:** 1 — Корректность и инварианты

## Description

Action providers in `rules/action_provider.py` hold I/O callbacks and instance state, violating the pure-rules invariant. Move the I/O out and de-state the base. Behavior unchanged.

1. **`merchant-provider-in-rules` (backlog: should).** `MerchantActionProvider` (`rules/action_provider.py:152-167`) stores a world-query callback (`self._get_nearby_merchants`) and calls it to read live layer state. The callback (`service/action_dispatcher.py:213-239`) queries `entities_layer._entities` and `world.time.hour` — I/O reaching into mutable layer state from inside `rules/`.

2. **`base-action-provider-stateful` (backlog: should).** `BaseActionProvider` (`:35-48`) is a stateful class holding `self._types`. `LootActionProvider` (`:137-149`) has the same world-query-callback smell as the merchant provider (same pattern — fix it consistently).

## Tests First (RED)

These are behavior-preservation + boundary tests:
- **Merchant actions unchanged.** With a merchant NPC at the actor's location, the available action set still includes `BUY`/`SELL`; with no merchant nearby, it doesn't. (Exercise through the dispatcher / provider entry point so the test passes regardless of where the nearby-merchant resolution now lives.)
- **Loot actions unchanged.** With a lootable nearby, `TAKE` is available; otherwise not.
- **Base actions unchanged.** The base action set (everything not provider-managed) is still offered when valid.
- **Purity boundary.** `rules/action_provider.py` no longer stores a world/layer-query callback and no longer reaches into layer state — the nearby-merchant/lootable data is supplied as an argument (or the provider lives in `service/`). Assert via the new shape (e.g. the pure function takes the nearby list as a parameter), not by grepping.

Run the existing provider/dispatcher tests as the regression backstop (behavior must not change).

## Implementation (GREEN)

Pick one consistent shape for both merchant and loot (discuss in implementation if ambiguous):

- **Option A — data as argument:** the provider receives the already-resolved nearby merchants/lootables (a plain list) per call, computed by the caller in `service/`. `rules/` stays pure; the dispatcher does the world query before invoking.
- **Option B — relocate to service:** move `MerchantActionProvider`/`LootActionProvider` into `service/` (they are inherently I/O-coupled), leaving only pure providers in `rules/`.

For `BaseActionProvider`: convert to a standalone function (e.g. `base_action_types(creature, ctx, types) -> list[ActionType]`) or a `frozen=True` dataclass, removing mutable instance state. The other providers (`Inventory`/`Equipment`/`Weapon`/`ClassFeature`) are already effectively stateless — align them to the same shape if it's cheap, otherwise leave them.

Keep `service/action_dispatcher.py` wiring working: it currently instantiates providers at startup (`:200-208`). Adjust construction to match whichever option is chosen.

Files: `rules/action_provider.py`, `service/action_dispatcher.py` (and a new `service/` provider module if Option B).

Gotcha: don't change which actions are offered or their order in a way that breaks awareness/LLM action schemas — this is a structural move, not a behavior change.

## Acceptance Criteria

- [ ] Tests written and RED before implementation
- [ ] `rules/action_provider.py` holds no world-query callback and reads no layer state (merchant + loot nearby data supplied as argument, or providers moved to `service/`)
- [ ] `BaseActionProvider` is a standalone function or frozen dataclass (no mutable instance state)
- [ ] Available action sets (base / merchant / loot) unchanged
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Went with Option B: moved `MerchantActionProvider` and `LootActionProvider` to the new `service/contextual_providers.py`. They still store callbacks (appropriate for service/), `rules/action_provider.py` is now callback-free. Removed `NearbyMerchantsFn` / `NearbyLootablesFn` type aliases from `rules/` as well — they now live in `service/contextual_providers`.

`BaseActionProvider` converted to `@dataclass(frozen=True)` with field `action_types` (was `self._types`). Constructor call sites are unchanged — positional arg still works.

Updated 3 test files that imported the moved classes (`test_take_loot`, `test_trade_handlers`, `test_action_provider_isolated`). No behavior change anywhere.
