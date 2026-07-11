# E2E Report: sprint022-post-audit

**Date:** 2026-07-12
**Flags:** --no-llm
**Sections tested:** 1.1-1.5, 2.1, 2.3-2.4 + Sprint 022 travel regression
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 8 tested, 8 passed after 1 quick fix
- Quick fixes: 1 applied
- Blockers: 0 found

## Results

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing page Player/DM split | pass | Русские Player и DM entry points видны, переключатель языка доступен. |
| 1.2 | Quick start in Sword Vale | pass | Новая сессия создалась, персонаж вошёл в игру, WebSocket подключился. |
| 1.3 | Language surface | pass | Landing, setup и game UI полностью отобразились в RU без raw translation keys. |
| 1.4 | Fighter point buy | pass | STR 15 и CON 14 оставили 3 очка; preview показал HP 12, AC 19, 1000 gold. |
| 1.5 | Fighter class UI | pass | Fighting Style и Chain Mail / Longsword / Shield отображались; Defense дал AC 19. |
| 2.1 | Peaceful perception | pass | Марта видна рядом с Attack/Talk controls. |
| 2.3 | Wait and time advance | pass | Wait сдвинул время с 10:00 до 11:00 и вернул следующий ход. |
| A1 | Destination-based travel | pass | После quick fix generic Travel action скрыт; путь в Location Panel передал `destination_id` и переместил игрока на Рыночную площадь без ошибки round loop. |

## Quick Fixes

- `ActionBar` больше не показывает generic `travel` как простую кнопку. Маршрут выбирается через Location Panel, единственный UI, который передаёт обязательный `destination_id`. Добавлен regression test.

## Findings

### Blockers

None.

### Minor

- При первом подключении после создания персонажа браузер один раз сообщил о закрытии первоначального WebSocket до установления соединения. Замещающее соединение открылось сразу, действия Wait и Travel выполнились штатно. Это известный dev-proxy/reconnect artifact.

## Log Analysis

- До quick fix generic Travel button вызвал `ValueError: Action travel missing required param: destination_id` и `GAME OVER`; исправление воспроизведено и проверено через чистую UI-сессию.
- После исправления повторный travel прошёл без новых backend errors или browser console errors.
- Focused frontend regression: 22/22 tests passed.
