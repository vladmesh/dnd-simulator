# Task: EntityType(StrEnum) — replace `"player"`/`"npc"`/`"creature"` literals

**Date:** 2026-04-13
**Sprint:** 016-tech-sweep
**Phase:** 4 — Enums & Fail-Fast

## Description

Define `EntityType(StrEnum)` in `core/models.py` with values `PLAYER`, `NPC`, `CREATURE`, `MONSTER`. Replace string-literal comparisons and `edata.get("entity_type")` string matches in the 3 call sites:

- `src/dnd_simulator/layers/entities/layer.py:497-509` — save/load entity reconstruction. Chain of `if entity_type == "player": ... elif "npc": ... elif "creature":`. Also: find the matching `save()` path that emits `"entity_type": "player"` etc. — must emit `EntityType.PLAYER.value` (StrEnum serializes cleanly).
- `src/dnd_simulator/layers/entities/query_handler.py:98-102` — `_query_entities` filter by `filter_type == "player" / "npc" / "monster"`. Note: "monster" is distinct from "creature" here — map `MONSTER` to "not PlayerCharacter, not Npc".
- `src/dnd_simulator/service/commands_creatures.py:187` — `if entity_type == "npc"` branch in a creature command.

Load path must accept both `EntityType` members (new) and raw strings from pre-migration save files via `EntityType(value)` constructor — saves are on-disk data, migration must be transparent. No backwards-compat shim, just use the StrEnum constructor which accepts the original strings.

Frontend not in scope — API surface still returns strings (StrEnum serializes as its value).

## Tests First

- Integration: save a session containing a PlayerCharacter, an Npc, and a spawned Creature (non-Character). Reload into a fresh session. Assert all 3 entities are reconstructed with correct concrete types (`isinstance(player, PlayerCharacter)`, `isinstance(npc, Npc)`, `isinstance(creature, Creature)` and not any subclass).
- Unit: `EntitiesLayer._query_entities` with `filter_type=EntityType.PLAYER` returns only PlayerCharacter instances. With `filter_type=EntityType.MONSTER` returns Creature instances that are neither PlayerCharacter nor Npc.
- Unit: passing a raw string `"player"` to query also works (StrEnum equality) — ensures API/JSON callers don't break.
- Unit: invalid entity_type string in save data raises `ValueError` with clear message (fail-fast on corrupt data, not silent skip).

## Implementation

1. Add `EntityType(StrEnum)` to `core/models.py` next to other enums.
2. Update `EntitiesLayer.load()` around line 497: `entity_type = EntityType(edata["entity_type"])` — fail-fast via constructor on unknown value (currently silent no-op on unknown type). Replace elif chain with `match` on `EntityType`.
3. Update `EntitiesLayer.save()` to emit `EntityType.X.value` — verify which method this is and align.
4. Update `_query_entities`: accept `EntityType | str`, normalize via `EntityType(filter_type)` when truthy.
5. Update `commands_creatures.py:187` site.
6. Grep for any other `"player"` / `"npc"` / `"creature"` string equality I missed.

## Acceptance Criteria

- [ ] Tests written and RED before implementation
- [ ] `grep -rn '== "player"' src/dnd_simulator/` returns nothing (same for `"npc"`, `"creature"` as type discriminators)
- [ ] Unknown `entity_type` in save data raises, not silently skipped
- [ ] `make check` passes
- [ ] Existing saves still load

## Status

`done`

## Developer Notes

Named the runtime enum `EntityKind` (not `EntityType`) to avoid collision with existing `content_loader.crud.EntityType` (YAML content kinds). Both concepts are legitimate and distinct — runtime discriminator vs content catalog — so renaming either would be worse than picking a new name.

4 members: PLAYER, NPC, CREATURE, MONSTER. Save data uses CREATURE for generic runtime creatures; API detail/query surface uses MONSTER for "Creature that isn't Player or Npc". Didn't unify — would force a save format migration for no real win.

Fail-fast added at `EntitiesLayer.load_state`: `EntityKind(edata["entity_type"])` raises on unknown, and the previous `else: continue` silent skip now raises (impossible state via save, but no point papering over it). Query filter uses `EntityKind(str(raw))` with mypy-narrowing cast since `params` is `dict[str, object]`.

Frontend untouched — API surface still returns string values (StrEnum serializes cleanly).
