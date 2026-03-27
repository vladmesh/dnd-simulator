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

## UX / World Builder

- [x] `dm-player-restructure` — ~~Разделить главную на Player/DM входы~~ FIXED Sprint 008 phase 4-5: master restructure, stepper, world management
- [ ] **could** `quickbar-drag-drop` — Drag-and-drop из инвентаря на action bar quickbar слоты: игрок сам выбирает какие consumables (зелья, свитки, бомбы) закрепить на панели для быстрого доступа. Сейчас consumables в drawer-popup, хватает.
- [ ] **could** `drag-resize-panels` — Drag-and-drop / resizable панели на dashboard
- [ ] **could** `mobile-layout` — Мобильная адаптация dashboard
- [ ] **could** `log-filter-tabs` — Фильтрация лога табами (Все/Бой/Диалоги)

## Tech Debt (from audits 2026-03-25)

- [x] `god-class-entities` — ~~EntitiesLayer 1215 строк~~ FIXED Sprint 005: extracted awareness_builder, activation_manager, query_handler, combat_manager, perception
- [ ] **should** `god-class-game-service` — GameService 836 строк, 43 метода. Продолжить выделение commands_*.py модулей
- [ ] **should** `god-class-politics` — PoliticsLayer 609 строк. Выделить подсистемы
- [x] `test-gaps-critical` — ~~rules/action_handlers.py без unit-тестов~~ FIXED Sprint 005: action_provider, awareness_builder, brain_factory, world isolation tests
- [x] `test-gaps` — ~~Нет тестов: action_provider, awareness, world, brain_factory~~ FIXED Sprint 005 (commands_*, session, store remain)
- [x] `rules-imports-layers` — ~~rules/trade.py импортирует из layers/~~ FIXED Sprint 005: merchant protocol extracted to core
- [x] `round-direct-layer-access` — ~~round.py напрямую импортирует EntitiesLayer~~ FIXED Sprint 005: public delegated methods
- [x] `mixin-type-ignores` — ~~27x type: ignore в service command mixins~~ FIXED Sprint 005: Protocol base added
- [ ] **should** `llm-client-type-ignores` — `# type: ignore[arg-type]` в llm/client.py на вызовах OpenAI SDK
- [x] `any-in-query-answer` — ~~Answer.value: Any~~ FIXED Sprint 005: Answer.value → object
- [x] `action-handlers-growing` — ~~action_handlers.py 605 строк~~ FIXED Sprint 005: split into rules/handlers/ (combat, equipment, items, movement, trade)
- [x] `content-loader-growing` — ~~content_loader.py 815 строк~~ FIXED Sprint 005: split into content_loader/ (world, creatures, items, monsters)
- [x] `long-methods` — ~~query() 125, resolve_attack 186~~ FIXED Sprint 005: query→query_handler, resolve_attack 186→62 lines
- [ ] **should** `test-gap-actions` — rules/actions.py (90 строк) без выделенных unit-тестов
- [ ] **should** `test-gap-weapons` — rules/weapons.py (48 строк) частично покрыт через test_combat/test_proficiency, но нет выделенных тестов
- [ ] **could** `session-serialization-duplication` — on_turn, on_action, on_round_end повторяют awareness/events/player/location сериализацию
- [ ] **could** `npc-behaviors-yaml-loading` — layers/entities/npc_behaviors.py загружает YAML на уровне модуля с global state mutation. Перенести в content_loader
- [ ] **could** `action-parsing-in-adapter` — Adapter (routes_ws) парсит Action из JSON, должен service layer
- [x] `magic-number-trade` — ~~Magic number 0.08 в politics/layer.py:338~~ FIXED 2026-03-24
- [ ] **should** `thick-adapter-world-state` — routes_master.py:290-330 оркестрирует 7+ layer queries напрямую + assert-based validation (500 при плохих данных). Вынести в GameService.get_world_state()
- [ ] **should** `routes-master-growing` — routes_master.py 554 строк, 32 роута. Разделить content-editing и session-control роуты
- [ ] **should** `test-gap-content-loader` — content_loader/schema_gen, refs, utils без выделенных unit-тестов (частично покрыты интеграционными)
- [ ] **could** `player-status-in-adapter` — routes_player._player_status() маппит Ability enum → строки, presentation logic в адаптере

## Security (from audits 2026-03-25)

- [ ] **should** `cors-wildcard` — CORS allow_origins=["*"], allow_methods=["*"], allow_headers=["*"] в app.py
- [ ] **should** `no-auth` — Нет аутентификации/авторизации, все эндпоинты открыты по session_id
- [ ] **should** `no-csrf` — Нет CSRF protection на state-changing HTTP; с CORS=* browser-based CSRF тривиален
- [ ] **could** `ws-max-size` — Нет лимита на размер WebSocket сообщений
- [ ] **could** `ws-origin-optional` — WS origin validation через env var, по умолчанию выключена; case-sensitive
- [ ] **could** `frontend-error-endpoint` — POST /api/frontend-error принимает произвольный JSON без валидации
- [ ] **could** `rest-rate-limiting` — Нет rate limiting на REST эндпоинтах (WS имеет token bucket)
- [ ] **could** `action-params-validation` — Action params из клиента без schema validation
- [ ] **could** `llm-prompt-injection` — Player say() текст попадает в NPC memory → system prompt

## Dead Code (from audit 2026-03-25)

- [ ] `dead-move-away-from-target` — core/brain.py:59, zero callers (future movement AI)
- [ ] `dead-auto-fail-saves` — rules/conditions.py:32 (future saving throws)
- [ ] `dead-refund` — core/turn_budget.py:54 (future reaction system)
- [ ] `dead-check-reactions` — round.py:302, stubbed (future reaction system)
