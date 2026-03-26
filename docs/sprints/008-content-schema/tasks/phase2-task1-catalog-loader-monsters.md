# Task: Catalog Loader + Monster Catalog

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 2 — Catalogs — Monsters + Items

## Description

Create global catalog infrastructure and migrate monster templates from world YAML into standalone catalog files.

**Catalog structure:**
```
content/catalogs/monsters/
  goblin.yaml       # one file per monster
  wolf.yaml
  bandit.yaml
```

Each catalog file is a standalone YAML dict matching `MonsterTemplateContent` schema (name, hp, ac, speed, cr, ability_scores, attacks, faction). The filename (without `.yaml`) is the catalog ID.

**Generic catalog loader** in `content_loader/catalogs.py`:
- `load_catalog(catalog_dir: Path, schema: type[BaseModel]) -> dict[str, BaseModel]` — read all `.yaml` files from a directory, validate each against the given Pydantic model, return dict keyed by filename stem.
- Fail fast: unknown files, validation errors → RuntimeError.

**Monster reference format** — world `monsters.yaml` changes from inline templates to catalog references:
```yaml
templates:
  goblin:
    base: goblin          # catalog ID (required)
    # optional field overrides
    hp: 10                # stronger goblins in this world
    faction: dark_goblin  # different faction

encounters:
  # unchanged
```

When `base` is present, load the catalog entry and merge overrides on top. Pure inline templates (without `base`) still work for world-specific monsters not in any catalog.

**Update `load_monsters()`** to accept `catalog: dict[str, MonsterTemplateContent]` and resolve `base` references before converting to runtime `MonsterTemplate`.

**Migrate sword_vale:** extract 3 templates (goblin, wolf, bandit) to catalog files. Update `content/library/ecology/sword_vale/monsters.yaml` to use `base:` references.

## Tests First

1. **Catalog loader — loads all YAML files from directory, indexes by filename stem.** Create a temp directory with 2 monster YAML files, call `load_catalog()`, verify both returned with correct IDs and validated fields.

2. **Catalog loader — fails on invalid YAML.** Put a malformed file in the catalog dir, verify RuntimeError with clear message.

3. **Monster reference resolution — base only.** A world template with `base: goblin` and no overrides produces a MonsterTemplate identical to the catalog entry.

4. **Monster reference resolution — base + overrides.** A world template with `base: goblin` and `hp: 20` produces a MonsterTemplate with the catalog's stats but HP=20.

5. **Monster reference resolution — inline (no base) still works.** A world template without `base` is parsed exactly as before — full inline definition required.

6. **Monster reference resolution — unknown base fails.** A template referencing `base: dragon` when no dragon in catalog → RuntimeError.

7. **Round-trip: catalog file → load → resolve in world → runtime MonsterTemplate.** Load goblin from catalog, reference it in a world with faction override, verify the resulting MonsterTemplate has catalog stats + overridden faction.

## Implementation

After tests are red:

1. Create `content/catalogs/monsters/` with `goblin.yaml`, `wolf.yaml`, `bandit.yaml` — extracted from `content/library/ecology/sword_vale/monsters.yaml`.

2. Create `src/dnd_simulator/content_loader/catalogs.py`:
   - `load_catalog(catalog_dir: Path, schema: type[T]) -> dict[str, T]` — generic loader.
   - `load_monster_catalog(content_dir: Path) -> dict[str, MonsterTemplateContent]` — convenience wrapper.

3. Add `MonsterRefContent` Pydantic model to `schemas.py` — a template entry that has optional `base: str` plus all `MonsterTemplateContent` fields as optional (for overrides). Or use a discriminated approach: if `base` is present, it's a reference; otherwise it's inline.

4. Update `content_loader/monsters.py`:
   - `load_monsters()` gains `catalog` parameter.
   - Template parsing: if `base` present → load from catalog, apply overrides. If not → parse as full inline template (existing behavior).

5. Update `content/library/ecology/sword_vale/monsters.yaml` — templates become `base:` references.

6. Keep `encounters` section unchanged — it already references template IDs.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Catalog files created in `content/catalogs/monsters/`
- [ ] sword_vale monsters.yaml uses `base:` references
- [ ] Inline templates (without `base`) still work
- [ ] `load_catalog()` is generic — reusable for items in task 2

## Status

`done`

## Developer Notes

Implemented generic `load_catalog()` with PEP 695 type params in `content_loader/catalogs.py`. Added `resolve_monster_template()` to `monsters.py` — handles `base:` references with field overrides via `model_dump(by_alias=True)` + dict merge. Updated `load_monsters()` to accept optional `catalog` param.

Wired catalog loading into `game_service.py` — loads from `content/catalogs/monsters/` if the directory exists, passes to `load_monsters()`. Test fixture helpers that create isolated content dirs now symlink `catalogs/` alongside `library/`.

Old tests in `test_content_parsers_creatures.py` updated to pass the catalog — intentional contract change since sword_vale now uses `base:` references.
