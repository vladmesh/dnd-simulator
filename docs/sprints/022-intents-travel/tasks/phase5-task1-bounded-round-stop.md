# Task: Bounded round-stop contract

**Date:** 2026-07-12
**Sprint:** 022-intents-travel
**Phase:** 5 — Bounded round shutdown

## Description

Сделать остановку round thread ограниченной по времени и атомарной относительно lifecycle-состояния
сессии. Если поток не завершился за заданный срок, `stop_round()` должен вернуть явную ошибку и оставить
ссылки на тот же round, brain и thread. Пока этот поток жив, новый round не запускается, а вызывающий код
может повторить остановку после освобождения блокирующего callback.

Успешная остановка сохраняет текущий контракт: round получает stop, очереди player brain разблокируются,
поток завершается, после чего lifecycle-ссылки очищаются. Таймаут должен быть одной именованной настройкой
сессии и сопровождаться структурированным логом с session context.

## Tests First

- Round callback блокируется дольше stop timeout: `stop_round()` завершается за ограниченное время с
  явной lifecycle-ошибкой, а живые round, brain и thread остаются привязаны к сессии.
- Пока старый поток жив после таймаута, повторный `start_round()` не создаёт второй loop и не заменяет
  lifecycle-ссылки.
- После освобождения callback повторный `stop_round()` дожидается того же потока и очищает round, brain
  и thread; следующий `start_round()` затем создаёт ровно один новый loop.
- Обычный parked player turn по-прежнему останавливается сразу и не достигает timeout path.

## Implementation

Перестроить `GameSession._stop_round()` в два этапа: под `_lock` получить стабильный lifecycle snapshot,
затем послать stop/unblock и выполнить bounded join без преждевременной очистки ссылок. После успешного
join очистить поля только если они всё ещё указывают на тот же snapshot. При живом потоке залогировать
timeout и выбросить отдельную понятную lifecycle-ошибку.

Не отпускать `_round_transition_lock` между stop request, join и фиксацией результата. Не брать
`_world_state_lock` вокруг join: round может завершать текущую mutation scope. Не добавлять второй
механизм остановки в `Round`.

Ключевые файлы: `service/session.py`, `tests/unit/test_session_lifecycle.py`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check-backend`)
- [ ] Stop ожидание ограничено одной именованной timeout-настройкой
- [ ] Timeout не теряет ссылки на живой round thread
- [ ] Живой старый thread исключает запуск второго round loop
- [ ] Повторная остановка после освобождения callback полностью очищает lifecycle

## Status

`pending`
