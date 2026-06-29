# Task: Persist player XP & level-up across save/load

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 4 — Save robustness & i18n polish

## Description

Closes backlog `player-xp-not-persisted`. A player's `experience` and `level_up_available` do **not** survive the modern save/reload path. `Character` defines both fields (`core/character.py:275-276`), but they are dropped on serialize and never restored on load:

- **Save** (`save_game`/`autosave_session` → `world.save()` → `EntitiesLayer.get_state()` → `PlayerCharacter.to_full_save_data()`): `to_full_save_data()` (`core/player.py:74-113`) does not emit `experience`/`level_up_available`.
- **Load** (`load_game` → `world.load()` → `EntitiesLayer.load_state()` → `parse_player()` → `PlayerContent.model_validate` → `_to_player()`): none of `PlayerContent` (`content_loader/schemas.py:431-457`), `_to_player()` (`content_loader/creatures.py:216-265`), or the existing-entity re-apply block in `load_state()` (`layers/entities/layer.py:600-602`) reads the fields. On reload XP resets to the content default (0).

`PlayerCharacter.load_save_data()` *does* restore both, but it only runs on the legacy `"player"`-block branch of `load_game` (`commands_save.py:71`), which modern saves never hit. This also breaks live dev level-up: the StrictMode evict→restore cycle (now grace-period guarded after phase 3) runs the player through this same save path, zeroing XP and making `POST /level-up` return 400.

Fix: round-trip `experience`/`level_up_available` through the modern path. `current_hp` is already a save-restore field carried on `PlayerContent` — follow that exact precedent.

## Tests First

Product-level, exercise the real `world.save()` → `world.load()` round-trip (not just the dict):

1. **Level-up flag survives reload.** A Fighter earns enough XP from a kill to cross the L2 threshold (`level_up_available` becomes `True`). Save the world, build a fresh world, load the save. The reloaded player has the same `experience` and `level_up_available is True`, and `GameService.level_up_player` (or the rule it calls) still succeeds — it does not 400 on `experience=0`.
2. **Mid-level XP value round-trips exactly.** A player with `experience=150` (below the next threshold, `level_up_available=False`) survives save→reload with `experience == 150` and `level_up_available is False` — not reset to 0, not flipped on.
3. **Autosave→load preserves XP (regression for the dev evict path).** Drive a session that grants the player XP, `autosave_session`, then `load_game` the autosave into a fresh session — `experience` is preserved. This is the path the dev StrictMode evict→restore takes.

Extend `tests/integration/test_save_roundtrip.py` (already covers hp/gold/ai_type) and/or `tests/integration/test_player_state_xp.py` rather than adding a new file, if they fit.

## Implementation

Four sites, mirroring how `current_hp`/`gold` are already handled:

1. `core/player.py` `to_full_save_data()` — add `"experience": self.experience` and `"level_up_available": self.level_up_available` to the `data` dict.
2. `content_loader/schemas.py` `PlayerContent` — add `experience: int = 0` and `level_up_available: bool = False` (save-restore fields riding the content schema, exactly like `current_hp: int | None`).
3. `content_loader/creatures.py` `_to_player()` — pass `experience=model.experience, level_up_available=model.level_up_available` into the `PlayerCharacter(...)` constructor.
4. `layers/entities/layer.py` `load_state()` — in the existing-entity re-apply block (`~600-602`, where `current_hp`/`gold` are re-read from `edata`), also set `entity.experience = int(edata.get("experience", entity.experience))` and `entity.level_up_available = bool(edata.get("level_up_available", entity.level_up_available))`. Both branches matter: fresh `parse_player` (entity is None) picks them up via `PlayerContent`; the already-present branch re-applies them here.

Gotcha: leave `load_save_data()` as-is (legacy branch) — it already restores these; the change is to make the *modern* path match.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `experience` and `level_up_available` survive `world.save()`→`world.load()` and `autosave_session`→`load_game`
- [ ] A reloaded player who was eligible to level up can still level up (no 400)
- [ ] `player-xp-not-persisted` marked resolved in `docs/BACKLOG.md`

## Status

`pending`
