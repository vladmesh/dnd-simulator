# Task: Повторный обязательный Paladin post-audit E2E

**Date:** 2026-07-14
**Sprint:** 023-trigger-table
**Phase:** 8 — Follow-up post-audit E2E Paladin

## Description

После выравнивания playbook выполнить отложенную Paladin часть полного post-audit E2E и записать
результат. Прогон должен подтвердить реальную пользовательскую цепочку: создание Paladin L1,
Lay on Hands, level-up до L2 с выбором Fighting Style, затем Divine Smite и target-scope
validation. Он заменяет остановленный report от 2026-07-14, а не считает прежнее 10/11 зелёной
границей.

Граница задачи: использовать утверждённый E2E playbook и существующий `level_up_test`; не
маскировать новый blocker quick fix-ом в ходе прогона. При блокере зафиксировать сценарий,
логи и точную следующую работу в новом report.

## Tests First

- Paladin L1 создаётся через UI без selector Fighting Style, получает ожидаемые HP, AC,
  стартовое снаряжение и Lay on Hands pool.
- В `level_up_test` убийство `xp_dummy` открывает LevelUpModal; выбор Dueling переводит Paladin
  на L2, добавляет Fighting Style и два spell slots level 1.
- Lay on Hands лечит допустимую цель и расходует pool, а hostile target отвергается понятным
  сообщением или отсутствует из target list.
- L2 melee attack с Smite расходует один spell slot и показывает radiant component в damage
  breakdown; завершение боя возвращает peaceful UI.

## Implementation

Запустить serial browser E2E по проектному playbook с `--no-llm`, предварительно согласовав
порты с координатором, и сохранить report в `docs/e2e-reports/`. Повторить обязательные
non-LLM sections, включая обновлённые §3.5 и §14, поскольку прежний полный прогон был
незавершён; приложить к report результаты, blocker status и анализ backend/browser logs.

## Acceptance Criteria

- [ ] E2E environment and ports are coordinated before the run
- [ ] Paladin L1, L2 level-up, Lay on Hands, Smite and target-scope scenarios execute through UI
- [ ] Full required non-LLM post-audit playbook is rerun rather than only the formerly failing row
- [ ] Report records scenario results and relevant logs
- [ ] Green result is dated after the corrected playbook; otherwise blockers remain explicit

## Status

`blocked`

## Developer Notes

2026-07-14: UI run passed Paladin L1 creation and verified automatic L2 modal after killing
`xp_dummy`. Closing that modal did not expose the required manual `Level Up` button, including
after the next round, so Dueling, Lay on Hands, Smite, target scope and the remaining mandatory
non-LLM sections were not run. See [rerun report](../../../e2e-reports/2026-07-14-sprint023-post-audit-paladin-rerun.md).

2026-07-14: The remaining reactions, faction relations, corpse loot, and intent/travel checks
passed in the live UI. The lair boundary remains blocked: after setting a lair core to 0 HP in the
Master UI and reconnecting, Test Vale materialized a second core/minion roster while retaining the
dead first core. See [final areas report](../../../e2e-reports/2026-07-14-sprint023-post-audit-final-areas.md).
