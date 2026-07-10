# Task: Consistent save and eviction paths

**Date:** 2026-07-10
**Sprint:** 022-intents-travel
**Phase:** 1 — Safe session lifecycle

## Description

Перевести manual save, per-action autosave, periodic autosave, shutdown autosave и empty-session evict на единый способ получения согласованного session snapshot. Snapshot включает мир и состояние session-owned dice RNG из одной критической секции. Файловая запись выполняется после получения snapshot, чтобы медленный диск не останавливал раунд.

Параллельное удаление или выселение сессии не должно воскрешать её, падать на итерации registry либо оставлять частично записанный SaveGame.

## Tests First

- Manual и periodic autosave во время живого раунда сохраняют валидный `SaveGame`, который загружается и содержит согласованное состояние мира и dice RNG.
- Медленная запись в `SaveStore` не удерживает world-state gate: после построения snapshot раунд может продолжить работу.
- Одновременные autosave и empty-session evict создают не более одного корректного autosave и не воскрешают удалённую сессию.
- Ошибка одной сессии в `autosave_all_sessions` не мешает сохранению остальных.

## Implementation

Сделать единый snapshot-builder на границе `GameSession`/`SaveCommands`; `_build_save_game` не должен читать изменяемые `session.world` и RNG раздельно. Все save entry points используют готовый immutable/Pydantic snapshot, затем вызывают store вне gate. Укрепить итерацию активных сессий и evict-путь против конкурентного удаления, сохранив существующее логирование ошибок.

Ключевые файлы: `service/commands_save.py`, `service/game_service.py`, `service/session.py`, `adapters/api/app.py`, тесты commands_save/periodic_autosave/autosave_error_logging.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Все точки save/autosave используют один согласованный snapshot path
- [ ] Мир и dice RNG попадают в snapshot под одной критической секцией
- [ ] Store I/O не выполняется под world-state gate
- [ ] Concurrent evict/delete не воскрешает сессию

## Status

`pending`
