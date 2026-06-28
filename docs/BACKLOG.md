# Backlog

Приоритеты: **must** — блокирует следующие уровни или играбельность, **should** — заметно улучшает качество, **could** — nice to have.

Механики и контент с зависимостями — в [ecs-and-content.md](brainstorms/ecs-and-content.md).
Валидация и инварианты — в [world-state-machine.md](brainstorms/world-state-machine.md).
Что сделано — в [ROADMAP.md](ROADMAP.md).
Свежие находки аудита живут в [audit.md](audit.md) до триажа; `/audit-triage` переносит их сюда.

---

## Gameplay

- [ ] **must** `monster-spawn` — Система спавна монстров: триггеры (proximity, time, event), таблицы встреч по региону/локации, CR-бюджет
- [ ] **must** `quest-system` — Система квестов: цели, триггеры завершения, награды. Минимум: fetch/kill/escort
- [ ] **should** `key-npcs` — Ключевые NPC (антагонист, компаньон): глубокая память, реакция на мировые события, персональные цели
- [ ] **should** `npc-wandering` — Динамические маршруты NPC между поселениями (сейчас только статичные расписания)
- [ ] **should** `npc-death-on-war` — NPC гибнут/исчезают при захвате поселения, войне
- [ ] **should** `divine-sense` — Divine Sense (Paladin): detect celestial/fiend/undead. Требует `CreatureType` enum на Creature, creature_type в каталогах монстров, resource pool (1 + CHA mod / long rest)
- [ ] **should** `divine-smite-scaling` — Divine Smite масштабирование: slot 2 → +3d8, +1d8 vs undead/fiend. Когда будет система уровней и `CreatureType`
- [ ] **should** `combat-reassess` — NPC переоценивает стратегию при смене ситуации (союзник упал, новый враг появился)
- [ ] **should** `versatile-weapons` — Versatile weapon property: переключение одноручный/двуручный хват, разный урон (longsword 1d8/1d10, warhammer 1d8/1d10, quarterstaff 1d6/1d8). WeaponDef.versatile_damage, автовыбор хвата по наличию щита
- [ ] **should** `hit-dice-short-rest` — Hit Dice spending на коротком отдыхе: ResourcePool(hit_dice, max=level, reset_on=LONG_REST), игрок выбирает сколько тратить, за каждую кость roll(class_hit_die)+CON_mod HP. Long rest восстанавливает max(1, level//2) костей (partial reset). Нужен PlayerBrain callback для выбора количества + UI
- [ ] **could** `conversation-costs-time` — Каждая реплика разговора тратит 6 секунд игрового времени (частично)
- [ ] **should** `loot-drops-monsters` — Общемонстровый дроп: loot-таблицы на шаблонах монстров, корпс-лут с обычных мобов поверх action `take` (Sprint 018 закладывает примитив `Lootable`/`transfer_items`)
- [ ] **should** `theft` — Воровство как отдельный режим доступа к инвентарю: take у живого несогласного владельца, contested Sleight of Hand против Perception, crime/репутация; отдельная `validate_steal` поверх общего `transfer_items`
- [ ] **should** `spawn-event-trigger` — Event-триггер спавна (спавн по мировому событию), в связке со спринтом квестов
- [ ] **could** `container-hp-locks` — Сундуки с замком/HP: взлом (lockpicking) и «разбить» контейнер
- [ ] **could** `lair-actions` — D&D lair actions на ядре логова
- [ ] **could** `lair-new-leader` — После смерти ядра логово с шансом поднимает нового вожака вместо деплита (динамика мира)

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
- [ ] **should** `master-panel-creature-inventory` — `CreatureResponse` / `all_entities` query не включают inventory/equipped_weapon; мастер не видит предметы существ. Добавить поля в схему и query
- [x] `master-give-item-ui` — ~~endpoint для give_item есть, кнопки нет~~ FIXED Sprint 007 phase 2: кнопка «Выдать предмет» в карточке существа
- [x] `inspect-as-idle-param` — ~~inspect шёл как `Action(IDLE, {inspect_target})`~~ FIXED Sprint 009 phase 4: клиентская NpcInspectModal из awareness
- [x] `world-builder-js-modules` — ~~world-builder.js 1700+ строк~~ OBSOLETE Sprint 008 phase 4: legacy vanilla JS заменён React SPA

## Engine & Session

- [ ] **should** `travel-action-type` — `go`/travel реализован как хак: `LocationPanel` шлёт `Action(WAIT, {hours: 0, travel_to})`. Нужен отдельный `ActionType.TRAVEL` с хендлером, валидацией маршрута и расчётом времени
- [ ] **should** `npc-instant-say-response` — после `say` тикнуть NPC в локации (1 раунд), чтобы RuleBrain/LlmBrain ответил в том же запросе. Сейчас NPC отвечают только при `advance_time`
- [ ] **could** `list-npcs-iterate-entities` — `list_npcs` итерирует по регионам; NPC в несуществующем регионе выпадает из списка. Итерировать по entities напрямую
- [ ] **could** `periodic-autosave-scheduler` — фоновый asyncio таск в FastAPI lifespan каждые ~2 мин вызывает `autosave_all_sessions()`; cancel на shutdown перед финальным autosave. Дополняет per-action и shutdown автосейв

## DevOps / Infra

- [ ] **should** `containerized-stack` — Воспроизводимый контейнерный сетап для подъёма всего стека (фронт + бэк) одной командой. Двойная польза: локально быстро поднять перед E2E и переиспользовать на проде. Сейчас `docker-compose.test.yml` — только `backend` + `integration-tests` (pytest), без фронта и без проброса портов наружу, поэтому браузерный E2E гоняется на хостовых `uvicorn`/`vite`: ловит убийство процесса песочницей при бинде порта и зависит от хостовых Node/uv. План: добавить сервис `frontend` (собранный бандл через `vite build` + `vite preview` или nginx со статикой, не dev-сервер — заодно тестируем прод-бандл), пробросить `8001`/`5173`, оформить профилем `--profile e2e` чтобы не мешать `integration-tests`, и перевести шаг «Start the stack» в скилле `/e2e` на `docker compose --profile e2e up`. Прод-вариант: тот же образ фронта (nginx) + бэкенд, общий базовый compose. Не закрывает E2E-в-CI (нужен отдельно Playwright-в-контейнере + написанные спеки) — это про воспроизводимость стека, не про сами тесты

## Performance

- [ ] **could** `awareness-rebuild-cache` — `build_awareness()` делает 4-5 query к нижним слоям на каждый ход каждого существа (O(N)/раунд), bottleneck при >20 LlmBrain NPC. Решение: WorldSnapshot per (region, tick) для weather/region/settlements/politics + dirty-flag per location для nearby entities. Делать когда начнёт тормозить

## Bugs

- [ ] **could** `corpse-nearby-actions` — мёртвое существо показывается в Nearby-панели с кнопками Attack/Talk/Inspect (E2E sprint 018 phase 2). Лут идёт через отдельный LootPanel; атака трупа возвращает корректное «уже мертва», так что ничего не ломается — но Attack/Talk на трупе бессмысленны. Скрывать их для мёртвых (или убирать трупы из Nearby, раз есть LootPanel)
- [ ] **should** `battle-map-configs-not-wired` — `battle_map_configs` из `regions.yaml` не передаётся в `EntitiesLayer` при создании сессии в `game_service.py`. Все combat maps дефолтят в 60×60. `load_battle_maps()` keyed by region_id, `CombatManager` ищет по location_id — нужен маппинг через `location_graph`
- [ ] **should** `player-character-no-attacks` — `POST /api/player/sessions/{id}/character` не принимает `attacks`; персонаж дерётся кулаками (1 урон). Добавить `attacks` в `CreatePlayerRequest` и `parse_player` (проверить — мог закрыться в Sprint 013 char-creation)
- [ ] **could** `look-action-i18n-hardcode` — `_cmd_look` в GameService хардкодит строки «Terrain:»/«Weather:» вместо `_()`. Не критично (perception API отдаёт сырые данные), но для консистентности text-команд стоит перевести
- [x] `sneak-attack-faction-check` — ~~SA ally-adjacency считала союзником любое живое существо в 5ft без учёта фракции~~ FIXED Sprint 011/014: ally detection через faction relations
- [x] `flaky-initiative-test` — ~~`test_second_attack_does_not_reroll_initiative` падал рандомно~~ FIXED: AC=30 чтобы атаки всегда мазали, c2 не удаляется из turn_order
- [ ] **could** `flaky-schemaform-ref-select` — `frontend/src/components/master/__tests__/SchemaForm.test.tsx > renders ref field as select with fetched options` флапает в полном `npx vitest run` (ждёт 3 option, видит 1), но зелёный при изоляции файла и на повторе. Похоже на гонку мока fetch ref-опций / async-рендера select. Замечен на Sprint 018 phase 3 (бэкенд-only коммит, влиять не мог). Стабилизировать ожидание опций (`findBy`/`waitFor`) или изолировать fetch-мок между тестами

## Tech Debt (from audits 2026-03-25, updated 2026-03-29)

- [x] `god-class-entities` — ~~EntitiesLayer 1215 строк~~ FIXED Sprint 005: extracted awareness_builder, activation_manager, query_handler, combat_manager, perception
- [ ] **should** `god-class-game-service` — GameService 1044 строки (836 на 2026-04-13, растёт). Продолжить выделение commands_*.py модулей
- [x] `god-class-politics` — ~~PoliticsLayer 609 строк~~ FIXED Sprint 014 phase 0: split into diplomacy.py, warfare.py, economy.py submodules
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
- [x] `session-serialization-duplication` — ~~on_turn, on_action, on_round_end повторяют сериализацию~~ FIXED Sprint 012 phase 4: shared event builder extracted
- [ ] **could** `npc-behaviors-yaml-loading` — layers/entities/npc_behaviors.py загружает YAML на уровне модуля с global state mutation. Перенести в content_loader
- [ ] **could** `action-parsing-in-adapter` — Adapter (routes_ws) парсит Action из JSON, должен service layer
- [x] `magic-number-trade` — ~~Magic number 0.08 в politics/layer.py:338~~ FIXED 2026-03-24
- [ ] **should** `thick-adapter-world-state` — routes_master.py:290-330 оркестрирует 7+ layer queries напрямую + assert-based validation (500 при плохих данных). Вынести в GameService.get_world_state()
- [ ] **should** `routes-master-growing` — routes_master.py 560 строк, 34 роута. Разделить content-editing и session-control роуты
- [ ] **should** `test-gap-content-loader` — content_loader/refs, utils, creatures без выделенных unit-тестов (частично покрыты интеграционными)
- [ ] **should** `core-brain-imports-rules` — core/brain.py:50,63,141 lazy-imports из rules/ (calculate_direction, get_weapon_attack). core не должен зависеть от rules. Перенести RuleBrain в rules/ или service/, или inject rule functions
- [ ] **should** `test-gap-session` — service/session.py 457 строк, 27 методов без выделенных unit-тестов. Round lifecycle, listener dispatch, resolve_abstract_move непокрыты
- [ ] **should** `god-class-combat-manager` — layers/entities/combat_manager.py 535 строк. Выделить initiative/turn logic от combat state management
- [ ] **could** `entities-layer-imports-content-loader` — layers/entities/layer.py:465,484,490 lazy-imports из content_loader в load_state. Layers → core only, content_loader — peer module
- [ ] **could** `player-status-in-adapter` — routes_player._player_status() маппит Ability enum → строки, presentation logic в адаптере
- [ ] **should** `merchant-provider-in-rules` — MerchantActionProvider в rules/ хранит world-query callback (I/O в pure rules). Перенести в service/ или передавать данные аргументом
- [x] `dice-os-import` — ~~rules/dice.py import os~~ FIXED audit 2026-03-31: set_global_seed() function
- [ ] **should** `base-action-provider-stateful` — BaseActionProvider в rules/ — stateful class с self._types. Сделать standalone функцией или frozen dataclass
- [ ] **should** `adapter-imports-core-directly` — routes_player импортирует PlayerCharacter/Ability, routes_master — Query/QueryType напрямую из core. Вынести бизнес-логику в GameService
- [ ] **should** `any-to-object-sweep` — 15+ файлов используют dict[str, Any] вместо dict[str, object] (core/models, layers, llm, adapters)
- [ ] **should** `entity-type-enum` — "player"/"npc"/"creature" строковые сравнения в 5+ файлах. Добавить EntityType(StrEnum)
- [ ] **should** `brain-type-enum` — ai_type == "rule_based" строковые сравнения. Добавить BrainType(StrEnum)
- [ ] **should** `layer-source-string-cmp` — game_service.py L535,595,611,626 source == "library" вместо LayerSource.LIBRARY enum
- [x] `long-func-run-combat-turn` — ~~round.py run_combat_turn 132 строки~~ FIXED Sprint 012 phase 4: extracted _prepare_combat_turn() + _build_combat_awareness()
- [x] `long-func-choose-combat-action` — ~~core/brain.py _choose_combat_action 114 строк~~ FIXED Sprint 014 phase 0: decomposed into _CombatContext + per-action helpers
- [ ] **should** `round-growing` — round.py 612 строк. Extract combat-turn and awareness-building into helpers
- [ ] **could** `action-defs-growing` — core/action_defs.py 541 строка. Рассмотреть data-driven YAML формат для action registry
- [ ] **should** `perception-fail-fast` — layers/entities/perception.py 54x .get() с silent defaults. Маскирует отсутствие данных в событиях
- [ ] **could** `test-bare-status-codes` — test_api.py, test_trade_ws.py используют bare 200/404 вместо HTTPStatus
- [ ] **should** `long-func-start-round` — service/session.py start_round 103 строки. Extract closures into named methods
- [x] `perception-dispatch-chain` — ~~perception.py if-elif chain~~ FIXED Sprint 012 phase 4: dict[EventType, handler] dispatch
- [ ] **should** `activation-manager-growing` — activation_manager.py 614 строк (406 на 2026-04-13; вырос на encounter-rolling в Sprint 018). Extract EncounterRoller (_roll_encounters, _is_daylight_at) + _materialize_squads()
- [ ] **could** `deep-nesting-diplomacy` — politics/layer.py _process_diplomacy 7 уровней вложенности
- [ ] **should** `silent-failure-autosave` — 3x contextlib.suppress(Exception) вокруг autosave. Логировать ошибки, не глушить
- [x] `silent-failure-awareness` — ~~awareness_builder.py 6x broad except Exception~~ FIXED Sprint 012 phase 4: narrowed to KeyError/LookupError
- [ ] **should** `silent-failure-movement` — handle_wait except ValueError: pass. Возвращать ошибку в ActionResult
- [ ] **could** `schema-form-growing` — frontend SchemaForm.tsx 488 строк, 30+ nested helpers
- [ ] **should** `llm-imports-layer-models` — llm/brain.py и llm/summarizer.py импортируют из layers.entities.models (Npc, NpcMemory). llm не должен зависеть от layers
- [ ] **should** `round-imports-entities-layer-v2` — round.py:31 напрямую импортирует EntitiesLayer (sprint 012 re-introduced coupling). Взаимодействовать через World/Layer interface
- [ ] **should** `mutable-dataclass-models` — Region, Nation, Settlement, Leader — @dataclass без frozen=True. Аудит: мутируются ли in-place или можно frozen
- [ ] **should** `proficiency-hardcoded-weapons` — rules/proficiency.py:33-34 хардкоженные строки оружия ("rapier", "shortsword"). Использовать enum или catalog ref
- [ ] **should** `perception-hardcoded-weapons` — perception.py:29-31 дублирует названия оружия из YAML каталогов
- [ ] **should** `content-loader-fail-fast` — 31 .get() с дефолтами в content_loader/. Некоторые оправданы (YAML boundary), но bm_data.get("width", 60) молча дефолтит размер карты
- [ ] **should** `dict-str-object-overuse` — 57+ dict[str, object] вместо TypedDict/dataclass в query_handler, game_service, combat_manager, schemas
- [ ] **should** `world-private-method-access` — world._make_query_fn() вызывается из session.py и round.py. Выставить как public API
- [ ] **could** `event-log-eslint-suppress` — EventLog.tsx eslint-disable-next-line react-hooks/exhaustive-deps
- [ ] **could** `api-client-growing` — apiClient.ts 365 строк, 35+ методов. Разделить по домену
- [ ] **could** `world-overview-growing` — WorldOverview.tsx 331 строка. Split sub-components
- [ ] **should** `class-features-hardcoded` — ClassFeatures/proficiency system hardcoded в Python. Adding new class requires code, not YAML. Vision drift.

## Security (from audits 2026-03-25)

- [ ] **should** `cors-wildcard` — origins теперь конфигурируются через `CORS_ALLOWED_ORIGINS` env + credentials отключаются при `*` (fixed d459e19). Остаётся: `allow_methods=["*"]`, `allow_headers=["*"]` всё ещё хардкод
- [ ] **should** `no-auth` — Нет аутентификации/авторизации, все эндпоинты открыты по session_id
- [ ] **should** `no-csrf` — Нет CSRF protection на state-changing HTTP; с CORS=* browser-based CSRF тривиален
- [ ] **could** `ws-max-size` — Нет лимита на размер WebSocket сообщений
- [ ] **could** `ws-origin-optional` — WS origin validation через env var, по умолчанию выключена; case-sensitive
- [ ] **could** `frontend-error-endpoint` — POST /api/frontend-error принимает произвольный JSON без валидации
- [ ] **could** `rest-rate-limiting` — Нет rate limiting на REST эндпоинтах (WS имеет token bucket)
- [ ] **could** `action-params-validation` — Action params из клиента без schema validation
- [ ] **could** `llm-prompt-injection` — Player say() текст попадает в NPC memory → system prompt
- [ ] **could** `ws-stall-vector` — routes_ws.py future.result(timeout=30) блокирует Round thread если клиент не читает
- [ ] **could** `layer-file-max-length` — UpdateLayerFileRequest.content без max_length — произвольный YAML на диск
- [ ] **could** `llm-prompt-no-separation` — NPC memory, entity descriptions интерполируются в system prompt без разделительной границы
- [ ] **could** `ability-scores-no-bounds` — ability_scores и attacks принимают произвольные значения без bounds validation
- [ ] **could** `world-name-path-traversal` — game_service.py:81 world_name from request used in path construction without regex guard at call site

## Dead Code (from audit 2026-03-25)

- [x] `dead-move-away-from-target` — ~~core/brain.py, zero callers~~ FIXED audit 2026-03-31: removed
- [x] `dead-auto-fail-saves` — ~~rules/conditions.py:32~~ FIXED audit 2026-03-31: removed
- [ ] `dead-refund` — core/turn_budget.py:58 (tested but unused, future budget mechanic)
- [x] `dead-check-reactions` — ~~stubbed~~ FIXED Sprint 012: wired into round loop
- [ ] `dead-is-daylight` — rules/geography.py:172, tested but unused in prod. Wire into geography layer or remove
- [ ] `dead-prone-stand-cost` — rules/conditions.py:27, tested but never integrated into movement handler
- [x] `dead-reset-resources` — ~~rules/resources.py, 12 test refs, 0 prod~~ FIXED Sprint 015 phase 1: wired into rest handlers
- [ ] `dead-walk-path` — rules/movement.py:201, 12 test refs, 0 prod. Budget-aware path walking
- [ ] `dead-to-save-data` — core/player.py:73, 1 test ref, 0 prod
- [ ] `dead-can-opportunity-attack` — rules/reactions.py:15, 0 prod callers, дублирует inline check в find_oa_triggers()

## Test Gaps (from audit 2026-03-29)

- [ ] **should** `test-gap-equipment-handlers` — rules/handlers/equipment.py только indirect coverage через test_accessories.py
- [ ] **should** `test-gap-entities-layer` — нет integration test для EntitiesLayer (activation, awareness, combat state, materialization)
- [ ] **should** `test-gap-save-commands` — autosave_all_sessions, delete_save, list_saves без unit-тестов
- [ ] **should** `test-gap-content-routes` — list_catalog_entries, list_schemas, get_schema, list_refs без тестов
- [ ] **should** `test-gap-master-routes` — list_library_templates, fork_world_layer без тестов
- [ ] **could** `test-gap-ws-fastforward` — player wait → time skip → NPC resume не тестируется
- [ ] **could** `test-gap-ws-disconnect-npc` — disconnect during NPC turn + reconnect не тестируется
- [ ] **could** `test-gap-ws-npc-combat-turn` — NPC full multi-action RuleBrain combat turn только indirect
- [ ] **should** `test-gap-action-provider` — rules/action_provider.py без unit-тестов
- [ ] **should** `test-gap-geography-rules` — rules/geography.py без выделенных unit-тестов
- [ ] **should** `test-gap-politics-rules` — rules/politics.py без выделенных unit-тестов
- [ ] **should** `test-gap-settlements-rules` — rules/settlements.py без выделенных unit-тестов
- [x] `test-gap-reactions-rules` — ~~rules/reactions.py без unit-тестов~~ FIXED Sprint 012 phase 4: 20 tests in test_rules_reactions.py
- [ ] **should** `test-gap-handlers-combat` — rules/handlers/combat.py без unit-тестов
- [ ] **should** `test-gap-handlers-items` — rules/handlers/items.py без unit-тестов
- [x] `test-gap-handlers-movement` — ~~rules/handlers/movement.py без unit-тестов~~ FIXED Sprint 012 phase 4: 12 tests in test_handlers_movement.py
- [x] `test-gap-handlers-reactions` — ~~rules/handlers/reactions.py без unit-тестов~~ FIXED Sprint 012 phase 4: 5 tests in test_handlers_reactions.py
- [ ] **should** `test-gap-commands-politics` — service/commands_politics.py 0 test references
- [ ] **should** `test-gap-commands-time` — service/commands_time.py 0 test references
- [ ] **should** `test-gap-fighting-style` — rules/fighting_style.py без выделенных unit-тестов (indirect через test_second_wind, test_create_player)
- [ ] **could** `test-gap-ws-malformed-json` — WS handler не тестируется на невалидный JSON (только unknown message type)

## From audit 2026-04-13 (post Sprint 017)

- [ ] **could** `mutable-turn-budget` — `core/turn_budget.py:18` TurnBudget — `@dataclass` без `frozen=True`. Per-turn value object, мутируется decrement-ом actions. Документировать как stateful или перейти на `replace()`
- [ ] **could** `mutable-resource-pool` — `core/resource.py:16` ResourcePool — `@dataclass` без `frozen=True`. Текущие use-cases мутируют `current_uses`. Документировать или frozen + replace
- [x] `schemas-any-types` — ~~`content_loader/schemas.py` — 5 уз `Any` в валидаторах и `model_post_init`~~ FIXED Sprint 017 phase 5 task 5: replaced with `object` at validator/post_init sites
- [ ] **could** `test-gap-ws-disconnect` — нет теста disconnect во время активного game loop
- [ ] **could** `test-gap-ws-reaction-prompts` — reaction prompt flow по WS не покрыт
- [ ] **could** `test-gap-ws-concurrent-messages` — concurrent message handling по WS не тестируется

## From audit 2026-06-28 (post Sprint 018), triaged

- [x] `any-treasure-items` — ~~`content_loader/monsters.py:207` `treasure_items: list[Any]`, хотя `parse_items()` отдаёт `list[Item]`~~ FIXED в триаже 2026-06-28: аннотация `list[Item]` + импорт `Item`
- [x] `test-gap-encounters-rule` — ~~`rules/encounters.py:8` `is_active_at_time` покрыт только косвенно через integration `test_time_of_day_encounters.py`~~ FIXED в триаже 2026-06-28: `tests/unit/test_encounters.py` (3 теста, truth-table)
- [ ] **could** `item-create-bounds` — `adapters/api/schemas.py:87` поля создания/выдачи предметов (`base_ac`, `max_dex_bonus`, `strength_req`, `ac_bonus`, `reach`) без `Field(ge=, le=)`, в отличие от player HP/AC. Master-only, game-data. Сосед `ability-scores-no-bounds`
- [ ] **could** `any-encounter-entries` — `content_loader/monsters.py:128` `_parse_encounter_entries(entries: Any)` на raw-YAML границе. `object`/`list[object]` строже (часть общего `any-to-object-sweep`)
- [ ] **could** `entities-layer-regrowth` — `layers/entities/layer.py` снова 629 строк после декомпозиции Sprint 005 (`god-class-entities`). Следить за ростом по мере ecology-фич
- [ ] **should** `test-gap-leveling` — `rules/leveling.py` без выделенных unit-тестов (косвенно через level-up тесты)
- [ ] **could** `schema-form-eslint-suppress` — `frontend SchemaForm.tsx:137` eslint-disable-next-line react-hooks/exhaustive-deps (намеренная зависимость эффекта; см. также `event-log-eslint-suppress`, `schema-form-growing`)
