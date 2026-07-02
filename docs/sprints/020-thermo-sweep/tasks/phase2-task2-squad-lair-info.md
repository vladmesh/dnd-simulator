# Task: SquadInfo/LairInfo на границе ecology→entities

**Date:** 2026-07-02
**Sprint:** 020-thermo-sweep
**Phase:** 2 — Типизация границ + enums

## Description

Squad- и lair-данные сейчас пересекают границу ecology→entities как bare `dict[str, Any]`: продюсеры `EcologyLayer._squad_to_dict` (`ecology/layer.py:421-432`, 9 ключей) и `_lair_to_dict` (`:435-452`, 12 ключей), потребитель — `ActivationManager` (`activation_manager.py:197,325-347,489-578`) со строковой индексацией `info["state"]`, `info.get("treasure_items")` и т.п.

Сделать:

- Frozen dataclasses `SquadInfo` и `LairInfo` (в `core/queries.py` из task 1, рядом с остальными payload-типами) — поля по фактическим ключам; `state: LairState` вместо строкового `.value`.
- Аксессоры `query_squads_at_location`, `query_squad_info`, `query_lairs_at_location` в том же модуле.
- `EcologyLayer` в ветках SQUADS_AT_LOCATION / SQUAD_INFO / LAIRS_AT_LOCATION возвращает датаклассы (`_squad_to_dict`/`_lair_to_dict` остаются только для get_state-сериализации, если ещё нужны).
- `ActivationManager` (`_materialize_squad`, `_materialize_lair`, `_treasury_core_alive`, `_sync_lair_treasury`, daylight/active-проверка `:197`) читает типизированные поля.

Вне скоупа: позиционный tuple `_materialized_squads` / `MaterializedSquad` — это фаза 3 (декомпозиция activation_manager, общий трекер материализации).

## Tests First

Поведение неизменно — пиновка ключевых цепочек до рефактора (GREEN):

- Вход игрока в локацию с активным сквадом материализует существ по member_templates и strength (есть в test_activation_manager/test_squads — убедиться, что цепочка покрыта, дописать недостающее).
- Логово: вход в локацию с ACTIVE-логовом материализует ростер + treasury-контейнер с treasure_items/gold; убийство core деплитит логово, treasury доступна (test_lairs integration).
- Новое: аксессор `query_lairs_at_location` сквозь реальный EcologyLayer возвращает `LairInfo` с `state: LairState` (enum, не строка).

## Implementation

1. Датаклассы + аксессоры в `core/queries.py`.
2. Producer-ветки ecology → датаклассы.
3. `ActivationManager` — заменить индексацию словарей на поля, убрать `assert isinstance(answer.value, list)` (`:196,331,487`) и сравнение `info["state"] == LairState.ACTIVE.value` на `info.state is LairState.ACTIVE`.

Gotcha: `get_state`/`load_state` ecology-слоя сериализуют сквады/логова в JSON — этот формат не трогаем (save-совместимость, пиновка через test_save_roundtrip).

## Acceptance Criteria

- [ ] Пиновочные тесты (squad + lair материализация, treasury) написаны и GREEN до рефактора
- [ ] `ActivationManager` не содержит строковой индексации squad/lair-словарей
- [ ] Save/load round-trip не изменился (test_save_roundtrip зелёный)
- [ ] `make check` зелёный

## Status

`pending`
