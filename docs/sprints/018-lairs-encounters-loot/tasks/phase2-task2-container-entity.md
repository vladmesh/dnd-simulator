# Task: `Container` entity + save/load persistence

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 2 — Лут и контейнеры

## Description

Introduce the lightweight `Container` entity — a sibling of `Creature` with inventory and gold but no HP, turn, or brain — and make it a first-class persisted entity so its contents survive save/load. This is the substrate the lair treasury (Task 4) reuses.

Concrete changes:

1. **`Container(Entity)`** (new, e.g. `core/container.py`). Inherits the `Entity` contract (`id`, `name`, `location_id`, `active`, `temporary`, `faction_id`, `_last_seen_log_index` — `core/character.py:192-203`). Adds `inventory: list[Item] = []`, `gold: int = 0`, and an open/closed state `is_open: bool = True`. No ability scores, HP, `turn_budget`, or `brain`. Satisfies `InventoryHolder` (Task 1) structurally.

2. **`is_lootable` for containers.** Extend Task 1's `rules/loot.py:is_lootable` so an open `Container` is lootable and a closed one is not.

3. **Persistence.** Add `EntityKind.CONTAINER = "container"` to `core/models.py:9-19`. In `EntitiesLayer.get_state` (`layers/entities/layer.py:400-486`) add a `Container` branch: serialize `id`, `name`, `location_id`, `active`, `is_open`, `gold`, and `inventory` (reuse `core/player._serialize_item`). In `load_state` (`layers/entities/layer.py:488-540`, the `EntityKind` reconstruct ladder) add a `CONTAINER` branch that rebuilds the `Container` from saved data (deserialize items the same way creatures' inventories are restored).

4. **Coexistence check.** `EntitiesLayer` already filters creature queries by `isinstance(e, Creature)` (`layers/entities/layer.py:135`, `:142`, `:154`), so a `Container` stays out of combat, activation, and brain loops. Verify nothing iterates `_entities` assuming `Creature` without a guard.

## Tests First

- **Container survives save/load.** A `Container("chest", location="cave")` holding a longsword and 25 gold is added to the world; serialize the entities layer, load into a fresh layer → the chest is present at `cave` with the longsword and 25 gold, and `is_lootable` is true.
- **Closed container is not lootable.** A container with `is_open=False` is not lootable; flipping `is_open=True` makes it lootable.
- **Container is not a creature.** `get_active_creatures()` excludes the container; it never appears in initiative, activation, or `get_active_creatures`/merchant queries.

## Implementation

- `core/container.py`: `Container` dataclass.
- `core/models.py`: `EntityKind.CONTAINER`.
- `layers/entities/layer.py`: serialize branch in `get_state`, reconstruct branch in `load_state`. Reuse `_serialize_item` and the item-deserialization helper used for creature inventories so item round-trip stays in one place.
- `rules/loot.py`: container arm of `is_lootable`.

Gotcha: the `get_state` ladder is `isinstance(e, Creature)` first (adds combat fields), then `PlayerCharacter`/`Npc`/`Creature` for `entity_type`. `Container` is not a `Creature`, so it skips the creature block entirely and needs its own top-level branch that sets `entity_type = CONTAINER`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `Container` round-trips through `get_state`/`load_state` with inventory + gold + open state
- [ ] `Container` is invisible to creature/combat/activation queries
- [ ] `is_lootable` treats open containers as lootable, closed as not

## Status

`done`

## Developer Notes

- `Container(Entity)` in `core/container.py`: `inventory`, `gold`, `is_open` (default open). No HP/brain/turn.
- `is_lootable` (`rules/loot.py`) gained the container arm: open → lootable, closed → not.
- `EntityKind.CONTAINER` added (`core/models.py`). Save/load wired in `layers/entities/layer.py`: a top-level `elif isinstance(e, Container)` branch in `get_state` (skips the Creature structural block, serializes `is_open`/`gold`/`inventory` via `_serialize_item`); a `CONTAINER` reconstruct branch in `load_state` that builds a bare `Container`; and a Container arm in the mutable-state chain that restores `gold`/`is_open`/`inventory` (via `deserialize_item`). Splitting reconstruct (bare object) from mutable-restore (contents) mirrors the existing Creature pattern, so both fresh-load and pre-existing containers restore correctly — matters for the Task 4 treasury.
- Coexistence confirmed: `Container` is excluded from `get_active_creatures`/merchant/wake queries (all guard on `isinstance(e, Creature)`/`Npc`). `awareness_builder` and `query_handler._entity_detail` iterate `_entities` without a Creature guard, but only matter once a container sits in a live location — that surfacing is Task 3 (`take`/awareness). No live-location container exists yet, so the suite stays green.
- One ruff I001 import-order fix (container import slotted after combat, belongs after conditions) auto-fixed.
- `make check` green: backend 2202 passed (+4), tsc clean, vitest 238 passed. The 2 `SchemaForm.tsx` eslint warnings are pre-existing.
