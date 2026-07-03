# Task: App-level exception handlers + единый player-status

**Date:** 2026-07-02
**Sprint:** 020-thermo-sweep
**Phase:** 2 — Типизация границ + enums

## Description

Две adapter-унификации из ревью.

**Exception handlers.** `app.py:88-96` уже центрально маппит `SessionNotFoundError`/`PlayerNotFoundError`; остальное — руками в каждом роуте (routes_content 10+ лестниц, routes_session 14, routes_world 11):

- Зарегистрировать app-level handlers для однозначных типов: `FileNotFoundError → 404`, `ValidationError → 422`, `FileExistsError → 409`, `KeyError → 404`. Убрать соответствующие ветки из роутов.
- `ValueError` маппится в разные статусы по роутам (400/404/409/403) — центральный handler невозможен без потери статусов. Оставить локальные `except ValueError` как есть; где ValueError фактически означает доменную ситуацию с нестандартным статусом (`routes_world.py:149` → 403, `:230,:243` → 409), можно ввести узкие доменные исключения по образцу фазы 1 — по месту, без сквозной переделки service-слоя.
- Content type-guard: дубль `if et not in _LAYER_ENTITY_TYPES: raise 400` ×6 и зеркальный catalog-guard ×5 (`routes_content.py:45-49,60,76,91,108,129,138,148,161,174`) → FastAPI dependency / helper `_require_entity_type(raw, kind=...)`, один источник.

**Player-status.** Три ручных копии одного набора из 19 полей + реальный дрейф (WS теряет `appearance`):

- `GameService.player_status` (`commands_player.py:153-201`, строит `PlayerStatusData`) — единственный источник.
- `session.py:164-197` `_player_to_dict` удалить; WS-путь (`:381,419`) берёт `dataclasses.asdict(...)` от того же билдера. WS-payload получает `appearance` — аддитивное изменение, фронт не сломается.
- `routes_player.py:76-99` `_to_response` (ручное перечисление 19 полей) → `PlayerStatusResponse.model_validate(dataclasses.asdict(data))` (имена/типы совпадают 1:1).

Вне скоупа: фронтовые близнецы `PlayerStatus`/`PlayerStatusResponse` (фаза 4), `GiveItemRequest`-union (не в фазе), WS-race `session-disconnect-debounce`.

## Tests First

- Пиновка статусов до рефактора (GREEN): параметризованный проход по роутам — несуществующий мир/сессия → 404, дубликат мира → 409, catalog-тип на layer-роуте → 400, layer-тип на catalog-роуте → 400, невалидный content-payload → 422, невалидный entity_type → 422 (дописать недостающие в test_content_api/test_rest_api).
- RED: WS/REST-паритет — player-словарь из round_state (WS-путь) имеет тот же набор ключей, что `asdict(player_status(...))`, включая `appearance`. Сейчас падает: `_player_to_dict` теряет appearance.
- Пиновка: `PlayerStatusResponse` из REST `GET /player/status` — прежний JSON (test_player_state_xp / test_rest_api).

## Implementation

1. Сначала пиновочные статус-тесты, потом handlers + зачистка веток в роутах. KeyError-handler проверить на конфликт: KeyError в разных роутах всегда 404 (разведка подтверждает) — если найдётся исключение, оставить локально.
2. Player-status: удалить `_player_to_dict`, WS собирает через билдер; `_to_response` → `model_validate(asdict(...))`.

Gotcha: `player_status` на `GameServiceProtocol` — WS-код (`session.py`) должен получить `PlayerStatusData` без повторного вычисления awareness; билдер уже отдельная функция, переиспользовать её напрямую.

## Acceptance Criteria

- [ ] Статус-пиновка написана и GREEN до рефактора; WS-паритет тест RED до фикса
- [ ] В routes_content не осталось копий type-guard'а; в роутах нет веток для FileNotFound/Validation/FileExists/KeyError
- [ ] `_player_to_dict` и ручной `_to_response` удалены; один источник — `player_status`
- [ ] WS-payload игрока содержит `appearance`
- [ ] `make check` зелёный

## Status

`done`

## Developer Notes

**Exception handlers.** Registered four app-level handlers in `app.py` via a `_status_handler(status)` factory: `FileNotFoundError → 404`, `KeyError → 404`, `FileExistsError → 409`, `ValidationError → 422`. Local `try/except` still wins (Starlette only calls app handlers for otherwise-unhandled exceptions).

Gotcha found during GREEN: pydantic v2 `ValidationError` **is a subclass of `ValueError`**. Routes that catch `ValueError → 400` (create/update entity, create catalog entry) would swallow a `ValidationError` before it reached the global 422 handler and return 400. Kept the local `except ValidationError → 422` branch ahead of `except ValueError` in those three routes to preserve behavior. The global 422 handler still serves routes with no local `ValueError` catch (e.g. `update_catalog_entry`, now bare).

Behavior-preservation deviation from the literal "no FileNotFound/FileExists branches in routes" criterion: `routes_world` routes with a **custom localized detail** (`get_world_template`, `get_world_manifest` → i18n "World '{}' not found"; `create_world`, `assemble_world` → i18n "already exists") keep their local branches. Removing them would swap the localized message for `str(exc)` (a raw path). Only plain `→ status, detail=str(exc)` branches were removed (fork_world, delete_world's FileNotFound, layer file/scaffold/fork routes). `routes_content` had all-plain branches → fully removed.

KeyError conflict: `spawn_creature` maps `KeyError → 400` (not 404). Kept its local `except (ValueError, KeyError, RuntimeError) → 400`; local catch wins over the global 404. All other KeyError sites were 404, now rely on the global handler.

**Content type-guard.** `_require_entity_type(raw, *, catalog: bool)` in `routes_content.py` folds parse (422) + layer/catalog guard (400) into one helper; removed the 11 copy-pasted `if et not in _..._ENTITY_TYPES` blocks.

**Player-status.** New `build_player_status(player) -> PlayerStatusData` in `session.py` is the single source. `commands_player.player_status` delegates to it; the two WS round-state call sites use `dataclasses.asdict(build_player_status(player))`; `routes_player._to_response` is now a one-line `PlayerStatusResponse.model_validate(dataclasses.asdict(data))`. Deleted `_player_to_dict`. WS payload now carries `appearance` (was dropped) — additive.

Old tests updated for the contract change (`_player_to_dict` → `build_player_status`): `test_session_awareness.py` (resource pools), `test_inventory_awareness.py` (equipped/inventory) now assert on the `PlayerStatusData` dataclass. Added: WS/REST parity test in `test_session_round_state.py` (RED before fix — missing `appearance`), type-guard status pins in unit `test_content_api.py`.
