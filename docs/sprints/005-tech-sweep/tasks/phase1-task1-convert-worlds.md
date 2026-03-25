# Task: Convert all single-file worlds to directory format

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 1 — Content Standardization

## Description

Split all 7 single-file YAML worlds into the directory format used by `sword_vale/`. Each world becomes a directory with separate files: `world.yaml`, `regions.yaml`, `locations.yaml`, `nations.yaml`, `npcs.yaml`, `monsters.yaml`, `squads.yaml`, `factions.yaml`.

**Production worlds (3):** `content/worlds/arena.yaml`, `village.yaml`, `sneak_test.yaml`
**Integration test worlds (4):** `tests/integration/content/worlds/arena.yaml`, `village.yaml`, `sneak_test.yaml`, `squad_world.yaml`

After conversion, delete the original single `.yaml` files.

## Tests First

- Load each converted production world via `load_world()`, `load_locations()`, `load_npcs()`, `load_nations()`, `load_settlements()`, `load_battle_maps()`, `load_factions()`, `load_monsters()`, `load_squads()` — assert same entity counts and IDs as before conversion.
- Load `arena` directory: 1 region, 1 location, 4 NPCs (razor, shadow, iron, paladin), battle map 80x80 with 4 walls.
- Load `village` directory: 1 region, 8 locations, 5 NPCs (olga, sergei, masha, ivan, tanya), 1 settlement (millbrook).
- Load `sneak_test` directory: 1 region, 1 location, 1 NPC (dummy), battle map 40x40.
- `load_world_meta()` returns correct name and description for each world.

## Implementation

For each world file:
1. Create directory `content/worlds/<name>/`
2. Extract `name` + `description` → `world.yaml`
3. Extract `regions` → `regions.yaml`
4. Extract `locations` → `locations.yaml`
5. Extract `nations` → `nations.yaml` (even if empty — `{}`)
6. Extract `npcs` → `npcs.yaml` (even if empty — `{}`)
7. Extract `monsters` → `monsters.yaml` (if present)
8. Extract `squads` → `squads.yaml` (if present)
9. Extract `factions` → `factions.yaml` (if present)
10. Delete original `.yaml` file

Same process for integration test worlds under `tests/integration/content/worlds/`.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] All 7 worlds converted to directory format
- [x] Original single-file `.yaml` files deleted
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Used `yaml.dump` to split files programmatically. Output formatting is less pretty than hand-written YAML (flow-style lists become block, multiline strings get quoted) but loads identically. Battle map wall tests needed adjustment — `BattleMap` auto-adds 4 boundary walls, so arena has 8 total (4 authored + 4 boundary) and sneak_test has 4 (0 authored + 4 boundary).
