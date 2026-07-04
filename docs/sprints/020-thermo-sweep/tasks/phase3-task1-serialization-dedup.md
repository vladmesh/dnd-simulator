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

`pending`
