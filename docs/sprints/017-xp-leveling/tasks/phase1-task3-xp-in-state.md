# Task: Expose XP in player state / API payload

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 1 — XP & Leveling Core

## Description

Выставить XP и `level_up_available` в player state payload, который уходит во фронт через REST и WS. Пока без UI модалки (это Phase 3), но фронт уже сможет считать и отобразить прогресс опыта.

**Ключевые точки:**

1. `service/session.py` `build_player_snapshot` (или как он там называется — есть `level` в payload уже) — добавить `experience`, `level_up_available`, `xp_to_next_level`.
2. `adapters/api/routes_player.py` `_player_status()` — аналогично.
3. Frontend types (`frontend/src/types/...`) — добавить поля в Player/Character типы, чтобы TS компилировался. Никакого UI рендера — только shape.

## Tests First

1. **Integration via WS / REST** `tests/integration/test_player_state_xp.py`:
   - Создать сессию, spawn Character L1 + monster CR 1/4. Fetch player state via API. Проверить поля: `experience == 0`, `level == 1`, `level_up_available == False`, `xp_to_next_level == 300`.
   - Character убивает monster. Fetch player state заново. `experience == 50`, `level_up_available == False`, `xp_to_next_level == 250`.
2. **Session snapshot contains XP** — если есть unit-тест build_snapshot, расширить.

## Implementation

**Backend:**

- `service/session.py`: в player snapshot dict добавить `experience`, `level_up_available`, `xp_to_next_level` (последнее — вычислить через `rules/leveling.xp_to_next_level`).
- `adapters/api/routes_player.py` `_player_status()`: те же три поля. Использовать ту же `rules/leveling` функцию.

**Frontend (только типы, без UI):**

- `frontend/src/types/player.ts` (или аналог — надо найти): добавить `experience: number`, `level_up_available: boolean`, `xp_to_next_level: number` в Player type.
- Никаких компонентов / рендера — это Phase 3.

**Gotchas:**

- `xp_to_next_level` считаем на бэке, не на фронте, чтобы не дублировать таблицу. Lean payload.
- Не сломать тесты, которые шейпят player snapshot через точное равенство dict — если такие есть, обновить их expected.

## Acceptance Criteria

- [ ] Integration тест API payload RED
- [ ] Backend snapshot и `_player_status` возвращают три новых поля
- [ ] Frontend TypeScript компилируется с новыми полями в типах
- [ ] `make check` проходит
- [ ] `make frontend` билдится без ошибок типов

## Status

`done`

## Developer Notes

- Added `experience`, `level_up_available`, `xp_to_next_level` to `session._player_to_dict` (turn/round WS payload) and to `PlayerStatusResponse` + `routes_player._player_status` (REST).
- `xp_to_next_level` computed server-side via `rules/leveling.xp_to_next_level` (no duplication on frontend).
- Frontend types: extended `PlayerStatusResponse` (api.ts) and `PlayerStatus` (game.ts) with the three fields. Updated GameScreen test literal.
- Added `xp_value` to `PatchCreatureRequest` + `commands_creatures.patch_creature` — needed to set a testable XP bounty on arbitrary creatures in integration tests (combat_test world's `target_dummy` is a Character with `xp_value=0` by default).
- Integration test gotcha: when all WS listeners disconnect, `GameService._on_session_empty` evicts the session from memory and the next REST call triggers an autosave round-trip. The post-kill status GET must happen BEFORE `sock.close()`, otherwise the session is rebuilt from disk (which doesn't currently preserve XP grant timing cleanly). Tests keep socket open for REST check.
- Also removed allied NPC before combat so kill credit goes to the player (otherwise the ally gets the XP).
