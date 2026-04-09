# Task: Awareness + Serialization for Reputation

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 2 — Personal Reputation + effective_relation

## Description

Wire `effective_relation` into the awareness system and persist reputation through save/load.

### Awareness
`AwarenessBuilder.check_faction_hostility` currently queries politics layer for raw faction relation. Switch to `effective_relation` — needs observer and other as Creature (already Creature instances in practice). This affects what LLM and RuleBrain see as hostile/friendly.

### Serialization
`EntitiesLayer.get_state` / `load_state` must include `reputation` dict so it survives save/load. Only serialize if non-empty (sparse).

### Content loading
Optional `reputation` field in YAML creature definitions. If present in NPC/creature YAML, parse into the dict. Most creatures won't have it — defaults to empty.

## Tests First

Scenarios:

- **Awareness hostility with personal rep:** Observer has reputation 10 with target's faction (factions are NEUTRAL by default) → `check_faction_hostility` returns True.
- **Awareness friendship override:** Factions are HOSTILE, but observer has reputation 80 with target's faction → `check_faction_hostility` returns False.
- **Awareness exile:** Observer has reputation 10 with OWN faction → hostile to same-faction creature.
- **Save/load roundtrip:** Creature with `reputation: {"goblin": 30, "human": 90}` → get_state → load_state → reputation dict preserved exactly.
- **Save/load empty reputation:** Creature with no reputation entries → `reputation` key absent from serialized data (sparse).
- **YAML loading:** NPC definition with `reputation: {goblin: 20}` → parsed creature has `reputation == {"goblin": 20}`.

## Implementation

1. **`awareness_builder.py`:** Change `check_faction_hostility` to use `effective_relation`. Add Creature type check — non-Creature entities have no reputation, fall back to faction-only.
2. **`layers/entities/layer.py` get_state:** Add `if e.reputation: data["reputation"] = dict(e.reputation)` in the Creature serialization block.
3. **`layers/entities/layer.py` load_state:** Restore `reputation` dict from saved data.
4. **Content loading (`content_loader/creatures.py`):** Parse optional `reputation` field from YAML into Creature.
5. **Pydantic content schema:** Add `reputation: dict[str, int] = {}` to the creature content model if one exists.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Awareness hostility reflects personal reputation, not just faction relations
- [ ] Reputation survives save/load cycle
- [ ] Empty reputation is not serialized (sparse storage)

## Status

`pending`
