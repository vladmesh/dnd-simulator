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

`done`

## Developer Notes

8 WS тестов: connect+turn, reconnect replay, invalid session, peaceful wait, attack→combat, end_turn, unknown message type, invalid action name.

Ключевые решения:
- WS тесты используют **отдельные сессии** (module-scoped fixtures), не shared с REST — round thread портит состояние.
- Peaceful turn не содержит `budget`/`player` — только combat turn. Ассерты скорректированы.
- Combat end_turn тест учитывает состояние от предыдущего attack теста (module scope).
- `_recv_until()` хелпер для drain сообщений до нужного типа — round thread шлёт turn/round_result/action_result асинхронно.

**Баг найден и пофикшен:** `routes_ws.py` не ловил `ValueError` от `ActionType()` при невалидном action name — WS закрывался вместо error message. Добавлен try/except с error response.
