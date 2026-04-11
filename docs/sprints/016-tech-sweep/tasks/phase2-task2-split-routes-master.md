# Task: Split routes_master.py into routes_world + routes_session

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 2 — Adapter & Routes

## Description

After task 1 extracts the thick logic, `routes_master.py` (560 lines, 32 routes) is all thin delegation but still a monolith. Split it into two focused modules:

1. **`routes_world.py`** — world management, library templates, content editing (14 routes, prefix `/api/master`):
   - `GET /library/{layer_type}` — list templates
   - `GET|POST /worlds` — list/create worlds
   - `POST /worlds/assemble` — assemble world
   - `POST /worlds/{id}/fork` — fork world
   - `DELETE /worlds/{id}` — delete world
   - `GET /worlds/{id}` — get world template
   - `GET /worlds/{id}/manifest` — get manifest
   - `GET|PUT /worlds/{id}/layers/{type}/files[/{filename}]` — layer file CRUD
   - `POST /worlds/{id}/layers/{type}/scaffold` — scaffold layer
   - `POST /worlds/{id}/fork/{type}` — fork layer

2. **`routes_session.py`** — session lifecycle, runtime controls, creatures, saves (18 routes, prefix `/api/master`):
   - `GET|POST /sessions` — list/create sessions
   - `GET|DELETE /sessions/{id}` — state/delete
   - Creature CRUD (7 routes)
   - Politics/settlement patch (2 routes)
   - Time advance, language set
   - Save/load/delete (4 routes)

Delete `routes_master.py` after the split. Update `app.py` to import the two new routers.

## Tests First

1. **Integration test: all world management endpoints respond correctly** — hit `GET /worlds`, `GET /library/geography`, `GET /worlds/{id}/manifest` on a known world. Verify status codes and basic response shapes. These routes exist today but have no dedicated integration coverage — adding a `TestWorldManagement` class ensures the split didn't break wiring.

2. **Integration test: session runtime endpoints still work** — the existing `TestSessionLifecycle` and creature tests in `test_rest_api.py` cover this. Verify they pass after the split (no new tests needed).

## Implementation

1. Create `routes_world.py`: move library + worlds + layer-files routes (lines 44–265) from `routes_master.py`. Own `APIRouter(prefix="/api/master", tags=["world-management"])`.
2. Create `routes_session.py`: move sessions + creatures + politics + time + saves + lang routes (lines 269–560). Own `APIRouter(prefix="/api/master", tags=["session"])`.
3. Move shared helpers (`_get_session`, `_format_time`, `_creature_to_response`) to whichever module uses them. If both need them, put in a small `routes_helpers.py`.
4. Update `app.py`: replace `routes_master` import with `routes_world` + `routes_session`.
5. Delete `routes_master.py`.
6. Run `make check` — mypy, lint, all tests green.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `routes_master.py` no longer exists
- [ ] Two new files: `routes_world.py` (< 250 lines) and `routes_session.py` (< 350 lines)
- [ ] `app.py` imports both new routers, no reference to `routes_master`
- [ ] All existing API endpoints still accessible (same paths, same behavior)

## Status

`pending`
