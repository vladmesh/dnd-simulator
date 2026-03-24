# Task: Docker Compose Integration Test Infrastructure

**Date:** 2026-03-24
**Sprint:** 002-meta-pipeline
**Phase:** 1 — Integration Tests

## Description

Обновить docker compose и тестовую инфраструктуру для полноценных интеграционных тестов.

Текущее состояние: `docker-compose.test.yml` поднимает backend + test runner, единственный тест — health check. Нужно:

1. **Dockerfile.test** — добавить копирование тестового контента (`tests/integration/content/`)
2. **docker-compose.test.yml** — добавить `DND_DICE_SEED` в environment backend
3. **conftest.py** — расширить фикстуры:
   - `backend_url` (уже есть)
   - `ws_url` — WebSocket URL для подключения
   - `session_id` — создание сессии с тестовым миром (fixture с teardown)
   - `player_id` — создание игрока в сессии
4. **Backend** — должен использовать тестовый контент. Варианты: volume mount или env var для content path.

**Файлы:** `docker-compose.test.yml`, `Dockerfile.test`, `tests/integration/conftest.py`

## Acceptance Criteria

- [ ] `make test-integration` поднимает стек с seeded dice и тестовым контентом
- [ ] Фикстура `session_id` создаёт сессию и удаляет после теста
- [ ] Фикстура `player_id` создаёт игрока в сессии
- [ ] WebSocket подключение работает из test runner контейнера
- [ ] Существующий `test_health.py` по-прежнему проходит
- [ ] `make check` зелёный

## Status

`done`

## Developer Notes

- Volume mount (`./tests/integration/content:/app/test-content:ro`) вместо копирования в image — быстрее пересобирать, контент обновляется без rebuild.
- Фикстуры scope=session — одна сессия на весь прогон, не создаём/удаляем на каждый тест. Для arena и village отдельные сессии.
- WS helpers (`ws_connect`, `ws_recv`, `ws_send_action`) вынесены в conftest — используем websocket-client (уже в зависимостях).
