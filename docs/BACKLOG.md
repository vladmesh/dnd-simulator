# Backlog

Приоритеты: **must** — блокирует следующие уровни или играбельность, **should** — заметно улучшает качество, **could** — nice to have.

Механики и контент с зависимостями — в [ecs-and-content.md](docs/brainstorms/ecs-and-content.md).
Валидация и инварианты — в [world-state-machine.md](docs/brainstorms/world-state-machine.md).
Что сделано — в [ROADMAP.md](docs/ROADMAP.md).

---

## Gameplay

- [ ] **must** `monster-spawn` — Система спавна монстров: триггеры (proximity, time, event), таблицы встреч по региону/локации, CR-бюджет
- [ ] **must** `quest-system` — Система квестов: цели, триггеры завершения, награды. Минимум: fetch/kill/escort
- [ ] **should** `key-npcs` — Ключевые NPC (антагонист, компаньон): глубокая память, реакция на мировые события, персональные цели
- [ ] **should** `npc-wandering` — Динамические маршруты NPC между поселениями (сейчас только статичные расписания)
- [ ] **should** `npc-death-on-war` — NPC гибнут/исчезают при захвате поселения, войне
- [ ] **should** `combat-reassess` — NPC переоценивает стратегию при смене ситуации (союзник упал, новый враг появился)
- [ ] **could** `conversation-costs-time` — Каждая реплика разговора тратит 6 секунд игрового времени (частично)

## World Simulation

- [ ] **should** `settlement-defenses` — Восстановление defenses поселений со временем
- [ ] **should** `population-economy` — Влияние населения на доход (сейчас только prosperity)
- [ ] **could** `settlement-lifecycle` — Создание/уничтожение поселений динамически
- [ ] **could** `alliance-logic` — Логика альянсов (ALLIANCE статус есть, механики нет)
- [ ] **could** `vassalage` — Вассалитет между нациями
- [ ] **could** `trade-routes` — Торговые маршруты между конкретными поселениями
- [ ] **could** `seasonal-travel` — Сезонные эффекты на путешествия
- [ ] **could** `procedural-gen` — Процедурная генерация регионов/мира

## LLM

- [ ] **should** `llm-model-tiering` — Выбор модели по важности NPC: дорогая для ключевых, дешёвая для фоновых
- [ ] **could** `llm-narrator` — Интерпретация абстрактных изменений мира в нарративные описания
- [ ] **could** `npc-language` — Динамический выбор языка NPC (из настроек или по языку игрока)

## Tech Debt (from audit 2026-03-24)

- [ ] **should** `god-class-entities` — EntitiesLayer 821 строк, 30 методов. Выделить awareness builder, activation manager, query handler
- [ ] **should** `god-class-politics` — PoliticsLayer 587 строк. Выделить подсистемы
- [ ] **should** `test-gaps` — Нет тестов: awareness, items, world, turn_budget, location, brain_factory, commands_*, session, store
- [ ] **should** `mixin-type-ignores` — 27x `# type: ignore[attr-defined]` в service command mixins. Добавить Protocol/ABC
- [ ] **should** `llm-client-type-ignores` — `# type: ignore[arg-type]` в llm/client.py на вызовах OpenAI SDK
- [ ] **should** `hardcoded-content` — ~120 строк game content (расписания, реплики) в entities/models.py вместо YAML
- [ ] **could** `long-methods` — query() 125 строк, run_combat_turn 124, resolve_attack 106
- [ ] **could** `action-parsing-in-adapter` — Adapter (routes_ws) парсит Action из JSON, должен service layer
- [ ] **could** `magic-number-trade` — Magic number 0.08 в politics/layer.py:338

## Security (from audit 2026-03-24)

- [ ] **should** `cors-wildcard` — CORS allow_origins=["*"] в app.py
- [ ] **could** `ws-max-size` — Нет лимита на размер WebSocket сообщений
- [ ] **could** `action-params-validation` — Action params из клиента без schema validation
- [ ] **could** `log-injection` — /api/frontend-error пишет unsanitized JSON в логи

## Dead Code (from audit 2026-03-24)

- [ ] `dead-move-away-from-target` — core/brain.py:59, zero callers (future movement AI)
- [ ] `dead-auto-fail-saves` — rules/conditions.py:111 (future saving throws)
- [ ] `dead-refund` — core/turn_budget.py:54 (future reaction system)
- [ ] `dead-check-reactions` — round.py:302, stubbed (future reaction system)
