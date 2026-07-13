# Task: Доставка каскадных событий в live session

**Date:** 2026-07-13
**Sprint:** 023-trigger-table
**Phase:** 2 — Событийный write-back — смерти логова

## Description

Закрыть блокер phase-scoped E2E: события, возвращённые слоями через `ActionResult.events`, должны автоматически
проходить через мировой event flow. Сейчас killing hit создаёт `ENTITY_DIED`, но live session только возвращает его
из `World.handle_event` и не доставляет ecology. Заодно сделать payload восприятия JSON-safe, чтобы provenance логова
с enum роли не ломала `WsEventListener.on_action_result`.

## Tests First

- Провести реальную атаку через один вызов мирового event flow и проверить немедленный ecology write-back без
  ручной повторной отправки `ENTITY_DIED`.
- Проверить доставку второго уровня cascade events, чтобы контракт не был специальным случаем смерти логова.
- Сериализовать perceived `ENTITY_DIED` с `LairOrigin` и проверить, что результат принимается стандартным JSON
  encoder без enum или dataclass внутри payload.

## Implementation

- Исполнить `ActionResult.events` как каскадные события внутри `World.handle_event`, сохраняя их в итоговом результате
  и доставляя всем слоям в порядке возникновения.
- Убрать ручной replay из тестов ecology write-back.
- Нормализовать вложенные dataclass и enum при построении WS event payload без зависимости service-слоя от FastAPI.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Killing hit немедленно обновляет ecology в live event flow
- [x] Cascade events второго уровня доставляются ровно один раз
- [x] `ENTITY_DIED` с provenance сериализуется в JSON для WS

## Status

`done`

## Developer Notes

`World.handle_event` теперь обрабатывает очередь событий, возвращённых слоями через `ActionResult.events`, и
возвращает полный каскад вызывающему коду. Тест ecology больше не воспроизводит отсутствующий production-шаг
ручным replay. `_events_to_list` рекурсивно переводит вложенные dataclass, enum и коллекции в JSON-safe значения,
поэтому provenance смерти проходит через стандартный WS encoder. Полный `make check` зелёный: backend 2495,
frontend 283.
