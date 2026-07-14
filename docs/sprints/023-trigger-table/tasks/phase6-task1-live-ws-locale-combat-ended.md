# Task: Единая locale и typed COMBAT_ENDED в live WS

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 6 — Post-audit E2E fixes

## Description

Закрыть E2E-блокер смешанной локали в live player WebSocket и добавить typed perception для
`COMBAT_ENDED`. Выбор EN/RU в интерфейсе должен быть языком сессии до подключения player WS и после
смены языка в уже открытой игре, поэтому server-side тексты event log не должны оставаться на
процессном default `DND_LANGUAGE`. Завершение боя с `CombatEndedPayload` должно дать нормальную
локализованную строку, а не fallback `Something happened (combat_ended)`.

Граница задачи: language propagation между frontend и существующим session-lang API, WS context и
perception handler. Не переносить локализацию всех content-названий и не менять формат event envelope.

## Tests First

- Создать EN player session, подключить live WS, спровоцировать бой и его завершение; `combat_started`,
  атака, смерть и `combat_ended` в event log приходят на английском, а последний текст явно сообщает
  о завершении боя без raw event type.
- Повторить для RU сессии: те же server-rendered сообщения приходят на русском; язык frontend controls
  и live log совпадает.
- В уже открытой player session переключить язык EN→RU и проверить, что следующее WS-событие приходит
  на новом языке, а не на первоначальном или process default.
- Unit-тест perception: `EventType.COMBAT_ENDED` с `CombatEndedPayload` форматируется handler'ом для
  наблюдателя и не достигает generic fallback.

## Implementation

Проследить выбор языка из `LanguageToggle` до `PUT /api/master/sessions/{id}/lang` или эквивалентной
session-scoped transport boundary, затем применять `session.lang` при установке WS context и при
асинхронной доставке listener callbacks. Убрать зависимость live события от default contextvar, не
использовать process-global переключение языка как замену session context.

Добавить узкий typed handler `COMBAT_ENDED` в entities perception рядом с остальными world/combat
handlers и его gettext message в каталоги. Сохранить `CombatEndedPayload` как единственный runtime
контракт, без dict compatibility bridge.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] EN и RU frontend language совпадает с текстом новых live WS-событий
- [ ] Смена языка в существующей session влияет на следующее live WS-событие
- [ ] `COMBAT_ENDED` имеет typed perception и не использует generic fallback
- [ ] В event-log нет raw `combat_ended` при штатном завершении боя

## Status

`done`

## Developer Notes

Round callbacks now apply the current session language while formatting each live payload, so a
language change affects the next player WS event. The player header propagates its language toggle
to the existing session-language endpoint. `COMBAT_ENDED` now has a typed perception handler using
the existing gettext entry.
