# Task: Событийный lifecycle активации

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 3 — Trigger table

## Description

Подключить trigger index к живому мировому event flow. Совпавший `on` переводит пару в сработавшее состояние,
прерывает текущее wait/sleep/travel intent и будит живое существо; совпавший `until` снимает только состояние этой
пары. Итоговая активность должна вычисляться из всех независимых причин: combat, awake anchor scene,
`always_active` и хотя бы одна сработавшая взведённая пара. Одно `until` не может погасить другую активную пару,
бой или `always_active`.

## Tests First

- В полном `World` отправить подходящий `WAR_DECLARED` и проверить, что далёкий dormant NPC с `war_duty`
  просыпается без activation polling; `PEACE_DECLARED` снимает пару, а следующий штатный activation pass гасит NPC.
- Разбудить NPC с wait и travel intent и проверить, что `on` прерывает намерение один раз, сохраняя последнюю
  достигнутую локацию путешественника. Повтор того же `on` должен быть идемпотентным.
- Дать существу две пары: `until` первой оставляет его активным из-за второй. Отдельно проверить, что
  `always_active` не гасится ни одним `until`, а мёртвое существо не пробуждается.
- Разбудить NPC событием, которое возникло как cascade из `EntitiesLayer` (например, реальным `ENTITY_DIED` от
  killing hit), и проверить доставку матчера ровно один раз. Это пинует существующий source-skip каскадной очереди
  и не допускает специального обхода только для внешних событий.
- Проверить, что активный по триггеру NPC остаётся активным после нескольких `update_activation`, даже если рядом
  нет anchor, и что обычная anchor-сцена продолжает работать без триггеров.

## Implementation

Добавить в `EntitiesLayer.handle_event` единый путь применения входящих событий к trigger index. События,
порождённые самим entities-слоем через `ActionResult.events`, также должны пройти matcher до source-skip в
`World.handle_event`; оформить это одним helper вокруг результата, а не перечислять типы каскадов по одному.

Расширить `ActivationManager` явным вычислением причин активности. Не использовать `creature.active = True` как
хранилище срабатывания: текущий manager перезаписывает этот флаг на каждом проходе. `on` меняет состояние пары и
прерывает intent штатным `interrupt_intent`; `until` снимает пару, после чего manager пересчитывает итоговый флаг.
Сохранить существующие encounter/materialization правила привязанными к anchor locations, чтобы trigger-активный
NPC не создавал транзитивный LOD-каскад.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `on` немедленно будит dormant существо и безопасно прерывает его intent
- [ ] `until` снимает только свою пару; combat, scene, другая пара и `always_active` имеют независимый приоритет
- [ ] Срабатывание переживает последующие activation passes и не делает активность транзитивной
- [ ] Внешние и entities-cascade события матчатся ровно один раз
- [ ] Матчинг происходит при эмиссии событий, а не через round polling

## Status

`pending`
