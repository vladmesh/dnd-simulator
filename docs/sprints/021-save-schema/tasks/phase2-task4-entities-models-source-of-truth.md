# Task: Entities save-модели — source of truth, не обёртка

**Date:** 2026-07-10
**Sprint:** 021-save-schema
**Phase:** 2 — Unified Pydantic save schema

## Description

Переработка результата task 2. Текущее состояние: `layers/entities/save_models.py` — валидирующая обёртка. `EntitySaveBase` объявлен с `extra="allow"`, поэтому бОльшая часть runtime-состояния (equipped-слоты, conditions, resource_pools, turn_budget, reputation, faction_id, xp_value, wake_at_seconds, is_dodging/is_disengaging, in_combat, combat_position, gold, inventory, class_features, brain type) едет НЕтипизированными extras; `serialize_entity` в `entity_serialization.py` по-прежнему руками собирает dict и лишь прогоняет его через `EntitySaveAdapter`; формат игрока по-прежнему определён в `content_loader/creatures.py:player_to_full_save_data`. Это не source of truth — это ре-валидация чужого формата, и следующие спринты (intents, триггеры, лог мыслей) снова будут дописывать рукописный сериализатор.

Довести до спеки task 2:

1. **Полные модели.** Инвентаризовать всё, что `serialize_entity` и `player_to_full_save_data` пишут сегодня (включая `EQUIPMENT_FIELDS` из `content_loader/items.py`), и объявить каждое поле в моделях явно. `extra="forbid"` на всех сейв-моделях. Никаких `dict[str, Any]`-мешков: `ItemSave` (зеркало формата `serialize_item`), `NpcMemorySave` (зеркало `NpcMemory.to_dict`), `ConditionsSave`, `ResourcePoolSave`, `TurnBudgetSave` и т.д. Где есть enum (EntityKind, BrainType, EquipmentSlot, Condition) — типизировать enum-ом, не строкой.
2. **Прямое построение.** `serialize_entity` строит модель напрямую из объекта (`PlayerSave(...)` от полей entity), без промежуточного рукописного dict; наружу отдаёт `model_dump(mode="json", by_alias=True)`. `player_to_full_save_data`/`load_player_save_data` схлопываются: формат игрока определяется только `PlayerSave` (функции-мосты в content_loader либо удаляются, либо становятся тонкими вызовами модели — два источника формата исчезают).
3. **Load через модель.** `EntitiesLayer.load_state` читает поля валидированной модели (пусть и передавая их существующей машинерии реконструкции `parse_player`/`parse_npc` — саму реконструкцию не переписывать).
4. **Combat sides — найденный lossless-пробел.** `CombatState.sides` (`core/combat.py:302`) не сериализуется вовсе: бой, сохранённый посреди схватки, после load теряет стороны. Добавить `sides` (и проверить остальные runtime-поля CombatState — индекс текущего хода и т.п.) в `CombatStateSave` + `combat_serialization.py`, восстановить при load.

## Tests First

- Пин полноты: round-trip максимально наполненного игрока/NPC/существа/контейнера сравнивает **каждое** поле объекта после load с оригиналом (экипировка всех слотов, склянки, условия с длительностями, пулы, репутация, память, бюджет хода, флаги dodge/disengage, wake_at, combat_position, xp/level_up_available).
- Незнакомое поле в entity payload → `ValidationError` (extra=forbid работает).
- Combat sides: сейв посреди боя 2×2 с несимметричными сторонами → load → `CombatState.sides` идентичны, бой продолжается корректными сторонами (атака врага валидна, союзника — отклоняется).
- Существующие round-trip сетки (`test_entities_serialization.py`, integration `test_save_roundtrip.py`) остаются зелёными.

## Implementation

После красных тестов: расширение `save_models.py`, переписывание `serialize_entity` на прямое построение моделей, правка `load_state`, `combat_serialization.py` + `CombatStateSave.sides`, схлопывание player-формата. Если какое-то поле сегодня пишется, но при load игнорируется (мёртвый груз) — не выбрасывать молча: зафиксировать в Developer Notes.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check-backend`, `make test-integration`)
- [x] `extra="forbid"` на всех entity save-моделях; ни одного `dict[str, Any]` в них
- [x] `serialize_entity` строит модели напрямую; формат игрока определён в одном месте
- [x] `CombatState.sides` переживает save/load

## Status

`done`

## Developer Notes

`save_models.py` теперь описывает entity payload явно: items, memory, resources, turn budget, runtime flags, equipment slots, conditions and combat sides validate through `extra="forbid"`. `serialize_entity` строит конкретные Pydantic-модели напрямую; `player_to_full_save_data()` оставлен как тонкий compatibility bridge к `PlayerSave` subset for `parse_player`.

Поля, которые пишутся, но не применяются к уже существующей entity при `load_state`: structural reconstruction data (`max_hp`, `ac`, `speed`, `ability_scores`, `attacks`) and parse aliases (`items`, `class_features`, NPC `hp`/`ai`/`start_location`/`race`/`class`). Они сохранены для missing-entity reconstruction через существующие `parse_player`/`parse_npc`, которые эта задача не переписывала.

Integration websocket fixture `ws_village` переведена с module scope на function scope: session eviction made the existing error-handling checks read a closed socket late in the suite.
