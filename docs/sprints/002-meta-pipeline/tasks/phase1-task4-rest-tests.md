# Task: REST API Integration Tests

**Date:** 2026-03-24
**Sprint:** 002-meta-pipeline
**Phase:** 1 — Integration Tests

## Description

Написать интеграционные тесты для REST API через httpx. Тесты дёргают реальный бэкенд в compose, проверяют ответы через ассерты.

Сценарии:

**Session lifecycle:**
- POST /sessions → создание сессии с тестовым миром
- GET /sessions → сессия в списке
- GET /sessions/{id} → полное состояние мира (god mode)
- DELETE /sessions/{id} → сессия удалена

**Player:**
- POST /sessions/{id}/character → создание персонажа
- GET /sessions/{id}/status → статус персонажа совпадает с созданным

**Creatures (hot controls):**
- GET /sessions/{id}/creatures → список содержит NPC из тестового мира
- POST /sessions/{id}/creatures → спавн нового существа
- PATCH /sessions/{id}/creatures/{eid} → изменение HP
- DELETE /sessions/{id}/creatures/{eid} → существо удалено

**Saves:**
- POST /sessions/{id}/save → сохранение
- GET /sessions/{id}/saves → сохранение в списке
- POST /sessions/{id}/saves/{name}/load → загрузка, состояние восстановлено

**Time:**
- POST /sessions/{id}/time/advance → время продвинулось, events вернулись

**Файлы:** `tests/integration/test_rest_api.py`

## Acceptance Criteria

- [ ] Все сценарии выше покрыты ассертами на статус-коды и тела ответов
- [ ] Тесты изолированы: каждый создаёт свою сессию или использует фикстуру с cleanup
- [ ] Детерминированные результаты (dice seed)
- [ ] `make test-integration` зелёный

## Status

`todo`

## Developer Notes

_(заполняется по завершении)_
