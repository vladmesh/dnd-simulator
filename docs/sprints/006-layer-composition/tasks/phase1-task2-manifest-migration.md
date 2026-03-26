# Task: Manifest Format + World Migration + Cleanup

**Date:** 2026-03-26
**Sprint:** 006-layer-composition
**Phase:** 1 — Library Structure + Manifest + Content Migration

## Description

Define the world manifest format. Convert sword_vale to a manifest that references library templates. Create a small all-custom test world. Delete obsolete worlds.

**manifest.yaml format (library references):**

```yaml
name: {en: Sword Vale, ru: Долина Мечей}
description: {en: "A region around the port of Silverport...", ru: "..."}
default_player_faction: kingdom

layers:
  geography:
    source: library
    template: sword_vale
    version: "1.0"
  politics:
    source: library
    template: sword_vale
    version: "1.0"
  settlements:
    source: library
    template: sword_vale
    version: "1.0"
  ecology:
    source: library
    template: sword_vale
    version: "1.0"
  entities:
    source: library
    template: sword_vale
    version: "1.0"
```

**manifest.yaml format (all-custom):**

```yaml
name: {en: Test Vale, ru: Тестовая Долина}
description: {en: "Small test world for integration testing"}
default_player_faction: militia

layers:
  geography:
    source: custom
  politics:
    source: custom
  settlements:
    source: custom
  ecology:
    source: custom
  entities:
    source: custom
```

Custom layers read data from `{world_dir}/{layer_type}/` subdirectories. Same file names as library templates (e.g. `geography/regions.yaml`).

**sword_vale after conversion:**

```
content/worlds/sword_vale/
└── manifest.yaml          # all 5 layers → library/sword_vale
```

No data files in the world dir — everything comes from library.

**Test world (test_vale) — all-custom, exercises every layer:**

```
content/worlds/test_vale/
├── manifest.yaml
├── geography/
│   ├── regions.yaml       # 2 regions (crossroads, forest), connected
│   └── locations.yaml     # 4-5 locations across both regions
├── politics/
│   └── nations.yaml       # 1 nation (militia)
├── settlements/
│   └── settlements.yaml   # 1 town in crossroads region
├── ecology/
│   ├── monsters.yaml      # 1 monster template (bandit)
│   └── squads.yaml        # 1 patrol squad
└── entities/
    └── npcs.yaml          # 3-4 NPCs: tavern_keeper, guard, merchant, blacksmith
```

**Cleanup:** Delete `content/worlds/arena/`, `content/worlds/village/`, `content/worlds/sneak_test/`.

## Tests First

1. **Manifest validity** — for each `content/worlds/{world}/`, verify: manifest.yaml exists, has required fields (name, layers), every layer entry has `source` field, library refs have `template` + `version`, custom layers have matching data subdirectory with expected files.

2. **Library reference resolution** — for every manifest with `source: library`, verify the referenced template exists at `content/library/{layer_type}/{template}/` and the version matches metadata.yaml.

3. **Test world completeness** — load test_vale's YAML files, verify: regions have connections, locations have neighbors, NPCs reference valid locations, squad references valid monster template and valid route locations.

4. **No old-format worlds** — scan `content/worlds/*/`, assert none have top-level `world.yaml` (old format marker), all have `manifest.yaml`.

## Implementation

1. Create `manifest.yaml` for sword_vale (all library refs). Delete sword_vale's data files (they're now in library).
2. Create `content/worlds/test_vale/` with all-custom layers:
   - Geography: 2 regions (crossroads plains, darkwood forest) with bidirectional connection. 4-5 locations (tavern, market, guard_post in crossroads town; forest_clearing, forest_road in darkwood).
   - Politics: 1 nation (Free Militia) controlling crossroads.
   - Settlements: 1 town (Crossroads Town) in crossroads region.
   - Ecology: 1 monster template (bandit), 1 patrol squad (militia_patrol) on a 2-location route.
   - Entities: tavern_keeper (rule_based), guard (rule_based), merchant (rule_based), wanderer (llm) — all at crossroads locations.
3. Delete arena, village, sneak_test directories.
4. Move `content/worlds/sword_vale/world.yaml` content into manifest.yaml, delete world.yaml.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] sword_vale has only `manifest.yaml`, no data files
- [ ] test_vale is a complete all-custom world with all 5 layers populated
- [ ] arena, village, sneak_test are deleted
- [ ] No `world.yaml` files exist under `content/worlds/`
- [ ] `make check` passes (content_loader not changed yet — tests validate structure only)

## Status

`pending`
