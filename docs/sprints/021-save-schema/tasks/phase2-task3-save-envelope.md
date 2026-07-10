# Task: SaveGame-конверт, schema_version=1, единый путь загрузки

**Date:** 2026-07-10
**Sprint:** 021-save-schema
**Phase:** 2 — Unified Pydantic save schema

## Description

Корневая модель сейва поверх task 1-2: `SaveGame(schema_version=1, meta: SaveMeta, world: WorldSave)`, где `WorldSave` = seed, dice_rng_state (глобальный RNG из `rules/dice.py` — `getstate()`/`setstate()`), time, last_tick_times, layers (стейты слоёв из task 1-2 как typed submodels или passthrough-dict от слоёв — выбрать одно и зафиксировать; typed предпочтительнее: конверт живёт вне core и может импортировать модели слоёв).

Единый путь: `service/commands_save.py` — `save_game()` и `autosave_session()` собирают один и тот же `SaveGame` (сейчас `save_game` не пишет `meta` — устранить), `load_game()` валидирует через `SaveGame.model_validate` и грузит. Legacy-фолбэки удаляются: ветки «нет world-ключа», «flat world», «top-level player» в `commands_save.py:49-73`, `.get()`-дефолты в `World.load` (`core/world.py:163`). Сейв без `schema_version` или с неожиданной версией → понятная ошибка загрузки («несовместимый сейв»), не попытка угадать. `World.save()`/`load()` могут остаться dict-мостом (core без pydantic), конверт валидирует снаружи.

Модуль конверта: `storage/save_schema.py` или `service/save_schema.py` — вне core, может импортировать layer-модели; `JsonFileStore` не меняется (dict на входе/выходе).

## Tests First

- Полный round-trip через сервис: сессия с игроком, NPC, экипировкой, активным combat → `save_game` → `load_game` в свежий сервис → идентичное состояние, раунд продолжается; dice-RNG продолжает последовательность бросков (бросок после load == бросок после save на оригинале).
- `autosave_session` и `save_game` производят одинаковую структуру (оба с `meta` и `schema_version`).
- Legacy-сейв (без `schema_version` / старый формат) → отказ с внятной ошибкой, не crash и не тихая полу-загрузка.
- `tests/integration/test_save_roundtrip.py` перепинован на новый формат и зелёный.

## Implementation

После красных тестов: конверт-модель, перевод `commands_save`, чистка `World.load` от компат-дефолтов (см. также `GameDateTime.from_dict` — дефолт `second=0` оставить: это не legacy-сейв, а нормализация), удаление legacy-веток и их тестов, обновление round-trip тестов. Проверить `_on_session_empty`-автосейв и shutdown-автосейв на новом пути (они зовут те же функции). Существующие сейвы в `saves/` станут несовместимыми — это принятое решение спринта (Decisions).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check-backend`); `make test-integration` зелёный
- [ ] Один путь сборки и один путь загрузки сейва; legacy-ветки удалены
- [ ] `schema_version=1` в каждом сейве; dice-RNG state в сейве и продолжается после load

## Status

`done`

## Developer Notes

Added the versioned `SaveGame` envelope in `storage/save_schema.py` with `schema_version=1`, meta, typed layer states, and dice RNG state. `save_game()` and `autosave_session()` now use the same envelope builder; `load_game()` validates the envelope and rejects legacy saves without `schema_version`. Autosave restore now validates the same schema and restores dice RNG before loading world state.
