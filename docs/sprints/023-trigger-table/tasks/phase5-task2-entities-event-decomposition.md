# Task: Разгрузка entities event flow и perception

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 5 — Post-audit refactor

## Description

Закрыть `entities-layer-regrowth` и `perception-fail-fast`. Вынести из `EntitiesLayer` применение trigger
boundaries, определение локации и запись событий в location log. Разделить 629-строчный perception dispatch по
доменам событий, оставив один публичный `perceive_event` и неизменные RU/EN строки.

После Task 1 каждый handler работает с гарантированным payload-классом. Для обязательных полей используются
атрибуты конкретного payload, без silent `.get()` и строковых aliases. Оркестрация слоя остаётся в
`EntitiesLayer`, а выделенные компоненты получают только нужные зависимости и не становятся новым god-module.

## Tests First

- Через живой `EntitiesLayer` провести событие войны, которое активирует NPC, и until-событие, которое его
  гасит; intent interruption, armed state и независимые причины активности сохраняют поведение Phase 3.
- Провести resolved movement, squad movement и смерть временного существа: события попадают в правильные
  location logs, origin/destination видят squad move, временное существо удаляется.
- Для representative action/combat/world payload'ов проверить прежние RU/EN descriptions и actor/target/data в
  `PerceivedEvent`, включая скрытую encounter roster и opportunity attack.
- Передать payload неправильного типа напрямую в выделенную границу и проверить явный contract failure вместо
  пустой строки, `None` или fallback по отсутствующему ключу.

## Implementation

Выделить небольшой trigger runtime-компонент поверх существующего `TriggerIndex`: он применяет `on`/`until`,
прерывает intent и обрабатывает каскадные события. Отдельный event-log/location компонент определяет место по
конкретным payload-типам, пишет обычные и двухточечные squad events и строит `PerceivedEvent` через явный codec
typed payload → JSON-safe data.

Разнести perception handlers как минимум на action/combat и world/lifecycle группы. Текущий
`layers.entities.perception` остаётся фасадом dispatch, чтобы callers не зависели от внутренней раскладки.
Повторяющиеся actor/target description helpers держать в одном месте. Не переносить save/load, combat resolution
или query orchestration в новые компоненты.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Trigger lifecycle и event location/logging отсутствуют как private implementations в `EntitiesLayer`
- [ ] Perception handlers читают обязательные поля из конкретных payload-классов без mapping access
- [ ] `perceive_event` и пользовательские RU/EN строки сохраняют публичный контракт
- [ ] `layers/entities/layer.py` и `perception.py` заметно уменьшаются, новые модули имеют одну ответственность

## Status

`pending`
