# Task: Entities-слой на Pydantic-моделях сейва

**Date:** 2026-07-10
**Sprint:** 021-save-schema
**Phase:** 2 — Unified Pydantic save schema

## Description

Самая большая поверхность: `layers/entities/entity_serialization.py:18` (`serialize_entity` — рукописный dict с ветвлением Creature/PlayerCharacter/Npc/Container), обратный путь в `layers/entities/layer.py:427` (`load_state` через `parse_player`/`parse_npc`/`Creature(...)`), `content_loader/creatures.py:313` (`player_to_full_save_data`/`load_player_save_data`), плюс `get_combats_state` (CombatState/BattleMap).

Ввести Pydantic-модели сейва сущностей: `EntitySave` как discriminated union по `EntityKind` (`CreatureSave`/`PlayerSave`/`NpcSave`/`ContainerSave`), submodels для инвентаря/экипировки (переиспользовать `serialize_item`/`deserialize_item` из `content_loader/items.py` как кодек или завести `ItemSave`), conditions, resource pools, turn budget, npc memory (`NpcMemory.to_dict` уже есть), combat state (`CombatStateSave`, `BattleMapSave`). `EntitiesState` — корневая модель слоя (entities + combats + rng, по образцу task 1).

Сейв-модели — отдельные от контентных схем (`content_loader/schemas.py`): контент — авторский формат, сейв — runtime-снапшот; общие enum-ы (EntityKind, BrainType, EquipmentSlot и т.п.) переиспользовать, модели не наследовать. Как и в task 1: сигнатуры `get_state`/`load_state` остаются dict-овыми, модель — внутренний source of truth; валидация fail-fast.

Lossless-инвариант (ключевое требование simulation-core): всё, что `serialize_entity` пишет сегодня, обязано пережить round-trip. Существующая сетка `tests/unit/test_entities_serialization.py` и `tests/integration/test_save_roundtrip.py` — опора; если сетка не пинует какое-то поле (например `wake_at_seconds`, `is_dodging`, `combat_position`, `equipped` slots, `reputation`) — допинуй.

## Tests First

- Round-trip всех четырёх видов сущностей с максимально наполненными полями (экипировка во всех слотах, склянки в инвентаре, условия с длительностями, resource pools, репутация, npc memory, xp/level_up_available, wake_at_seconds, dormant/active) → идентичное состояние.
- Combat round-trip: активный бой (initiative order, positions, walls, sides, round number) переживает save/load, следующий ход корректен.
- RNG слоя entities: encounter-roll последовательность продолжается после load (по образцу task 1).
- Невалидный entity payload → `ValidationError`.

## Implementation

После красных тестов: модели (предлагается `layers/entities/save_models.py`), `entity_serialization.py` переписывается на построение моделей (или растворяется в них), `load_state` — через `model_validate` + фабрики. `content_loader/creatures.py` player-save функции переезжают/сводятся к модели (не оставлять два источника формата игрока). Аккуратно с брейнами: `BrainType` сохраняется, реассайн брейнов при load остаётся как есть (brain_factory на стороне сервиса).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check-backend`)
- [ ] `serialize_entity`-ветвление заменено discriminated union; формат игрока определён в одном месте
- [ ] Lossless: round-trip сохраняет все сериализуемые поля, включая combat state и RNG слоя

## Status

`done`

## Developer Notes

Added `EntitiesState` with discriminated Pydantic entity models, typed combat submodels, and entities-layer RNG state. `EntitiesLayer.get_state()` now always emits `entities`, `combats`, and `rng_state`; `load_state()` validates through `EntitiesState` before reconstruction. The old NPC `conversation_summary` save fallback is now invalid, matching the sprint decision to drop legacy save formats.
