# Task: Lair treasury — Container from content, gated behind core, persists across visits

**Date:** 2026-06-28
**Sprint:** 018-lairs-encounters-loot
**Phase:** 2 — Лут и контейнеры

## Description

Give lairs a treasury: a `Container` (Task 2) spawned at materialization, populated from the lair's content definition, optionally locked until the core/boss is dead. Because the treasury is a persisted `Container` entity, its looted state survives leaving and returning to the location and survives save/load — half-looted treasure never refills.

Random loot tables are out of scope: the treasury contents are an explicit item + gold list in content (deterministic). General monster corpse drops remain deferred (`loot-drops-monsters` in BACKLOG).

Concrete changes:

1. **Content schema.** Extend `LairContent` (`content_loader/schemas.py`) with optional `treasure`: a list of item refs (resolved via the existing catalog `ref:` mechanism used elsewhere in entity content) plus `gold: int`, and `treasure_behind_core: bool = true`. A lair with no `treasure` block gets no treasury.

2. **Lair model + state.** Add to `Lair` (`core/lair.py:23-39`): `treasure_items` (resolved item list), `treasure_gold: int`, `treasure_behind_core: bool`. Persist these (and the fact a treasury was created) in `EcologyLayer.get_state` lair dict (`layers/ecology/layer.py:202-224`) next to `alive_members`. Loading restores them.

3. **Spawn at materialization.** In `_materialize_lair` (`layers/entities/activation_manager.py:461-487`), when the lair has treasure, spawn one **persistent** (`temporary=False`) `Container` with a deterministic id (`f"{lair_id}_treasury"`) holding `treasure_items` + `treasure_gold`. Skip the spawn if that container already exists (it persists in `_entities` / save data — Task 2). Set its `is_open` from the gate: `is_open = (not treasure_behind_core) or (not lair.core_alive)`. Update `is_open` from `core_alive` on each materialization so killing the core unlocks it.

4. **Don't dematerialize the treasury.** In `_dematerialize_lair` (`layers/entities/activation_manager.py:489-515`) leave the treasury container in the world (unlike the roster creatures, which are popped). Its remaining contents persist as entity state, so a return visit sees whatever is left, not a refill.

## Tests First

Integration (extend `tests/integration/test_lairs.py` / the `lair_world` fixture with a treasure block):

- **Treasury gated behind core.** Lair treasury holds a magic sword + 100 gold, `treasure_behind_core: true`. While the core is alive, the treasury is present but not lootable (`is_open` false) — `take` is rejected. Kill the core → treasury becomes lootable → player `take` → player gains the sword + 100 gold.
- **No refill on return.** After looting, leave the location (dematerialize) and return (re-materialize) → the treasury is still present and empty; nothing respawned.
- **Save/load preserves looted state.** Loot half the treasury, save and reload → the treasury holds exactly what was left.
- **Open treasury.** With `treasure_behind_core: false`, the treasury is lootable from the first visit regardless of core state.
- **No treasure block → no treasury.** A lair without a `treasure` block spawns no treasury container.

## Implementation

- `content_loader/schemas.py` + the lair parser (`content_loader/monsters.py:186-210`, `_to_lair`): parse and resolve `treasure` item refs against the catalog; fail fast on unknown refs (same pattern as member/core template validation).
- `core/lair.py`: new fields.
- `layers/ecology/layer.py`: persist/restore treasure fields in lair state.
- `layers/entities/activation_manager.py`: spawn-once persistent treasury container, open-state gate tied to `core_alive`, exclude from dematerialization.
- Reuse the `Container` from Task 2 and `take` from Task 3 — no new transfer or loot logic here.

Gotcha: the treasury container's `is_open` must track `core_alive` across visits. Recompute it on materialization from the (persisted) lair `core_alive` rather than only at first spawn, so a player who returns after killing the core finds it unlocked.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Treasury spawns from lair content; unknown item refs fail fast
- [ ] `treasure_behind_core` gates lootability on core death; open treasuries are lootable immediately
- [ ] Looted state persists across leave/return and save/load (no refill)
- [ ] A lair without treasure spawns no treasury
- [ ] Phase verify path holds: kill core → loot treasury → gain items + gold (E2E "убил → залутал" handled at phase close)

## Status

`pending`
