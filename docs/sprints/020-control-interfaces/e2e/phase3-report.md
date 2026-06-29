# E2E Report: sprint020-phase3

**Date:** 2026-06-29
**Flags:** --no-llm
**Sections tested:** Phase 3 new functionality (spectator Live feed) + targeted regression (1 session setup, 3 combat, 10 dashboard)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 7 tested, 7 passed, 0 failed
- Quick fixes: 0
- Blockers: 0

Phase 3 delivered the spectator-listener primitive, disconnect grace-period, `?spectate=true` WS endpoint, and the frontend Live observe feed. The live feed was verified end-to-end across two browser tabs: a connected player generating combat events and a master (admin + DM) observing them stream into a read-only feed.

## Results

### Auto-discovered (Phase 3 focus)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| P3.1 | Live tab present for admin (observe lens) | pass | SessionView for admin shows tabs Мир/Существа/**Лента**; Time/Saves hidden; "Наблюдение (только чтение)" badge present |
| P3.2 | Live tab present for DM (full lens) | pass | SessionView for DM shows all 5 tabs Мир/Существа/**Лента**/Время/Сохранения; no observe badge |
| P3.3 | Spectator WS connects read-only | pass | `?spectate=true&user_id=admin1&role=admin` accepted; backend `add_spectator spectator_count: 1`; feed has no action affordances |
| P3.4 | Live event streaming (player acts → spectator feed updates) | pass | Player (tab 0) attacked NPC; admin spectator feed (tab 1) streamed 5 events live: `combat_started`, `entity_attack` (full dice breakdown), `entity_died`, `reputation_changed`, `combat_ended`, each with event-type badge + RU description |
| P3.5 | Spectator churn does not evict session | pass | Multiple spectator connect/disconnect cycles (StrictMode remount + tab nav) logged `add_spectator`/`remove_spectator` only; never `stop_round`/evict while player connected; session stayed reachable for the later DM spectator |
| P3.6 | Empty replay state | pass | Spectator connecting to a peaceful/idle session shows "Ожидание событий…" placeholder (no event lines to replay) |

Disconnect grace-period (debounce evict) was not separately exercised through the UI (1.5s race window); it is covered deterministically by the integration suite (`test_websocket.py`, green this run) and unit tests (`test_session_lifecycle.py`). Backend log confirms the player `remove_listener` during remount logged `scheduled_evict: false` while a player listener remained — eviction is gated on player listeners.

### Regression

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.2 | Quick start — create character, enter game | pass | Sword Vale → new session c56eb0b8 → Fighter human STR15/CON14 Defense → redirect to /play/:id, dashboard renders, "Подключено" toast |
| 1.x | Player WS identity propagation (wsClient.ts change) | pass | Player socket URL carries `user_id=admin1&role=player`; connection established |
| 3.x | Combat (incidental, used to generate feed events) | pass | combat_started → attack `[d20(19)+4=23 vs КЗ 10] 4 урона (1d8 рубящий + +2 str)` → death → reputation 100→80 → combat_ended; loot panel ("Добыча") appeared after kill |
| 10.1 | Three-column dashboard | pass | Поблизости / Персонаж+Инвентарь / Локация all on screen; 6 equip slots |

## Quick Fixes

- None.

## Findings

### Blockers
- None.

### Minor
- **English faction id leaks into RU combat log.** The reputation line renders as «Твоя репутация с **kingdom** изменилась (100 → 80)» — `kingdom` is a raw faction id inside a Russian string. Appears in both the player log and the spectator feed (the feed faithfully mirrors the source event). This is the known backlog item `combat-log-i18n-gaps`, already scheduled for **Phase 4** of this sprint. Not a Phase 3 regression.

## Log Analysis

- `/tmp/dnd-e2e-backend.log`: 0 errors, 0 exceptions, 0 tracebacks.
- Spectator lifecycle is clean: `add_spectator`/`remove_spectator` pairs on every connect/disconnect, no `stop_round` or eviction event anywhere in the run (player stayed connected throughout).
- Only warnings observed are the benign dev StrictMode "WebSocket is closed before the connection is established" (player and spectator sockets), with the subsequent connection succeeding in each case. 0 console errors on every page.
