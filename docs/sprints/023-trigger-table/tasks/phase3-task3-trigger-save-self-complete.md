# Task: Сейв и самогашение триггера

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 3 — Trigger table

## Description

Сделать trigger table lossless частью save schema и добавить штатное действие мозга «моя роль сыграна».
Сейв должен хранить `always_active`, определения пар, взведённость и текущее сработавшее состояние, чтобы runtime
NPC, восстановленный только из сейва, продолжил ждать правильный `until`. Действие `complete_trigger` принимает
`trigger_id`, снимает сработавшее состояние этой пары и завершает мирный ход; итоговое dormancy по-прежнему
определяет общий activation lifecycle.

## Tests First

- Разбудить NPC событием, сохранить и загрузить полный world state, затем отправить `until`: восстановленная пара
  должна совпасть по исходному typed условию, сняться и позволить существу погаснуть.
- Сохранить ещё не сработавшую и вручную снятую с взведения пары; после load первая должна сработать на `on`, а
  вторая остаться отключённой. Неизвестные/лишние поля в trigger save state должны отклоняться строгой Pydantic
  схемой.
- Восстановить runtime-created NPC, которого нет в исходном YAML, только из save: определения, IDs и состояния
  trigger table не теряются.
- Провести `complete_trigger` через реальный `ActionDispatcher` от scripted brain: действие доступно только при
  наличии сработавшей взведённой пары, снимает указанный trigger ID, завершает ход и после activation pass гасит
  существо без других причин активности.
- Проверить отказ для неизвестного, отключённого или ещё не сработавшего trigger ID без мутации и расхода бюджета;
  при двух сработавших парах завершение одной оставляет существо активным.

## Implementation

Добавить строгие save-модели условия, определения и runtime-состояния пары в
`layers/entities/save_models.py`; протянуть поля через `entity_serialization.py` и `EntitiesLayer.load_state` для
всех `Creature`. После load полностью перестраивать trigger index, не оставляя ссылки на старые объекты.

Добавить `ActionType.COMPLETE_TRIGGER`, gettext-описание `ActionDef`, отдельный provider только для существ с
доступными к завершению парами и handler, который меняет trigger state через доменную операцию. Не выставлять
`active=False` прямо в handler и не прятать действие в `RuleBrain`: любой Brain может выбрать его через обычный
контракт действий, а manager учитывает оставшиеся причины активности. Обновить LLM/frontend schema-derived
поверхности и каталоги gettext, если их проверяет существующий action registry gate.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Trigger definitions, взведённость, срабатывание и `always_active` проходят строгий save/load round-trip
- [x] Runtime-created NPC восстанавливает trigger table без исходного YAML
- [x] `complete_trigger` идёт через ActionDef/provider/dispatcher и снимает ровно указанную активную пару
- [x] Ошибочное самогашение не мутирует состояние и не расходует action budget
- [x] После самогашения итоговая активность учитывает остальные пары, combat, scene и `always_active`

## Status

`done`

## Developer Notes

Добавлены строгие `EventConditionSave`/`ActivationTriggerSave` в единый Pydantic-конверт entities. Все `Creature`
сохраняют `always_active`, определения пар, `armed` и `active`; load полностью заменяет runtime-пары и перестраивает
`TriggerIndex`, включая NPC, созданных только во время сессии.

`complete_trigger` реализован доменной операцией и штатной цепочкой ActionDef → provider → dispatcher → handler.
Provider показывает действие только для взведённой активной пары, handler не меняет `active` существа напрямую и
ошибки не мутируют пары. LLM/API metadata строится из registry; gettext-каталоги и frontend action type/labels
обновлены. Полный gate зелёный: 2517 backend unit и 283 frontend tests.
