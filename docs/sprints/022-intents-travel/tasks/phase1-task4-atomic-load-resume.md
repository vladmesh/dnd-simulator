# Task: Atomic load and connection-driven resume

**Date:** 2026-07-10
**Sprint:** 022-intents-travel
**Phase:** 1 — Safe session lifecycle

## Description

Сделать load атомарной сменой состояния сессии. Живой round loop сначала полностью останавливается, затем мир, dice RNG и brains восстанавливаются под world-state gate. Загруженный бой не исполняет ходы NPC в фоне до подключения игрока и не отправляет события в старый listener из состояния до load.

После следующего player connection обычный idempotent `start_round` продолжает игру из сохранённого состояния. Spectator не запускает раунд. Контракт применяется и к явному load в существующую сессию, и к восстановлению session autosave из registry.

## Tests First

- Сейв боя на Round 1 загружается после расхождения мира и остаётся на Round 1, пока player listener отсутствует; spectator также не сдвигает бой.
- После подключения игрока round запускается один раз и ждёт сохранённого хода игрока, не прокручивая промежуточные раунды.
- Load во время живого round thread не оставляет старый thread/brain и не применяет действие, ожидавшее в старой очереди, к новому миру.
- Autosave restore создаёт паузированную сессию и начинает симуляцию только через player WebSocket lifecycle.

## Implementation

Скоординировать `SaveCommands.load_game`, `GameSession.stop_round`, listener lifecycle и `_try_restore_session`. Перед заменой состояния дождаться завершения старого round thread, очистить cached turn/reaction state, атомарно загрузить world + session RNG, затем переназначить brains. Не запускать round из load/restore; единственная точка старта остаётся player WebSocket connection после регистрации listener.

Ключевые файлы: `service/commands_save.py`, `service/session.py`, `service/game_service.py`, `adapters/api/routes_ws.py`, unit/integration tests session lifecycle и save round-trip.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Старый round thread полностью завершён до загрузки snapshot
- [ ] Загруженный бой не меняется без player listener
- [ ] Spectator не запускает загруженный раунд
- [ ] Player connection запускает ровно один round loop из сохранённого состояния
- [ ] Mid-combat save → load → reconnect проходит интеграционно

## Status

`done`

## Developer Notes

`GameSession` сериализует start/stop/load через отдельный round-transition lock. Load отключает callbacks старого
раунда, полностью завершает thread, очищает cached turn и под world-state gate восстанавливает world, session RNG
и brains. Player после load остаётся без brain до следующего player connection; spectator по-прежнему не запускает
симуляцию. Autosave restore использует тот же gated restore и публикуется в registry в паузированном состоянии.

Два существующих lair integration-сценария обновлены под новый контракт: после REST load они переподключают player
WebSocket перед продолжением. Полный integration suite: 160 passed.
