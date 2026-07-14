# Task: Типизированное ядро событий

**Date:** 2026-07-12
**Sprint:** 023-trigger-table
**Phase:** 1 — Типизированная таксономия событий

## Description

Заменить свободный `Event.data: dict[str, Any]` на типизированный контракт payload'ов, пригодный для последующего матчинга trigger table. Каждый `EventType` получает один фиксированный frozen payload; событие нельзя создать с payload'ом другого типа или с произвольным набором ключей. Метаданные доставки (`source_layer`, `description`, `observer_ids`) остаются на `Event`.

На первом инкременте ввести основу контракта и перевести системные и layer-события: время/погоду, politics/settlements, squad lifecycle/combat и materialization. `CUSTOM` убрать из штатных эмиссий этих модулей: каждому реально используемому мировому событию нужен именованный `EventType` и payload.

## Tests First

- Создание события погоды, движения сквада и материализации через публичный типизированный API сохраняет все доменные поля и не требует словарных ключей у потребителя.
- Нельзя связать `EventType.SQUAD_MOVE` с payload'ом погоды: контракт падает сразу на границе создания события, а не позже в perception или trigger matching.
- Реальный ecology tick, где сквад перемещается и встречает противника, выдаёт типизированные события с location/squad/faction данными; существующий результат симуляции не меняется.
- World propagation доставляет типизированный payload всем слоям без преобразования обратно в dict.

## Implementation

Вынести payload-модели в отдельный модуль `core/events.py`, чтобы не раздувать `core/models.py`. Использовать frozen dataclasses и явное соответствие `EventType -> payload`; не вводить универсальный `dict[str, object]` escape hatch. Оставить удобный конструктор, который mypy может проверить в producer-сайтах, и runtime-проверку для динамических границ.

Мигрировать producer/consumer-сайты в geography, politics, settlements и ecology. Perception системных событий читать через атрибуты payload'а. Если `CUSTOM` сейчас кодирует несколько разных смыслов, дать им отдельные типы вместо одного payload с набором optional-полей.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Системные и layer-события не создаются через свободные dict payload'ы
- [x] Несовпадение `EventType` и payload определяется fail-fast
- [x] Штатные эмиссии geography/politics/settlements/ecology не используют `CUSTOM`

## Status

`done`

## Developer Notes

- Добавлен `core/events.py`: 14 frozen payload-моделей и реестр `EventType → payload type`; `Event` валидирует зарегистрированный контракт при создании.
- Geography, politics, settlements, ecology и squad/lair materialization переведены на typed payload'ы. Семь смыслов politics и settlement damage получили отдельные `EventType` вместо `CUSTOM`.
- До завершения миграции action/lifecycle событий в tasks 2-3 `Event.data` остаётся временно типизирован как `Any`. Typed payload'ы имеют read-only mapping facade для немигрированных wire/log consumers; producer-код словари больше не собирает.
- Malformed typed events теперь падают на границе `Event`, поэтому старые fail-fast тесты обновлены с позднего `KeyError` perception на ранний `TypeError`.
- `make check`: backend 2481 passed, frontend 283 passed.
