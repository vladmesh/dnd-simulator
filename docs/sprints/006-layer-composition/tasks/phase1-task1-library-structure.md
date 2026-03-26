# Task: Library Structure + Sword Vale Extraction

**Date:** 2026-03-26
**Sprint:** 006-layer-composition
**Phase:** 1 — Library Structure + Manifest + Content Migration

## Description

Define the layer template format and create the library from sword_vale's data. This establishes the canonical structure that all templates follow.

**New directory layout:**

```
content/
├── library/
│   ├── geography/sword_vale/
│   │   ├── metadata.yaml
│   │   ├── regions.yaml      (without settlements — extracted)
│   │   └── locations.yaml
│   ├── politics/sword_vale/
│   │   ├── metadata.yaml
│   │   ├── nations.yaml
│   │   └── factions.yaml
│   ├── settlements/sword_vale/
│   │   ├── metadata.yaml
│   │   └── settlements.yaml   (NEW — extracted from regions.yaml)
│   ├── ecology/sword_vale/
│   │   ├── metadata.yaml
│   │   ├── monsters.yaml
│   │   └── squads.yaml
│   └── entities/sword_vale/
│       ├── metadata.yaml
│       └── npcs.yaml
```

**metadata.yaml format:**

```yaml
name: "Sword Vale Geography"
layer_type: geography          # geography | politics | settlements | ecology | entities
version: "1.0"
description: "7 coastal/inland regions around the port of Silverport"
tags: [medieval, fantasy, coastal]
```

**Settlements extraction:** Pull all `settlements:` blocks from regions.yaml into a standalone `settlements.yaml`. Each entry keyed by settlement id, with a `region:` field pointing back. regions.yaml loses its `settlements:` keys.

**settlements.yaml format:**

```yaml
silverport_city:
  name: {en: Silverport City, ru: Город Серебропорт}
  region: silverport
  type: city
  population: 5000
  prosperity: 70
  defenses: 60
```

## Tests First

Tests validate the on-disk structure — no loader changes yet, so we test the YAML files directly.

1. **Library template completeness** — for each `content/library/{layer_type}/{template}/`, verify: metadata.yaml exists and has required fields (name, layer_type, version), layer_type matches the parent directory name, expected data files exist per layer type (geography → regions.yaml + locations.yaml, politics → nations.yaml, settlements → settlements.yaml, ecology → monsters.yaml, entities → npcs.yaml).

2. **Settlements extraction correctness** — load the new settlements.yaml from sword_vale library, verify every settlement has a `region` field, verify that region exists in regions.yaml. Load regions.yaml and verify no `settlements:` key remains on any region.

3. **Data preservation** — count of regions, locations, nations, NPCs, settlements, squads, monster templates in the library matches the counts from the original sword_vale (hardcode expected counts from current data).

## Implementation

1. Create `content/library/` directory tree.
2. Extract settlements from `content/worlds/sword_vale/regions.yaml` — parse, restructure, write `settlements.yaml`.
3. Rewrite `regions.yaml` without `settlements:` blocks.
4. Copy remaining sword_vale files into appropriate library template dirs.
5. Write `metadata.yaml` for each of the 5 templates.
6. Original sword_vale files stay in place for now (Task 2 converts to manifest).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] `content/library/` has 5 layer type dirs, each with a `sword_vale` template
- [ ] Every template has a valid `metadata.yaml`
- [ ] `settlements.yaml` contains all settlements previously in `regions.yaml`
- [ ] `regions.yaml` in library has no `settlements:` keys
- [ ] Data counts match original sword_vale

## Status

`pending`
