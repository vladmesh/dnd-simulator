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

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Системные и layer-события не создаются через свободные dict payload'ы
- [ ] Несовпадение `EventType` и payload определяется fail-fast
- [ ] Штатные эмиссии geography/politics/settlements/ecology не используют `CUSTOM`

## Status

`pending`
