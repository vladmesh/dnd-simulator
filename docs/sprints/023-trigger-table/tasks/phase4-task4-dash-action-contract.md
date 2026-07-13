# Task: Контракт Dash без мёртвого перемещения

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 4 — Ручка ГМ + failure containment

## Description

Закрыть `dash-actiondef-movement-conflation`. `Dash` добавляет текущую скорость к остатку movement budget, а
само перемещение выполняется отдельным `move`/`move_to`. Убрать из его публичного ActionDef мёртвые параметры
`toward`, `away_from` и `direction`, перестать обещать движение «до двойной скорости» одним action и сохранить
существующую механику handler/Cunning Action.

## Tests First

- Получить Dash из action registry/tool schema и проверить, что он не принимает параметры выбора направления и
  явно описывает добавление скорости к movement budget с последующим отдельным движением.
- Через реальный dispatcher выполнить Dash существом со скоростью, изменённой condition/modifier pipeline:
  остаток перемещения увеличивается на `effective_speed`, позиция не меняется, затем отдельный `move` тратит новый
  бюджет.
- Проверить обычный Action-cost и rogue Cunning Action bonus-cost, чтобы правка metadata не изменила механику.

## Implementation

Изменить только Dash metadata в `core/action_defs.py`, связанные LLM/frontend-derived descriptions и gettext
каталоги. Оставить `handle_dash`, abstract MOVE resolution и budget rules без функциональной переделки. Параметр
`cost_mode`, если он ещё нужен текущему cost override контракту, сохранить отдельно от удаляемых movement params;
`description` оставить только как flavor, если registry использует его для других actions.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Dash schema не содержит `toward`, `away_from` и `direction`
- [ ] Описание требует отдельного move после пополнения movement budget
- [ ] Dash не меняет позицию и добавляет ровно `effective_speed(actor)`
- [ ] Обычная и Cunning Action стоимости не изменились
- [ ] Handler и abstract MOVE resolution не получили лишней переделки

## Status

`pending`
