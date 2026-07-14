# Task: Повторное открытие Level Up после defer

**Date:** 2026-07-14
**Sprint:** 023-trigger-table
**Phase:** 8 — Follow-up post-audit E2E Paladin

## Description

Восстановить ручной путь к `LevelUpModal` после закрытия автоматически открытого окна. После
победы над `xp_dummy` Paladin L1 получает XP и остаётся с `level_up_available=true` до успешного
подтверждения повышения. Закрытие окна должно только отложить его: автоматические WS-снимки не
открывают окно снова, но в панели персонажа остаётся доступная кнопка `Level Up`, которая
повторно открывает то же окно.

Проверить полный контракт от backend state до frontend store: выдача XP, `action_result` /
`round_result` snapshots, `PlayerStats`, локальный флаг defer и REST-подтверждение level-up.
Не обходить правила уровня, не добавлять Fighting Style или spell slots на L1 и не менять
условия `perform_level_up`; если backend уже корректно сохраняет и передаёт pending state,
исправление ограничить frontend state/UI boundary.

## Tests First

- Через реальный игровой результат убийства проверить, что Paladin L1 получает XP за `xp_dummy`,
  а transport snapshot после события несёт `level_up_available=true`; REST level-up до
  подтверждения не вызывается и pending state не сбрасывается.
- В frontend regression пропустить этот pending snapshot через штатный `onActionResult` или
  `onRoundResult`: модалка открывается автоматически, Close переводит её в defer, а следующий
  snapshot с тем же pending state не открывает модалку сам.
- После defer проверить видимую кнопку `Level Up` в панели персонажа, её повторное открытие
  модалки и сохранение выбора Fighting Style до штатного REST-confirm. Сценарий должен покрыть
  Paladin L1 → L2, а не вручную подставленный изолированный `PlayerStatus` без WS-пути.
- После успешного подтверждения проверить, что обновлённый backend status с
  `level_up_available=false` скрывает кнопку и больше не открывает модалку.

## Implementation

Сначала проследить, где в live WS результате теряется или перезаписывается pending level-up
state: `build_player_status`, WS message types, `turnSlice.applyCommon`, `playerSlice` и
`PlayerStats`. Устранить только подтверждённый разрыв между server snapshot и controlled dialog.
Держать `level_up_available` каноническим серверным состоянием, а `levelUpDismissed` только
клиентским флагом defer; ручная кнопка должна зависеть от первого, а автоматическое открытие —
от обоих. Не дублировать state в компоненте и не подменять player status после закрытия модалки.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Реальный XP/WS путь сохраняет `level_up_available` до REST-confirm
- [ ] Close автоматически открытой модалки не применяет повышение и не скрывает ручную кнопку
- [ ] Ручная кнопка повторно открывает модалку без следующего automatic prompt
- [ ] Успешный L2 confirm убирает pending control; правила Paladin L1/L2 не менялись
- [ ] Phase 8 Task 2 остаётся blocked до полного обязательного E2E rerun

## Status

`done`

## Developer Notes

`level_up_available` already survived XP, transport, and REST-confirm paths. The regression was
client-only: `combat_ended` cleared the local defer flag, so an unchanged pending snapshot reopened
the dialog instead of leaving the manual control available. WS-driven Paladin L1 → L2 coverage now
checks defer, manual reopen, Fighting Style confirmation, and removal of the pending control.
