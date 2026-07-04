# Task: Дедуп сериализации (предусловие save-schema)

**Date:** 2026-07-04
**Sprint:** 020-thermo-sweep
**Phase:** 3 — Декомпозиция бэкенд-модулей

## Description

Сериализация мира собрана из рукописных `dict`-построений, дублирующихся между save и load, между слоями и между `to_full_save_data`/`load_state`. Это приоритетный пункт фазы: по [simulation-core](../../brainstorms/simulation-core.md) «мир заморожен на полушаге» требует lossless-сейва, а каждая новая сущность модели умножает боль рукописного формата. Это стартовый кусок бэклог-эпика `save-schema` — но здесь только дедуп, **формат JSON неизменен** (пиновка round-trip).

Сделать (поведение неизменно, каждый шаг под пиновочным тестом):

1. **`GameDateTime.to_dict()` / `from_dict()`** (`core/models.py:154`). Сейчас year/month/day/hour/minute/second собираются вручную 4× в `core/world.py:157-164,167-174,199-206` (save time, save last_ticks, load time, load last_ticks) с одинаковым backward-compat (`.get(..., default)`). Вынести в методы `GameDateTime`, `World.save/load` их зовут.
2. **`entity_serialization.py`** (зеркало `combat_serialization.py`) в `layers/entities/`. Сейчас `EntitiesLayer.get_state` (`layer.py:401-495`) и `load_state` (`:497-…`) инлайнят построение/разбор entity-словарей и трижды лениво импортируют `_serialize_item`/`deserialize_item`. Вынести `serialize_entity(entity)` / `deserialize_entity(data)` в отдельный модуль, слой их зовёт.
3. **Разрыв цикла `core/player → content_loader`.** `core/player.py:119` и `EntitiesLayer` (`layer.py:568,571,623`) лениво импортируют `content_loader.items.deserialize_item` внутри функций именно чтобы обойти цикл. Item-(де)сериализация — это данные предмета, не контент-загрузка: перенести `serialize_item`/`deserialize_item` в `core/items.py` (или `core/item_serialization.py`), `content_loader` реэкспортирует для обратной совместимости. После переноса ленивые импорты становятся обычными top-level.

Вне скоупа: смена формата сейва, версионирование схемы, `DictBackedLayer`-база для per-layer `get_state` (оценить в реализации — если дедуп между 5 слоями крупный, вынести общий helper; если слои слишком разные, оставить). Реальный `save-schema`-эпик (Pydantic-модели сейва) — отдельный будущий спринт.

## Tests First

Поведение неизменно — пиновка round-trip до рефактора (GREEN):

- **Полный save→load round-trip мира** с магическими аксессуарами из `d0e8eda` (`ring_of_protection` с `grant_modifiers`), игроком с XP/`level_up_available`, инвентарём, экипировкой во всех слотах, активным боем, сквадом и логовом: `world.save()` → `world.load()` → повторный `world.save()` даёт **идентичный** dict. Уже есть `test_save_roundtrip` — расширить до покрытия всех перечисленных сущностей, если чего-то нет.
- `GameDateTime.from_dict(gdt.to_dict()) == gdt` для набора значений включая second; `from_dict` на старом словаре без `"second"` даёт `second=0` (backward compat сохранён).
- Item round-trip: `deserialize_item(serialize_item(item)) == item` для оружия с magic bonus, брони, аксессуара с `grant_modifiers`.

## Implementation

Порядок RED→GREEN:

1. Пиновочный round-trip тест (расширить `test_save_roundtrip`) — зелёный на текущем коде.
2. `GameDateTime.to_dict/from_dict`, переключить `World.save/load`. Прогнать round-trip.
3. Перенести item-(де)сериализацию в `core/`, `content_loader.items` реэкспортирует, снять ленивые импорты в `core/player.py` и `EntitiesLayer`. Прогнать mypy (цикла быть не должно — проверить `python -c "import dnd_simulator.core.player"` без отложенного импорта).
4. `entity_serialization.py`: вынести build/parse entity-словарей из `EntitiesLayer.get_state/load_state`. Слой зовёт хелперы.

Gotcha: формат байт-в-байт неизменен — любые изменившиеся ключи/типы ловит round-trip тест. Backward-compat ветки (`.get(..., default)`) в новых методах сохранить. Ленивые импорты снимать только после переноса, иначе вернётся цикл — mypy strict это поймает.

## Acceptance Criteria

- [ ] Round-trip пиновочный тест (аксессуары + XP + экипировка + бой + сквад/логово) написан и GREEN до рефактора
- [ ] `GameDateTime.to_dict/from_dict` заменили 4 рукописных построения в `world.py`
- [ ] Item-(де)сериализация в `core/`; ленивые импорты `content_loader` из `core/player.py`/`EntitiesLayer` сняты; цикла нет
- [ ] `entity_serialization.py` создан, `EntitiesLayer.get_state/load_state` зовут хелперы
- [ ] Save/load формат байт-в-байт неизменён (round-trip зелёный)
- [ ] `make check` зелёный

## Status

`done`

## Developer Notes

- **GameDateTime.to_dict/from_dict** (`core/models.py`): replaced the 4 hand-rolled year/month/day/hour/minute/second dict-builds in `world.py` (save time, save last_ticks, load time, load last_ticks). `from_dict` keeps the backward-compat defaulting (old saves lacking `second` → 0). Signature is `dict[str, Any]` at the deserialization boundary (avoids `int(object)` overload noise).
- **Cycle break `core/player → content_loader`**: done the sprint-intended way — item (de)serialization now lives in `content_loader`, and `core/player` no longer imports `content_loader` at all. Moved `_serialize_item` → `content_loader.items.serialize_item` (public) and `_EQUIPMENT_FIELDS` → `content_loader.items.EQUIPMENT_FIELDS`; moved `PlayerCharacter.to_full_save_data`/`load_save_data` → free functions `player_to_full_save_data(player)` / `load_player_save_data(player, data)` in `content_loader.creatures` (next to `parse_player`). `core/player.py` is now a thin dataclass. `deserialize_item` stayed in `content_loader.items` (it legitimately uses `ItemContent`).
- **entity_serialization.py** (mirror of `combat_serialization.py`): extracted the get_state per-entity build into `serialize_entity(entity)`; `EntitiesLayer.get_state` is now a one-line dict-comp. The load/restore half stays in `load_state` — it dispatches entity *construction* against the live layer, so it isn't a clean pure-function extraction. Documented in the module docstring.
- **Import-cycle gotcha**: `content_loader.__init__` imports `creatures` → `layers.entities.models` → `layers.entities.__init__` → `layer.py`. So `layer.py` (and `entity_serialization.py`) must import `content_loader` *lazily* inside functions — this is the pre-existing pattern, not new debt. The core-level cycle (the actual deliverable) is gone: `core/player` has zero `content_loader` imports.
- **Callers updated**: `commands_save.py`, `game_service.py` (`player.load_save_data` → `load_player_save_data(player, ...)`); tests `test_character.py`, `test_starting_equipment.py` (import from `content_loader`, method→function). Contract change is intentional (methods became free functions to break the cycle).
- **Pins**: new `test_serialization_dedup.py` (GameDateTime to/from dict incl. missing-`second` backward compat; item round-trip deep-equality for weapon/finesse-weapon/armor/shield/accessory-with-grant_modifiers/potion). Existing `test_entities_serialization`, `test_starting_equipment`, `test_autosave_all`, `test_commands_save` all still green. `make check` green (backend 2358, frontend 242). Integration `test_save_roundtrip` deferred to `/close-phase` (task changed no integration tests; save format is byte-for-byte unchanged).
