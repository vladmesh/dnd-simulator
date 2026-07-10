# Task: Периодический автосейв в FastAPI lifespan

**Date:** 2026-07-10
**Sprint:** 021-save-schema
**Phase:** 3 — Autosave hardening

## Description

Фоновый периодический автосейв (backlog `periodic-autosave-scheduler`). Сейчас автосейв срабатывает только на shutdown (`adapters/api/app.py:82`, finally-блок lifespan), после `create_player` (`service/commands_player.py:128`) и при опустении сессии (`service/game_service.py:244`). Упавший процесс теряет всё с момента последнего события — а «мир заморожен на полушаге» (simulation-core) требует, чтобы сейв был всегда свежим.

Добавить asyncio-таск в `lifespan()` (`adapters/api/app.py:52-82`): каждые `DND_AUTOSAVE_SECONDS` (env, default 120) вызывает `service.autosave_all_sessions()`. Старт после `set_service(service)`; на shutdown — `task.cancel()` + await (проглотить `CancelledError`) СТРОГО до финального `autosave_all_sessions()` в finally, чтобы не гонять два сейва одной сессии параллельно. `autosave_all_sessions` синхронный и ходит в диск — не блокировать event loop: `asyncio.to_thread` (или run_in_executor).

## Tests First

- Продуктовый сценарий: сессия с игроком мутируется (движение/урон), периодический тик срабатывает (короткий интервал в тесте, например 0.05с) → сейв-файл сессии появился/обновился и содержит свежие данные (schema_version=1, актуальный HP/локация).
- Shutdown-порядок: при останове приложения периодический таск отменён раньше финального автосейва; финальный автосейв выполнен один раз (никаких konkurrent-записей).
- Ошибка одной сессии в периодическом проходе не убивает таск: следующий тик продолжает сохранять остальные (уже покрыто поведением `autosave_all_sessions`, но пин на уровне шедулера — таск живёт после исключения).
- `DND_AUTOSAVE_SECONDS` читается из env; невалидное значение → fail-fast при старте (ValueError), не тихий дефолт.

## Implementation

После красных тестов: helper `_periodic_autosave(service, interval)` в `adapters/api/app.py` (или `service/`, если удобнее тестировать), wiring в lifespan. Документировать env в CLAUDE.md рядом с `DND_WORLD_SEED`. Тесты уровня unit с fake/минимальным service, без подъёма uvicorn (httpx ASGI-клиент или прямой вызов lifespan-хелпера).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check-backend`)
- [ ] Автосейв тикает по интервалу, отменяется на shutdown до финального сейва
- [ ] `DND_AUTOSAVE_SECONDS` документирован

## Status

`pending`
