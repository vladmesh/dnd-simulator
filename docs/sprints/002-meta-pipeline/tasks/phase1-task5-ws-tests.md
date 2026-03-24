# Task: WebSocket Integration Tests

**Date:** 2026-03-24
**Sprint:** 002-meta-pipeline
**Phase:** 1 — Integration Tests

## Description

Написать интеграционные тесты для WebSocket game loop. Подключение к реальному бэкенду в compose, эмуляция игрока через websocket client.

Сценарии:

**Connection:**
- Подключение к WS /api/ws/{session_id}?player_id={pid}
- Получение первого `turn` сообщения (awareness, events, budget)
- Reconnect: повторное подключение → replay last turn

**Peaceful turn:**
- Получение turn с mode=peaceful
- Отправка wait action → round_result

**Combat flow:**
- Игрок и NPC в одной локации → бой начинается (или триггерим через attack)
- Получение turn с mode=combat, budget с actions/movement
- Отправка attack action → action_result с damage (детерминированный через dice seed)
- Бой до конца → round_result или game_over

**Error handling:**
- Невалидный action → error message
- Rate limiting: быстрая отправка 20+ сообщений → отклонение

**Файлы:** `tests/integration/test_websocket.py`

## Acceptance Criteria

- [ ] Полный боевой цикл: подключение → turn → attack → результат с проверкой damage
- [ ] Peaceful flow: wait → round завершён
- [ ] Reconnect replay работает
- [ ] Error handling проверен
- [ ] Все ассерты на конкретные значения (damage, HP) благодаря dice seed
- [ ] `make test-integration` зелёный

## Status

`todo`

## Developer Notes

_(заполняется по завершении)_
