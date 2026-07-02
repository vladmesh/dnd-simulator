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

`pending`
