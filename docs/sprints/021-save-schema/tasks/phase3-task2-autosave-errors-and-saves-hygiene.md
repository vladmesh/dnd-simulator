# Task: Ошибки автосейва в лог + чистка saves/ в интеграционных тестах

**Date:** 2026-07-10
**Sprint:** 021-save-schema
**Phase:** 3 — Autosave hardening

## Description

Две гигиенические половины (backlog `silent-failure-autosave` + минимальный фикс `saved-session-accumulation`).

**A. Де-глушение автосейва.** Два сайта `contextlib.suppress(Exception)` вокруг автосейва глотают ошибки молча: `service/commands_player.py:128` (после create_player) и `service/game_service.py:244-246` (`_on_session_empty`). Заменить на try/except с `logger.exception(...)` (structlog, по образцу `autosave_all_sessions` в `commands_save.py:40-47` — тот уже логирует, его не трогать). Семантика «не падать наружу» сохраняется — меняется только видимость.

**B. Чистка saves/ в integration teardown.** Интеграционные прогоны накопили в репо сотни `saves/*/session_*.json` (E2E sprint 020 нашёл ~900). Тесты создают сессии через API, автосейвы пишутся в общий `saves/`, teardown ничего не убирает. Сделать fixture-уровневую уборку в `tests/integration/conftest.py`: снимок множества файлов в `saves/` до теста (или до сьюта) → после — удалить новые. Учесть, что backend в docker пишет в примонтированный каталог — проверить, как volume настроен в `docker-compose.test.yml`, и чистить на правильной стороне. Существующие накопленные session_*.json из репо удалить в этом же коммите (git rm, кроме фикстурных сейвов, если такие есть — проверить, что ни один тест не читает существующий файл из saves/).

## Tests First

- A: автосейв, у которого store бросает исключение (подсунуть ломающийся store/путь), логирует ошибку (caplog/structlog capture) и не роняет вызывающий поток (`create_player` возвращает успех, evict продолжается).
- B: интеграционный прогон не оставляет новых файлов в `saves/` после завершения (проверяется самим fixture-механизмом; локальный критерий — `git status` чист после `make test-integration`).

## Implementation

Половина A — точечные правки двух сайтов + unit-тесты. Половина B — conftest fixture + одноразовая чистка каталога. Не трогать сейвы, на которые ссылаются доки/фикстуры (grep по именам перед удалением).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation, для половины A)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check-backend`, `make test-integration`)
- [ ] В `src/` не осталось `contextlib.suppress` вокруг автосейва
- [ ] После `make test-integration` рабочее дерево чистое (saves/ не растёт)

## Status

`pending`
