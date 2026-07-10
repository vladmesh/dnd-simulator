# Task: World-state mutation gate

**Date:** 2026-07-10
**Sprint:** 022-intents-travel
**Phase:** 1 — Safe session lifecycle

## Description

Ввести отдельную session-level критическую секцию для состояния мира. Раундовые мутации и получение согласованного snapshot используют один gate; listener/lifecycle lock остаётся отдельным и не меняет назначения. Gate нельзя удерживать во время блокирующего ожидания действия `PlayerBrain`, иначе autosave зависнет на всё время человеческого хода.

Граница атомарности должна позволять сохранить мир между законченными действиями или раундами, но никогда посреди handler, реакции, activation/materialization либо `advance_time`.

## Tests First

- Autosave, начатый во время контролируемой мутации мира, ждёт её завершения и получает состояние после целой мутации, без смешения значений до и после.
- Autosave проходит, пока раунд припаркован в ожидании действия игрока.
- Реакция и вызвавшее её действие не дают snapshot с наполовину применённым результатом.
- Остановка раунда и конкурентный snapshot завершаются без deadlock.

## Implementation

Добавить в `GameSession` отдельный re-entrant world-state gate и явный API для согласованного чтения/мутации. Передать gate в `Round` либо инъецировать эквивалентный контекстный callback. Покрыть им activation/materialization, action dispatch вместе с вложенными реакциями, завершение боя и продвижение времени. Не расширять существующий `_lock`: он защищает listeners, timer и ссылки lifecycle, а его смешение с world-state создаст обратный порядок блокировок.

Ключевые файлы: `service/session.py`, `round.py`, тесты round/session concurrency.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Snapshot невозможен посреди мутации игрового состояния
- [ ] Ожидание `PlayerBrain` не удерживает world-state gate
- [ ] Listener callbacks и stop/join не создают обратного порядка блокировок

## Status

`pending`
