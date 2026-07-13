# Task: Protocol containment и финальный autosave

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 5 — Post-audit refactor

## Description

Закрыть `test-gap-ws-malformed-json` и `test-gap-shutdown-autosave-failure`. Синтаксически валидный JSON, который
не является object (`[]`, `null`, строка, число), должен получить protocol error и оставить player/spectator WS
живым. Ошибка финального autosave при shutdown должна быть явно залогирована и не мешать завершению lifespan
после остановки periodic task.

Player и spectator receive loops должны использовать одну границу разбора JSON envelope, чтобы одинаковая
валидация и локализованный ответ не разъехались снова.

## Tests First

- В player WS после первого `turn` отправить по очереди `[]`, `null`, JSON string и число; на каждый получить
  `error`, затем отправить валидный action и получить штатный следующий message в том же соединении.
- Повторить non-object cases для spectator: получить тот же protocol error, затем object action отклоняется как
  spectator action, а соединение продолжает получать broadcast игрока.
- Проверить отдельно malformed JSON text: он сохраняет текущий `Invalid JSON` ответ и не смешивается с ошибкой
  корректного JSON неправильной формы.
- Смоделировать final `autosave_all_sessions()` exception: periodic task сначала отменён и дождан, ошибка
  логируется один раз с traceback/context, lifespan завершается без повторного исключения.

## Implementation

Добавить общий parser JSON-object envelope в `routes_ws.py`. Он различает syntax error и non-object value,
возвращает локализованное protocol-сообщение и не допускает вызова `.get()` до type check. Использовать parser в
обоих receive loops; не закрывать socket для recoverable bad input.

В shutdown `lifespan` оставить порядок `cancel → await periodic → final autosave`, но окружить только последний
autosave узкой logging boundary с отдельным событием. Не глушить ошибки старта приложения и не менять retry
поведение periodic autosave.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Player и spectator non-object JSON получают protocol error без disconnect
- [ ] Оба WS пути используют одну object-envelope validation boundary
- [ ] Валидное следующее сообщение обрабатывается после protocol error
- [ ] Ошибка final autosave логируется и не блокирует завершение lifespan
- [ ] Periodic task завершается до запуска final autosave

## Status

`pending`
