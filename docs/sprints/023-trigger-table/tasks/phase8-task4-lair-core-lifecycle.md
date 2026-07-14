# Task: Terminal lifecycle ядра логова

**Date:** 2026-07-14
**Sprint:** 023-trigger-table
**Phase:** 8 — Follow-up post-audit E2E Paladin

## Description

Исправить terminal lifecycle логова после того, как Master UI меняет `current_hp` его ядра на
`0`. Сейчас reconnect игрока оставляет мёртвое исходное ядро и материализует второй core/minion
roster. Логово должно перейти в единое depleted состояние, сохранить исходное мёртвое ядро как
исторический результат мутации и не создавать новый roster при reconnect.

Граница задачи: проследить materialization, depletion и событийный write-back смерти логова на
поддерживаемом Master mutation path. Не скрывать мёртвое исходное ядро и не обходить проблему
frontend-only фильтром: состояние ecology и сохранённый lifecycle должны оставаться согласованными.

## Tests First

- В integration-регрессии материализовать логово, через поддерживаемую Master-команду установить
  `current_hp=0` его core и подтвердить terminal depletion без второго roster.
- После reconnect той же session проверить, что исходное мёртвое ядро не исчезло, новый core и
  minions не материализованы, а lair lifecycle остаётся depleted.
- Закрепить event write-back: mutation ядра приводит ecology/lair state к тому же terminal
  состоянию, которое ожидается после смерти ядра, и это состояние не расходится после save/load,
  если путь затрагивает сохранение.
- Повторить targeted browser boundary из §15.2: Master mutation `current_hp=0` и reconnect не
  создают второй roster.

## Implementation

Найти общий инвариант между Master creature edit, entity lifecycle/event emission, ecology
write-back и lair materialization. Исправить подтверждённый разрыв в этом инварианте, сохранив
typed event contract и прежний normal combat-death path. Добавить регрессии на минимальном
backend уровне, а browser report обновить только после успешного targeted rerun.

## Acceptance Criteria

- [ ] Reproduction покрывает Master mutation `current_hp=0` ядра логова и subsequent reconnect.
- [ ] Depleted lair не материализует второй core/minion roster при reconnect.
- [ ] Исходное мёртвое ядро не скрывается ради прохождения проверки.
- [ ] Materialization, depletion и event write-back имеют согласованное terminal state.
- [ ] Regression tests добавлены и сначала воспроизводят дефект.
- [ ] `make check` проходит.
- [ ] Phase 8 Task 2 остаётся `blocked` до завершения этой задачи; после неё повторяется только lair E2E boundary.

## Status

`pending`

## Developer Notes

Источник дефекта: [final areas E2E report](../../../e2e-reports/2026-07-14-sprint023-post-audit-final-areas.md),
§15.2. В `/tmp/dnd-e2e-logs/session_d953fe0d/full.jsonl` зафиксированы initial и reconnect-time
`lair_materialize` events с разными ID chieftain/minions после Master mutation исходного core.
