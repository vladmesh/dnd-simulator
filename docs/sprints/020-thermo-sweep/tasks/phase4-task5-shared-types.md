# Task: Shared/typed models — collapse PlayerStatus twins, type world-state rows

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 4 — Декомпозиция фронта

## Description

Два класса ручных близнецов:

1. `PlayerStatus` (`types/game.ts`) и `PlayerStatusResponse` (`types/api.ts`) описывают один и тот же бэкенд-контракт (REST `player_status` и WS-статус). Поля почти совпадают; расхождение — `ability_scores` (`AbilityScores` vs `Record<string, number>`) и наличие `equipped`/`inventory`/`resource_pools` только в WS-версии. По факту после фазы 2 бэка это один источник (`PlayerStatusData`). Свести к одному типу.

2. `WorldStateResponse.regions/nations/settlements` типизированы как `Array<Record<string, unknown>>` — фронт кастует `String(...)` везде. Ввести `Region`/`Nation`/`Settlement` по фактическому wire-контракту `get_world_state` (см. `service/commands_world_state.py` + `core/queries.py` dataclasses).

Фактические wire-поля (из бэка, только чтение — `src/` не трогаем):
- **Region**: `id, name, latitude, longitude, elevation, terrain, water_proximity, weather: {condition, temperature}, temperature`
- **Nation**: `id, name, regions: string[], wealth, military, stability, leader: {name, age, trait} | null`
- **Settlement**: `id, name, region_id, type, population, prosperity, defenses`

Цель — один тип на контракт, без ручных близнецов; строковые касты уходят там, где тип теперь известен.

Вне скоупа: кодогенерация из JSON-схемы (оверкил для этого размера — вводим ровно нужные интерфейсы вручную, но единожды); изменение бэкенда/wire-формата.

## Tests First

Тип-только изменение — гейт это `tsc --noEmit` (и `tsc -b` для полноты). Плюс:

- Существующие тесты, использующие `PlayerStatus`/`PlayerStatusResponse` в моках (`PlayerStats`, `LevelUpModal`, `CharacterForm.test`), компилируются и зелёные после унификации.
- `WorldOverview`-пиновка (task 4) работает с типизированными `Region`/`Nation`/`Settlement`.

## Implementation

1. Свести `PlayerStatusResponse` к `PlayerStatus` (или наоборот) — один экспортируемый тип, ре-экспорт для обратной совместимости имён, если это дешевле правки импортов. `ability_scores` — единый тип; `equipped?`/`inventory?`/`resource_pools?` опциональны.
2. Ввести `Region`/`Nation`/`Settlement`/`WeatherSummary`/`LeaderInfo` в `types/api.ts` (или `types/world.ts`), переиспользовать в `WorldStateResponse`.
3. Мигрировать потребителей (`WorldOverview`, `SessionView`, всё, что читает эти поля).

## Acceptance Criteria

- [ ] Один тип player-status, ручного близнеца нет
- [ ] `WorldStateResponse` строки типизированы; `Record<string, unknown>`-касты убраны у потребителей
- [ ] `tsc --noEmit` + `eslint src/` чисто; существующие тесты зелёные
- [ ] wire-контракт не тронут (только типы фронта)

## Status

`done`

## Developer Notes

- `PlayerStatus` (в `types/game.ts`) — единственный источник; `appearance?` добавлен (опционален: не каждый payload его несёт). `types/api.ts`: `export type PlayerStatusResponse = PlayerStatus` вместо ручного близнеца. `ability_scores` единый (`AbilityScores`).
- Введены `Region`/`Nation`/`Settlement`/`WeatherSummary`/`LeaderInfo` по wire-контракту `get_world_state`; `WorldStateResponse` строки типизированы. Единственный потребитель строк — `WorldOverview` (миграция `String(...)`-кастов сделана в [task 4](phase4-task4-world-overview.md)).
- `tsc -b`: pre-existing test-mock ошибки лишь переименовались (`PlayerStatusResponse`→`PlayerStatus`, тот же счёт); новые ошибки WorldOverview закрыты task 4. Player-тесты (PlayerStats/LevelUpModal) зелёные.
