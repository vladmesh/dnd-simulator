# Sprint 002 — Meta Pipeline

**Goal:** Формализовать процесс разработки и покрыть стек интеграционными тестами. После спринта: новые фичи катятся быстрее и безопаснее, пайплайн воспроизводим через скиллы, интеграционные тесты ловят баги на стыке фронт↔бэк автоматически.

**Type:** Tech sprint

**Started:** 2026-03-24

## Context

Sprint 001 показал что пайплайн работает, но каждый шаг выполняется вручную. Нет интеграционных тестов (дыра между unit и E2E). Скиллы покрывают только хвост пайплайна (audit, update-docs). Нужен фундамент для масштабирования процесса.

**Ссылки:** [SPRINT_PIPELINE.md](../../SPRINT_PIPELINE.md), [BACKLOG.md](../../BACKLOG.md)

---

## Phase 1: Integration Tests

Полностью автоматизированные тесты внутри docker compose. Изолированный стек: бэкенд идентичный проду. Детерминированный: без LLM (только rule brains), dice seed для предсказуемых результатов. Тестовый контент (минимальный мир). Pytest + httpx/websockets. REST + WebSocket.

**Tasks:**

1. [Deterministic Dice (DND_DICE_SEED)](tasks/phase1-task1-dice-seed.md)
2. [Minimal Test World](tasks/phase1-task2-test-content.md)
3. [Docker Compose + Test Infra](tasks/phase1-task3-compose-infra.md)
4. [REST API Integration Tests](tasks/phase1-task4-rest-tests.md)
5. [WebSocket Integration Tests](tasks/phase1-task5-ws-tests.md)

## Phase 2: Sprint Pipeline Skills

Скиллы для каждого этапа пайплайна: планирование (сократовский диалог), генерация задач, закрытие задач, E2E прогон, закрытие спринта.

**Tasks:**

_(генерируются отдельно перед началом фазы)_

---

## Status

**Current:** Phase 1 tasks generated. Ready to start task 1 (dice seed).

## Decisions

- **API-only в Phase 1** — фронтенд и Playwright в compose отложены. Сначала покрываем REST + WebSocket, Playwright добавим позже.
- **Dice seed через env var** — не DI, не stub. Module-level `_rng` с seed. Минимальное изменение, один файл.

## Deferred

_(заполняется по ходу спринта)_

## Results

_(заполняется в конце спринта)_
