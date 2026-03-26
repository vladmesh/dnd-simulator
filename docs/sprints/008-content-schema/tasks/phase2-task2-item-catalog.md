# Task: Item Catalog + NPC Equipment References

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 2 — Catalogs — Monsters + Items

## Description

Create a global item catalog and update NPC/player YAML to reference catalog items instead of inline definitions.

**Catalog structure:**
```
content/catalogs/items/
  dagger.yaml
  health_potion.yaml
  longsword.yaml
  ...
```

Each catalog file is a standalone YAML dict matching `ItemContent` schema (name, type, weapon fields, armor fields, etc.). The filename stem is the catalog ID. Catalog items do NOT include `equipped` or `price` — those are per-NPC overrides.

**NPC item reference format** — items in NPC YAML change from inline to references:
```yaml
items:
  - ref: dagger           # catalog ID
    equipped: true         # NPC-specific override
    price: 200             # NPC-specific override (merchant price)
  - ref: health_potion
    price: 50
  - name: Custom Artifact  # inline item (no ref) still works
    type: weapon
    weapon_id: artifact
    ...
```

When `ref` is present, load the catalog entry and merge NPC-specific overrides on top. Pure inline items (without `ref`) still work.

**Update `parse_items()`** to accept `item_catalog: dict[str, ItemContent]` and resolve `ref` fields before converting to runtime `Item`.

**Migrate sword_vale:** extract Gretta's items (health potion, dagger) to catalog. Update `content/library/entities/sword_vale/npcs.yaml` to use `ref:` references.

## Tests First

1. **Item catalog loads all YAML files from directory.** Create temp dir with dagger.yaml and health_potion.yaml, call `load_catalog()` with `ItemContent`, verify both loaded with correct IDs.

2. **NPC item reference — ref only.** An NPC item with `ref: dagger` resolves to the catalog dagger definition with auto-generated ID.

3. **NPC item reference — ref + overrides.** An NPC item with `ref: dagger, equipped: true, price: 200` resolves to catalog dagger with equipped=true and price=200.

4. **NPC item reference — inline (no ref) still works.** An item without `ref` parses exactly as before — full inline definition required.

5. **NPC item reference — unknown ref fails.** An item with `ref: vorpal_sword` when no such catalog entry → RuntimeError.

6. **Merchant inventory from catalog refs.** Load an NPC with `role: merchant` and catalog-referenced items, verify the merchant's inventory has correct items with prices, and they appear in awareness/trading context.

7. **Player items from catalog refs.** Player YAML with `ref: longsword, equipped: true` resolves correctly, player has the weapon equipped.

## Implementation

After tests are red:

1. Create `content/catalogs/items/` with `dagger.yaml`, `health_potion.yaml` — extracted from Gretta's inventory in npcs.yaml.

2. Add `load_item_catalog(content_dir: Path) -> dict[str, ItemContent]` to `content_loader/catalogs.py` — uses the generic `load_catalog()` from task 1.

3. Update `ItemContent` in `schemas.py` — add optional `ref: str | None = None` field. When present, signals "resolve from catalog."

4. Update `content_loader/items.py`:
   - `parse_items()` gains `item_catalog` parameter (default empty dict for backward compat).
   - If item dict has `ref` → load base from catalog, merge overrides (equipped, price, any other fields), then convert to runtime Item.
   - If no `ref` → existing inline parsing.

5. Update `content_loader/creatures.py`:
   - `load_npcs()` and `parse_npc()` pass `item_catalog` through to `parse_items()`.
   - `parse_player()` same treatment.

6. Update `content/library/entities/sword_vale/npcs.yaml` — Gretta's items become `ref:` references.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Catalog files created in `content/catalogs/items/`
- [ ] sword_vale NPC items use `ref:` references
- [ ] Inline items (without `ref`) still work
- [ ] Equipped/price overrides work correctly
- [ ] Player items can use catalog refs too

## Status

`pending`
