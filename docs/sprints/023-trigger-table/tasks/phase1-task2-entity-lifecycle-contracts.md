# Task: Контракты lifecycle и боя существ

**Date:** 2026-07-12
**Sprint:** 023-trigger-table
**Phase:** 1 — Типизированная таксономия событий

## Description

Перевести события entities-слоя, которые описывают изменения мирового состояния: encounter spawn, начало/конец боя, смерть, движение, раунд, инициативу, opportunity attack, XP и репутацию. После задачи будущие ecology write-back и trigger table получают типизированные `entity_id`, `location_id`, `faction_id` и причинные поля без чтения строковых ключей.

Сохранить текущую наблюдаемость encounter spawn. Перцептор уже существует с Sprint 019 и намеренно скрывает roster строкой `Something stirs nearby`; задача пинует это поведение на новом payload-контракте, а не реализует его повторно.

## Tests First

- Полная цепочка убийства в реальном entities/combat контуре выдаёт типизированные attack, death, XP и reputation payload'ы с теми же значениями, которые нужны игровым потребителям.
- Начало и завершение боя дают payload'ы с location и turn order; movement и opportunity attack сохраняют координаты, дистанцию и участников.
- Успешный random encounter создаёт типизированный payload с location и spawned entity IDs/names, а игрок видит локализованную расплывчатую строку без имён монстров и без fallback `Something happened`.
- Perception каждого мигрированного lifecycle-события работает через поля payload'а; несовместимый payload отбрасывается на создании события.

## Implementation

Добавить lifecycle/combat payload-модели в `core/events.py` и мигрировать producers в `layers/entities/`, `round.py` и связанные combat-resolution модули. Потребителей в combat manager, awareness/perception и тестовых capture callbacks перевести с `event.data[...]` на типизированные поля.

Encounter payload должен содержать стабильные идентификаторы заспавненных существ; display names можно сохранить для лога, но триггеры и write-back не должны матчиться по локализованному имени. Не менять правила видимости и observer routing.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Lifecycle/combat producers не собирают payload через dict
- [x] Death и encounter payload'ы содержат стабильные entity/location идентификаторы для фаз 2-3
- [x] Encounter log остаётся локализованным, не раскрывает roster и не использует fallback

## Status

`done`

## Developer Notes

- Добавлены frozen payload-контракты для death, movement, combat start/end, encounter, round/turn skip, opportunity attack, XP и reputation. Encounter сохраняет и ID, и display names; перцептор по-прежнему выдаёт только локализованную расплывчатую строку.
- Producers и lifecycle-perception переведены на атрибуты payload. Combat summary теперь читает типизированный turn order; старые fail-fast тесты обновлены с позднего `KeyError` на ранний `TypeError` при создании события.
- Разрешённый attack event остаётся в task 3 вместе с остальными action payload'ами, чтобы roll/damage value objects мигрировали одним контрактом.
- `make check`: backend 2483 passed, frontend 283 passed.
