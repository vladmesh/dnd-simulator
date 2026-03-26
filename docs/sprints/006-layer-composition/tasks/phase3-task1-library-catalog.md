# Task: Library Catalog Service + API

**Date:** 2026-03-26
**Sprint:** 006-layer-composition
**Phase:** 3 — World Assembly Backend

## Description

Create a library catalog module that scans `content/library/` and returns template listings per layer type, with compatibility filtering. Add API endpoints to expose this.

The catalog reads `metadata.yaml` from each template directory. Compatibility is declared explicitly: upper-layer templates declare `requires_geography` or `requires_politics` in their metadata — a list of geography/politics template slugs they're designed for. Geography templates (the base layer) have no requirements. This avoids loading full YAML data for compatibility checks.

**Metadata extension** — add `requires_geography` to politics, settlements, ecology metadata; add `requires_geography` to entities metadata. All current sword_vale templates get `requires_geography: [sword_vale]`. Test_vale is a custom world (not in library), so no changes there.

**New module:** `src/dnd_simulator/content_loader/library.py`
- `list_templates(content_dir, layer_type) -> list[TemplateInfo]` — scan `content/library/{layer_type}/`, read metadata.yaml from each.
- `list_compatible_templates(content_dir, layer_type, selected) -> list[TemplateInfo]` — given already-selected layers (e.g. `{"geography": "sword_vale"}`), return only templates whose `requires_geography` includes the selected geography (or has no requirements).
- `TemplateInfo` frozen dataclass: slug, name, layer_type, version, description, tags, requires_geography.

**New API endpoints** on `routes_master.py`:
- `GET /api/master/library/{layer_type}` — list all templates of this type.
- `GET /api/master/library/{layer_type}?geography=sword_vale` — filtered by compatibility with selected geography.

## Tests First

1. **Catalog scan** — given a temp directory with two geography templates (each with metadata.yaml), `list_templates()` returns both sorted alphabetically. Missing metadata.yaml in a subdirectory raises RuntimeError.

2. **Compatibility filter** — given a settlements template with `requires_geography: [sword_vale]` and another with `requires_geography: [other_world]`, calling `list_compatible_templates(layer_type="settlements", selected={"geography": "sword_vale"})` returns only the first. A template with no `requires_geography` is always compatible (universal).

3. **API endpoint** — FastAPI test client hits `GET /api/master/library/geography` and gets a list including sword_vale. Hits `GET /api/master/library/settlements?geography=sword_vale` and gets sword_vale settlements.

## Implementation

1. Add `requires_geography` field to relevant metadata.yaml files in `content/library/`.
2. Create `src/dnd_simulator/content_loader/library.py` with `TemplateInfo`, `list_templates()`, `list_compatible_templates()`.
3. Add `list_library_templates()` / `list_compatible_library_templates()` methods to `GameService`.
4. Add `GET /api/master/library/{layer_type}` route to `routes_master.py` with optional `geography` query param.
5. Add response schema `TemplateListItem` to `schemas.py`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `GET /api/master/library/geography` returns sword_vale template
- [ ] `GET /api/master/library/settlements?geography=sword_vale` returns compatible templates
- [ ] Incompatible templates are filtered out

## Status

`pending`
