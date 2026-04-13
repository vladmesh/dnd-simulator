# Task: Level-up via GameService

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 5 — Post-audit cleanup

## Description

`adapters/api/routes_player.py` currently bypasses GameService and calls `rules/` functions directly:

- `perform_level_up()` — used in the `level_up` endpoint
- `xp_to_next_level()` — used in `_player_status()` helper
- `effective_ac()` — used in `_player_status()` helper
- `STARTING_GOLD`, `POINT_BUY_BUDGET` — exposed via `setup-config` (constants, OK to keep direct)

Per CLAUDE.md, adapters translate I/O — they do not call rule functions. Move the level-up + status logic into `GameService` so the adapter only orchestrates HTTP concerns (request parsing, error mapping, response shaping).

## Tests First

Add to `tests/unit/test_game_service_player.py` (create if missing):

- **`service.level_up_player(session_id, fighting_style)` happy path** — Fighter at L1 with `level_up_available=True`, call succeeds, returned PlayerCharacter has `level=2`. Same Character instance is mutated in the session's player slot.
- **`service.level_up_player` no player** — session without a player → raises `ValueError` (adapter maps to 404).
- **`service.level_up_player` no level-up available** — `level_up_available=False` → raises `ValueError` (adapter maps to 400).
- **`service.level_up_player` invalid style** — Paladin L1→L2 with `style=None` → raises `ValueError`.
- **`service.player_status(session_id)`** — returns a dataclass/dict with all the fields currently computed in `_player_status` (level, experience, level_up_available, xp_to_next_level, ac, ability_scores, resource_pools, etc.). Verify a Fighter at L1 reports the expected derived fields.

Then update existing integration tests for `/level-up` if any exist; adapter tests should still pass without change because the public HTTP contract is unchanged.

## Implementation

1. Add `GameService.level_up_player(session_id: str, fighting_style: FightingStyle | None) -> PlayerCharacter` — internally calls `perform_level_up`. Raises `ValueError` on the same conditions; adapter maps.
2. Add `GameService.player_status(session_id: str) -> PlayerStatusData` — a typed return object (dataclass) containing all fields currently computed in the adapter's `_player_status`. Place the return type next to other service-layer DTOs (or in `service/dto.py` if it doesn't exist yet — create it).
3. Adapter `routes_player.py`:
   - Drop imports of `perform_level_up`, `xp_to_next_level`, `effective_ac`, `PlayerCharacter`, `Ability`.
   - `level_up` endpoint becomes: parse request → `service.level_up_player(...)` → return `PlayerStatusResponse` from a small mapper.
   - `_player_status` adapter helper becomes a pure DTO→response mapper (takes the new `PlayerStatusData`, returns `PlayerStatusResponse`).
   - `setup-config` keeps `STARTING_GOLD` / `POINT_BUY_BUDGET` direct imports (constants, no logic).
4. Verify `make check` passes.

## Acceptance Criteria

- [ ] Tests written for the 5 service-level scenarios
- [ ] `routes_player.py` no longer imports from `rules/` (except STARTING_GOLD/POINT_BUY_BUDGET constants) or `core.player`/`core.character`
- [ ] `GameService.level_up_player` and `GameService.player_status` exposed
- [ ] Existing integration tests for `/api/player/...` still pass unchanged
- [ ] `make check` clean

## Status

`pending`
