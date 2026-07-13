# Task: Контракт и индекс trigger table

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 3 — Trigger table

## Description

Добавить на `Creature` строгие декларативные пары `{on, until}` и построить событийный индекс для их
матчинга. Условие состоит из `EventType` и необязательного набора точных значений полей typed payload;
неизвестный event type, поле не из соответствующего payload или несовместимое значение должны отклоняться при
загрузке контента. У каждой пары есть стабильный ID, флаг взведения и runtime-состояние срабатывания. Индекс
должен выбирать кандидатов по типу пришедшего события, а не обходить всех существ на каждом раунде.

Контентный формат для именного NPC:

```yaml
always_active: false
triggers:
  - id: war_duty
    on:
      event: war_declared
      match: {aggressor_id: north, target_id: south}
    until:
      event: peace_declared
      match: {nation_a_id: north, nation_b_id: south}
```

## Tests First

- Загрузить NPC с парой `war_declared` / `peace_declared` и проверить, что typed runtime-модель сохраняет ID,
  оба условия, `always_active` и начальное взведённое, но ещё не сработавшее состояние.
- Проверить точный subset-match: нужная война выбирает триггер, война других фракций и другой `EventType` не
  выбирают; условие без `match` принимает любое событие указанного типа.
- Проверить несколько существ и несколько условий одного типа: индекс возвращает только подходящие пары и не
  зависит от activation tick или `active` существа.
- Отклонить YAML с неизвестным event type, повторяющимся trigger ID и полем, которого нет в typed payload
  выбранного события. Ошибка должна возникать на content boundary, а не при первом событии в игре.

## Implementation

Ввести небольшие frozen value objects условия и определения пары в `core/` и отдельное mutable runtime-состояние
пары на `Creature`. В `content_loader.schemas.NpcContent` добавить `always_active` и `triggers`, протянуть их через
`content_loader.creatures` без словарей `Any`. Валидировать ключи `match` по dataclass-полям из
`EVENT_PAYLOAD_TYPES`; матчинг оставить точным и декларативным, без операторов или произвольного Python.

Вынести индекс/матчер в отдельный модуль `layers/entities/`, принадлежащий `EntitiesLayer`. Индекс строится по
`EventType` при создании или загрузке набора существ и обновляется при `add_entity`/`remove_entity`; на событии он
проверяет только bucket этого типа. Эта задача создаёт контракт и чистый matcher, но ещё не меняет `active`.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] YAML задаёт строгие пары `{on, until}` со стабильными ID и точным typed-payload match
- [x] Невалидные event type, payload-поля и дубли ID падают при загрузке контента
- [x] Матчинг индексирован по `EventType` и не выполняется в шестисекундном activation loop
- [x] `always_active` и trigger definitions живут на runtime `Creature`, а не во внешнем сценарном реестре

## Status

`done`

## Developer Notes

Добавлены frozen `EventCondition`/`TriggerDefinition`, отдельное mutable `ActivationTrigger` на `Creature` и
строгий YAML-контракт для именных NPC. Значения `match` проверяются в strict-режиме по type hints соответствующего
typed payload; неизвестные поля, типы событий, несовместимые значения и дубли ID падают при загрузке.

`TriggerIndex` принадлежит `EntitiesLayer`, держит отдельные buckets для `on` и `until` по `EventType`, учитывает
текущую взведённость и обновляется при add/remove. Матчинг пока только возвращает совпадения и не меняет
активность, event lifecycle остаётся task 2, save/load состояния остаётся task 3.
