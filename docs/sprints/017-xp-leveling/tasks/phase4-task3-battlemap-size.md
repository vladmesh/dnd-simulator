# Task: Per-location battle_map size in YAML

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 4 — E2E follow-up bug sweep

## Symptom

The `level_up_test/arena_floor` location is described as a "tiny 3×3 sandstone ring" in its YAML description, but combat there opens on the engine default battle map (`DEFAULT_BATTLE_MAP_SIZE`, ~13×13). Two NPCs declared 1 cell apart had ~50 ft of empty arena between them on screen.

This isn't a crash — but the gap between authored intent and engine behavior makes the test world misleading and forces playbook scenarios to talk in cells the YAML doesn't control.

There **is** an existing mechanism — `battle_map_configs` — populated from `geography/battle_maps.yaml` in `service/game_service.py`, but only at region scope:

```py
region_battle_maps = load_battle_maps(layer_paths["geography"])
battle_map_configs = {}
for loc in locations:
    if loc.region_id in region_battle_maps:
        battle_map_configs[loc.id] = region_battle_maps[loc.region_id]
```

So the data path exists, but is **opt-in per region**. Tasks 4.3 should make it possible to author per-location maps at the location level, and ideally make this the canonical authoring point (region as fallback).

## Investigation scope

Before changing anything, document in Developer Notes:

1. **Current loader** (`load_battle_maps` — likely in `content_loader/`): which file shape it expects, what schema validation it does. Are walls supported? Any examples in tree (`grep -r 'battle_maps'` in `content/`)?
2. **Why region-scoped first?** Look in git log of `battle_map_configs` and `BattleMapConfig`. There may be an existing reason (regions = terrain templates, locations = instances) that we shouldn't paper over.
3. **What happens for locations with NO config?** Currently fall-through to `DEFAULT_BATTLE_MAP_SIZE`. Should the fallback stay, or should it become a hard error so misconfigured worlds can't silently size up to 13×13?

## Possible directions

- **Per-location override file**: `content/worlds/<id>/geography/battle_maps.yaml` with location_id keys. Region keys still allowed as defaults, location overrides region. Loader resolves. **(Likely best — additive, doesn't break existing worlds.)**
- **Inline in `locations.yaml`**: each location grows a `battle_map: {width, height, walls?}` block. Less file sprawl but mixes geometry with battle config. Choose only if location/map are tightly coupled.
- **Drop default fallback entirely**: every location that hosts combat must declare its battle_map. More fail-fast (good) but breaks every existing world that doesn't have a declaration. Probably too aggressive for this task — separate later.

Pick one, justify in writing.

## Tests First

1. `test_battle_map_per_location_override` — content fixture with one location declaring `battle_map: {width: 3, height: 3}` and another in the same region using region default; loader produces correct configs for both.
2. `test_combat_uses_per_location_size` — start combat at the small location, assert `BattleMap.width == 3`.
3. Schema validation: width/height bounds (min 2, max ~50), walls within grid.

## Implementation

- Extend whichever Pydantic model represents location geography (or add a new `BattleMapContent` if cleaner).
- Update `service/game_service.py` to merge region defaults + location overrides (location wins).
- Update `level_up_test/arena_floor` to declare a 5×5 (or whatever fits the two NPCs adjacent to player) battle_map. **5×5 is more honest than 3×3 — three creatures at fixed positions need room.**
- Re-run phase 3 E2E to confirm the arena now feels arena-sized.

## Acceptance Criteria

- [ ] Developer Notes contain the schema/loader trace + chosen direction with rationale
- [ ] Per-location `battle_map` declaration works end-to-end (YAML → loader → combat init)
- [ ] `level_up_test/arena_floor` declares an explicit small map (≤ 7×7) and uses it in combat
- [ ] At least one regression test loading an existing world (`sword_vale` or `test_vale`) passes — region-level maps still work
- [ ] `make check` green

## Status

`pending`
