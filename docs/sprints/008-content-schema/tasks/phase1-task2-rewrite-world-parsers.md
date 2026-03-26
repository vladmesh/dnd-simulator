# Task: Rewrite World Structure Parsers

**Date:** 2026-03-26
**Sprint:** 008-content-schema
**Phase:** 1 — Pydantic Content Models + Parser Rewrite

## Description

Rewrite parsers in `content_loader/world.py` to use Pydantic content models from task 1 instead of hand-written `dict[str, Any]` extraction. Each parser becomes: `yaml dict → model_validate → convert to runtime dataclass`.

Functions to rewrite:
- `load_world()` — regions via RegionContent
- `load_locations()` — locations via LocationContent
- `load_nations()` — nations via NationContent
- `load_settlements()` — settlements via SettlementContent
- `load_factions()` — factions (simpler structure, may stay dict-based or get a small model)
- `load_battle_maps()` — battle maps (nested in region, optional)

Each rewritten function:
1. Reads YAML as before (`_load_section` / `_read_yaml`)
2. Validates each entry via `ContentModel.model_validate(data)`
3. Converts to existing runtime dataclass (Region, Location, Nation, Settlement)
4. Returns the same types as before — callers don't change

Conversion functions (`_to_region`, `_to_location`, etc.) map content model → runtime dataclass. These are thin — mostly field copying + ID injection (YAML dict key becomes `id` field).

## Tests First

Unit tests in `tests/unit/test_content_parsers_world.py`:

1. **Round-trip: regions.** Load sword_vale `regions.yaml` → list[Region]. Dump each back to dict via RegionContent → re-validate → fields match originals. Verifies no data loss in the model_validate path.
2. **Round-trip: locations.** Same for locations.yaml.
3. **Round-trip: nations.** Same for nations.yaml.
4. **Round-trip: settlements.** Same for settlements.yaml.
5. **Validation error on bad region.** YAML with `terrain: "lava"` → clear error (Pydantic validation), not a silent KeyError deep in code.
6. **Validation error on missing required field.** Region without `name` → ValidationError, not AttributeError.
7. **Empty YAML returns empty list.** Scaffolded (empty) geography layer → `load_world()` returns `[]`, `load_locations()` returns `[]`.
8. **start_game still works with sword_vale.** Load sword_vale through `GameService.start_game()` → session created, all 5 layers present. This is the integration sanity check — parsers changed but behavior identical.

## Implementation

1. Add conversion functions to `content_loader/world.py` (or a new `content_loader/converters.py` if it gets large):
   - `_to_region(region_id: str, model: RegionContent) -> Region`
   - `_to_location(loc_id: str, model: LocationContent) -> Location`
   - `_to_nation(nation_id: str, model: NationContent) -> Nation`
   - `_to_settlement(settlement_id: str, model: SettlementContent) -> Settlement`
2. Rewrite each `load_*` function to use `ContentModel.model_validate(entry_data)` then convert.
3. Remove all hand-written `ndata.get(...)`, `float(...)`, `str(...)` casting — Pydantic handles this.
4. Keep `resolve_text()` calls for i18n — content models store the raw value (string or dict), resolution happens at conversion time.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] No hand-written dict extraction remains in world.py load functions
- [ ] Bad YAML data produces clear Pydantic ValidationError (not KeyError/TypeError)
- [ ] sword_vale loads and starts a session identically to before

## Status

`done`

## Developer Notes

Rewrote `load_world`, `_parse_locations`, `load_nations`, `load_settlements` to use Pydantic
`model_validate()` on each YAML entry, then convert to runtime dataclasses via thin `_to_*` functions.
`load_battle_maps` and `load_factions` left as-is — battle maps are nested in regions (already validated
by RegionContent), and factions have a simple key-based structure that doesn't benefit from a model.

One existing test updated: `test_manifest_resolver.py::test_missing_region_field_raises` — now expects
`ValidationError` instead of `KeyError`. This is intentional: the task goal is to replace raw dict
extraction with Pydantic validation, which produces `ValidationError` for missing required fields.
