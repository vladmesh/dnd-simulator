# Backlog

Приоритеты: **must** — блокирует следующие уровни или играбельность, **should** — заметно улучшает качество, **could** — nice to have.

Механики и контент с зависимостями — в [ecs-and-content.md](brainstorms/ecs-and-content.md).
Направление симуляционного ядра (время, активность, внутреннее я, детализация) — в [simulation-core.md](brainstorms/simulation-core.md).
Валидация и инварианты — в [world-state-machine.md](brainstorms/world-state-machine.md).
Что сделано — в [ROADMAP.md](ROADMAP.md).
Свежие находки аудита живут в [audit.md](audit.md) до триажа; `/audit-triage` переносит их сюда.

---

## Simulation Core (брейншторм 2026-07-04)

Эпики новой модели из [simulation-core.md](brainstorms/simulation-core.md). Порядок зависимостей: `save-schema` → `anchor-as-property` + `intents` → `trigger-table` → `inner-self` → `detail-ladder` → `quest-system`.

- [x] **must** `save-schema` — CLOSED Sprint 021: единая схема сейва (Pydantic по образцу контента) вместо рукописного формата в нескольких местах. Предусловие всей модели: «мир заморожен на полушаге» требует lossless-сейва (намерения, планы мозгов, триггеры, лог мыслей, зародыши субъектности). Стартовый кусок — «дедуп сериализации» в Sprint 020 phase 3, добивается отдельным спринтом
- [x] **must** `anchor-as-property` — FIXED Sprint 022: `is_anchor` на любом Creature, активация больше не зависит от `PlayerCharacter`
- [x] **must** `intents` — FIXED Sprint 022: строгие сохраняемые wait/sleep/travel intent, встроенные прерывания и границы пробуждения/прибытия
- [ ] **must** `trigger-table` — парные декларативные триггеры `{on, until}` на существе (YAML + ручка ГМ), матчинг при эмиссии событий, активация/гашение dormant↔active, самогашение «моя роль сыграна» как действие мозга. Требует типизированной таксономии событий (фундамент заложен Sprint 020 phase 2). Поглощает `spawn-event-trigger`
- [ ] **should** `brain-gate-decide` — контракт Brain: дешёвый гейт (чистые ифы, «продолжаю намерение?», хоть каждый раунд) + дорогое решение (только границы: завершение, прерывание, триггер, ГМ). Инвариант: LLM никогда не вызывается на 6-секундном пути
- [ ] **should** `llm-turn-plan` — план хода внутри LlmBrain: 1 вызов на ход вместо 3-5, шаги плана со сверкой awareness дешёвой проверкой, перепланирование при сюрпризе. Плюс иерархия командир/исполнитель для сцен: LLM-стратегия на входе, правила разыгрывают раунды, reassess-триггеры (союзник упал, HP < 1/2, враг сдаётся, появился поименованный) поднимают момент до сюжетного решения. Поглощает `combat-reassess`. Движок не меняется — всё внутренности мозга
- [ ] **should** `inner-self` — внутреннее я NPC: цели одним списком (типизированный словарь kill/protect/reach/... исполним RuleBrain + свободные строки только для LLM), типизированные отношения (не путать с reputation), живой alignment (переваривание свидетельствует, правило применяет сдвиг по накоплению с гистерезисом), mood-enum; лог мыслей (только LLM); контракт переваривания «обнови ядро + перепиши дневник»; правиловый близнец суммаризатора (5-8 детерминированных правил — нужен Classic и CI)
- [ ] **should** `detail-ladder` — лестница детализации для поселений: материализация анонимной массы из чисел (детерминированный seed), храповик субъектности (первое взаимодействие → персистентный зародыш, копится с каждой материализацией), событийная запись значимого вверх через emit_fn (смерть/кража/пожар — немедленно; дрейф — сверка при дематериализации). Тот же механизм чинит `lair-death-event`
- [ ] **should** `gm-interlude` — интерлюдия ГМ («прошло три месяца»): fast-forward по wake-точкам и тикам слоёв, по умолчанию совсем без LLM (правиловое переваривание); LLM для ключевых NPC на укрупнённых чекпоинтах — настройка, расширение параметров позже
- [ ] **could** `gm-actives-panel` — панель активных для ГМ: кто, с какого момента, почему, чего ждёт для гашения. Видимые призраки вместо невидимой утечки

## Gameplay

- [x] `monster-spawn` — ~~Система спавна монстров: триггеры (proximity, time, event), таблицы встреч по региону/локации, CR-бюджет~~ FIXED Sprint 018: логова (`core/lair.py`, core-death depletion), региональные encounter-таблицы (region→location fallthrough), time-of-day гейт (day/night). CR-бюджет/авто-скейлинг сознательно отброшен (кенши-стиль). Event-триггер вынесен в `spawn-event-trigger`
- [ ] **must** `quest-system` — Система квестов. НЕ отдельный движок: квест разлагается на типизированные цели + парные триггеры + награды-события ([simulation-core](brainstorms/simulation-core.md)). Планировать после `trigger-table` и `inner-self` (цели), иначе построим параллельную систему под снос. Минимум: fetch/kill/escort. Мир не прогибается: квест может быть уничтожен самим миром
- [x] `key-npcs` — ~~Ключевые NPC (антагонист, компаньон): глубокая память, реакция на мировые события, персональные цели~~ ПОГЛОЩЁН simulation-core: это `always_active` + `inner-self` + `trigger-table`. После эпиков остаётся только контент (прописать самих NPC в YAML)
- [ ] **should** `npc-wandering` — Динамические маршруты NPC между поселениями (сейчас только статичные расписания). Реализуется как travel-намерения у NPC — после `intents`
- [ ] **should** `npc-death-on-war` — NPC гибнут/исчезают при захвате поселения, войне. Реализуется через `detail-ladder` (индивиды поселений) + событийную запись; для именных — событие войны как триггер
- [ ] **should** `divine-sense` — Divine Sense (Paladin): detect celestial/fiend/undead. Требует `CreatureType` enum на Creature, creature_type в каталогах монстров, resource pool (1 + CHA mod / long rest)
- [ ] **should** `divine-smite-scaling` — Divine Smite масштабирование: slot 2 → +3d8, +1d8 vs undead/fiend. Когда будет система уровней и `CreatureType`
- [x] `combat-reassess` — ~~NPC переоценивает стратегию при смене ситуации (союзник упал, новый враг появился)~~ ПОГЛОЩЁН `llm-turn-plan`: reassess-триггеры иерархии командир/исполнитель
- [ ] **should** `versatile-weapons` — Versatile weapon property: переключение одноручный/двуручный хват, разный урон (longsword 1d8/1d10, warhammer 1d8/1d10, quarterstaff 1d6/1d8). WeaponDef.versatile_damage, автовыбор хвата по наличию щита
- [ ] **should** `hit-dice-short-rest` — Hit Dice spending на коротком отдыхе: ResourcePool(hit_dice, max=level, reset_on=LONG_REST), игрок выбирает сколько тратить, за каждую кость roll(class_hit_die)+CON_mod HP. Long rest восстанавливает max(1, level//2) костей (partial reset). Нужен PlayerBrain callback для выбора количества + UI
- [x] `conversation-costs-time` — ~~Каждая реплика разговора тратит 6 секунд игрового времени (частично)~~ ПОГЛОЩЁН `intents`: «каждое действие несёт длительность» — реплика 6с, часть модели времени
- [ ] **should** `loot-drops-monsters` — Общемонстровый дроп: loot-таблицы на шаблонах монстров, корпс-лут с обычных мобов поверх action `take` (Sprint 018 закладывает примитив `Lootable`/`transfer_items`)
- [ ] **should** `theft` — Воровство как отдельный режим доступа к инвентарю: take у живого несогласного владельца, contested Sleight of Hand против Perception, crime/репутация; отдельная `validate_steal` поверх общего `transfer_items`
- [x] `spawn-event-trigger` — ~~Event-триггер спавна (спавн по мировому событию), в связке со спринтом квестов~~ ПОГЛОЩЁН `trigger-table`: спавн — одно из действий сработавшего триггера
- [ ] **could** `spawn-api-xp-value` — master spawn API не принимает `xp_value` для generic-монстров: XP-смоук возможен только на фикстурном мире. E2E sprint 021 close
- [ ] **could** `container-hp-locks` — Сундуки с замком/HP: взлом (lockpicking) и «разбить» контейнер
- [x] **should** `lair-death-event` — закрыт Sprint 023 Phase 2: `ENTITY_DIED` немедленно и идемпотентно обновляет ростер/core/depletion ecology, результат сохраняется и не откатывается при dematerialize
- [ ] **could** `lair-actions` — D&D lair actions на ядре логова
- [ ] **could** `lair-new-leader` — После смерти ядра логово с шансом поднимает нового вожака вместо деплита (динамика мира)
- [ ] **could** `lair-time-of-day` — Активность логова варьируется день/ночь (`active_at: day|night` гейтит материализацию ростера). Переиспользует `TimeOfDay`/`IS_DAYLIGHT`/`is_active_at_time` из Sprint 018 phase 4 (отложено при планировании фазы 4)

## World Simulation

- [ ] **should** `settlement-defenses` — Восстановление defenses поселений со временем
- [ ] **should** `population-economy` — Влияние населения на доход (сейчас только prosperity)
- [ ] **could** `settlement-lifecycle` — Создание/уничтожение поселений динамически
- [ ] **could** `alliance-logic` — Логика альянсов (ALLIANCE статус есть, механики нет)
- [ ] **could** `vassalage` — Вассалитет между нациями
- [ ] **could** `trade-routes` — Торговые маршруты между конкретными поселениями
- [ ] **could** `seasonal-travel` — Сезонные эффекты на путешествия
- [ ] **could** `procedural-gen` — Процедурная генерация регионов/мира
- [ ] **could** `rumor-propagation` — Слухи ползут между поселениями с задержкой: реалистичная доставка информации поверх всеведущих триггеров (simulation-core: «механизм всеведущий, реализм — надстройка»)

## LLM

- [ ] **should** `llm-model-tiering` — Выбор модели по важности NPC и наблюдению: дорогая для реплик в лицо игроку, дешёвая для фоновых и ненаблюдаемых решений. Теперь явная часть модели simulation-core (экономия структурная, не выключением)
- [ ] **could** `llm-narrator` — Интерпретация абстрактных изменений мира в нарративные описания
- [ ] **could** `npc-language` — Динамический выбор языка NPC (из настроек или по языку игрока)

## UX / World Builder

- [x] `dm-player-restructure` — ~~Разделить главную на Player/DM входы~~ FIXED Sprint 008 phase 4-5: master restructure, stepper, world management
- [ ] **could** `quickbar-drag-drop` — Drag-and-drop из инвентаря на action bar quickbar слоты: игрок сам выбирает какие consumables (зелья, свитки, бомбы) закрепить на панели для быстрого доступа. Сейчас consumables в drawer-popup, хватает.
- [ ] **could** `drag-resize-panels` — Drag-and-drop / resizable панели на dashboard
- [ ] **could** `mobile-layout` — Мобильная адаптация dashboard
- [ ] **could** `log-filter-tabs` — Фильтрация лога табами (Все/Бой/Диалоги)
- [x] **should** `attack-buttons-accessible-names` — кнопки Attack/Talk/Inspect в nearby-списке и в inspect-модалке получили target-aware `aria-label` по уникальному `entity.id` (тот же контракт, что у action-bar `TargetDropdown`); SmiteChoice тоже именует цель по id. Закрыто в Sprint 022 phase 4 task 3: EN/RU уникальность подтверждена браузерным E2E (три NPC на рынке → три различимых имени) + компонентные тесты. E2E sprint 021 close
- [ ] **should** `master-panel-creature-inventory` — `CreatureResponse` / `all_entities` query не включают inventory/equipped_weapon; мастер не видит предметы существ. Добавить поля в схему и query
- [x] `master-give-item-ui` — ~~endpoint для give_item есть, кнопки нет~~ FIXED Sprint 007 phase 2: кнопка «Выдать предмет» в карточке существа
- [x] `inspect-as-idle-param` — ~~inspect шёл как `Action(IDLE, {inspect_target})`~~ FIXED Sprint 009 phase 4: клиентская NpcInspectModal из awareness
- [x] `world-builder-js-modules` — ~~world-builder.js 1700+ строк~~ OBSOLETE Sprint 008 phase 4: legacy vanilla JS заменён React SPA

## Engine & Session

- [x] **should** `save-round-concurrency` — FIXED Sprint 022 phase 1: snapshot и раундовые мутации используют единый session-level world gate; load, autosave и eviction согласованы с round lifecycle
- [x] **must** `travel-action-type` — FIXED Sprint 022 phase 3: `ActionType.TRAVEL` движется по рёбрам графа и сохраняет маршрут без телепорта
- [ ] **should** `npc-instant-say-response` — dormant отвечает пассивно, не просыпаясь (simulation-core): после `say` дать существам в локации отреагировать в том же запросе (1 раунд). Сейчас NPC отвечают только при `advance_time`
- [ ] **could** `list-npcs-iterate-entities` — `list_npcs` итерирует по регионам; NPC в несуществующем регионе выпадает из списка. Итерировать по entities напрямую
- [x] **should** `periodic-autosave-scheduler` — FIXED Sprint 021 phase 3 (`DND_AUTOSAVE_SECONDS`, cancel до финального сейва): фоновый asyncio таск в FastAPI lifespan каждые ~2 мин вызывает `autosave_all_sessions()`; cancel на shutdown перед финальным autosave. Дополняет per-action и shutdown автосейв. Повышен could→should: «мир заморожен на полушаге» (simulation-core) требует надёжного автосейва
- [ ] **could** `control-interfaces-donor` — Донор-ветка `sprint/020-control-interfaces` и PR #15: identity/roles, три линзы и admin park реализованы против до-thermo control-plane. При планировании control-interfaces использовать как референс задач и тестов; raw merge невозможен из-за конфликтов с thermo-sweep. Grace-period и spectator уже перенесены отдельно
- [x] **should** `wait-no-fastforward-with-npc` — FIXED Sprint 022 phase 2: intent делает якорь dormant, соседний RuleBrain NPC больше не удерживает сцену, мир быстро доходит до ближайшей wake-точки
- [ ] **could** `saved-session-accumulation` — тест-гигиена закрыта Sprint 021 phase 3 (интеграционный стек чистит saves/ через session fixture); остаётся UX-половина (пагинация/фильтр/TTL в Sessions-вкладке). Master → Sessions грузит ВСЕ сохранённые сессии без пагинации/очистки; за прогоны integration-тестов в общий `saves/` накопилось ~900 сессий (E2E sprint 020 phase 2), вкладка Sessions раздувается, ручной поиск конкретной сессии непрактичен (снимок дерева перевалил за токен-лимит). Две стороны: (1) тест-гигиена — integration-тесты не чистят созданные сейв-сессии в `saves/`; (2) UX/масштаб — в списке нет пагинации/фильтра/TTL. Мин. фикс: чистка `saves/` в teardown интеграционных тестов; долгий — пагинация + фильтр в Sessions-вкладке
- [x] **should** `session-disconnect-debounce`: FIXED 2026-07-10. При уходе последнего player listener `GameSession` **сразу** ставит раунд на паузу (`stop_round`), а откладывает только выселение из реестра: ставится grace-period timer (default 1.5s, `DND_EVICT_GRACE_SECONDS`), reconnect в окне отменяет timer, а вернувшийся игрок перезапускает раунд через `start_round`. Раньше откладывались И stop_round, И evict — из-за этого player-less раунд-луп продолжал крутить ходы NPC в grace-окне (при сетевом блипе игрок молча терял боевые ходы), а поскольку все сессии тянут один процесс-глобальный RNG костей, пересекающиеся «осиротевшие» раунды делали seed-зависимые integration-тесты недетерминированными (`test_player_state_xp::test_rest_status_updated_after_kill` флакал в CI). Spectator listeners не держат сессию живой и не запускают round lifecycle. WS arena tests переведены на fresh session per test, поэтому больше не зависят от evict-reset и не накапливают arena combat до `game_over`.

## DevOps / Infra

- [ ] **could** `saves-dir-env` — каталог сейвов захардкожен (`DEFAULT_SAVES_DIR` в app.py); env-переопределение (напр. `DND_SAVES_DIR`) нужно E2E/тестам для изоляции от рабочего saves/. E2E sprint 021 close
- [ ] **should** `containerized-stack` — Воспроизводимый контейнерный сетап для подъёма всего стека (фронт + бэк) одной командой. Двойная польза: локально быстро поднять перед E2E и переиспользовать на проде. Сейчас `docker-compose.test.yml` — только `backend` + `integration-tests` (pytest), без фронта и без проброса портов наружу, поэтому браузерный E2E гоняется на хостовых `uvicorn`/`vite`: ловит убийство процесса песочницей при бинде порта и зависит от хостовых Node/uv. План: добавить сервис `frontend` (собранный бандл через `vite build` + `vite preview` или nginx со статикой, не dev-сервер — заодно тестируем прод-бандл), пробросить `8001`/`5173`, оформить профилем `--profile e2e` чтобы не мешать `integration-tests`, и перевести шаг «Start the stack» в скилле `/e2e` на `docker compose --profile e2e up`. Прод-вариант: тот же образ фронта (nginx) + бэкенд, общий базовый compose. Не закрывает E2E-в-CI (нужен отдельно Playwright-в-контейнере + написанные спеки) — это про воспроизводимость стека, не про сами тесты
- [ ] **could** `pnpm-shared-store` — Перевести frontend с npm на pnpm: общий content-addressable store делает `node_modules` в свежем git-ворктри почти мгновенным (hardlink из стора) вместо ~1-2 мин `npm ci` на каждый Orca-воркер. Возникло из оркестрации 2026-07-04: `orca.yaml` setup ставит только uv-зависимости, фронт каждый воркер ставит сам. Дешёвый первый шаг без смены менеджера — добавить `cd frontend && npm ci` в `orca.yaml` setup. Полный переход = правки CI, Makefile, docker, доков

## Performance

- [ ] **could** `awareness-rebuild-cache` — `build_awareness()` делает 4-5 query к нижним слоям на каждый ход каждого существа (O(N)/раунд), bottleneck при >20 LlmBrain NPC. Решение: WorldSnapshot per (region, tick) для weather/region/settlements/politics + dirty-flag per location для nearby entities. `llm-turn-plan` снизит частоту пересборок для LLM-мозгов; остаётся актуально для сцен. Делать когда начнёт тормозить

## Bugs

- [ ] **should** `load-combat-round-resume` — загрузка сейва посреди боя: раунд-луп продолжает крутить ходы NPC сразу после load, до реконнекта игрока — UI после реконнекта показывает Round 3/4 вместо сохранённого Round 1; в логах `listener_error` в `WsEventListener.on_turn`. Сейв корректен (`turn_order`/`sides`/`round_number` на месте — sprint 021 phase 2 это починил), проблема в lifecycle: после load раунд должен стоять на паузе до подключения player listener (родня grace-period из `session-disconnect-debounce`). Repro: [e2e phase2-report](sprints/021-save-schema/e2e/phase2-report.md), Finding 1
- [ ] **could** `ui-language-mixing` — в английском UI серверные строки идут по `DND_LANGUAGE=ru`: combat log «Бой начался», «КЗ», «промах», тип NPC «человек» при английском shell UI. Язык клиента и сервера не согласован (сервер берёт env, клиент — свой). Сосед `npc-language`. E2E sprint 021 phase 2
- [ ] **should** `dash-actiondef-movement-conflation` — `ActionDef` для `ActionType.DASH` (`core/action_defs.py`) рекламирует Dash как «move up to double your speed» и объявляет параметры движения `toward`/`away_from`/`direction`, но реальный `handle_dash` (`rules/handlers/movement.py`) только добавляет `effective_speed(actor)` к `budget.movement_remaining` и эмитит `ENTITY_DASH`. `service/session.py` резолвит abstract-move только для `MOVE`, не для `DASH`, поэтому параметры у Dash мёртвые. RuleBrain делает правильно: Dash добавляет бюджет, отдельный `move` тратит его. Фикс: убрать `toward`/`away_from`/`direction` из params Dash, переписать `description`/`llm_hint` в духе «добавляет твою скорость к остатку перемещения; двигаться надо отдельным `move`». Хендлер не трогать
- [ ] **should** `equip-in-combat-free` — Семейство экипировки слотов в `core/action_defs.py` (`EQUIP`/`UNEQUIP`, armor/shield/head/feet/ring) зарегистрировано как `cost_type=FREE` и без `combat_mode`, то есть доступно в бою через дефолт `ANY`. Enforcement сейчас идёт через `check_action_mode` и `check_budget` в `rules/validation.py`, поэтому броню, шлем, обувь и кольцо можно менять в бою бесплатно. Фикс: `EQUIP_ARMOR`/`UNEQUIP_ARMOR` и accessory-слоты сделать `PEACEFUL_ONLY`; `EQUIP_SHIELD`/`UNEQUIP_SHIELD` оставить в бою, но сделать `cost_type=ACTION`; оружейные `EQUIP`/`UNEQUIP` можно оставить `FREE` как object interaction. Синхронизировать `ends_peaceful_turn`: сейчас он стоит у оружия, но не у брони/щита/accessory
- [ ] **could** `take-action-cost-vestigial` — `ActionType.TAKE` (`core/action_defs.py`) объявлен `cost_type=ACTION`, но `combat_mode=PEACEFUL_ONLY`. В мирном ходу бюджета нет, `check_budget` в `rules/validation.py` сразу возвращает `None`, поэтому ACTION-стоимость никогда не списывается. Либо лут должен быть доступен в бою и тогда ACTION начнёт работать, либо стоимость надо снять как вестигиальную
- [ ] **could** `peaceful-turn-end-flag-gaps` — Рассинхрон `ends_peaceful_turn` у action/bonus-action действий с `combat_mode=ANY`: `USE_ITEM` завершает мирный ход, а `BLESS`/`SECOND_WIND`/`LAY_ON_HANDS` нет. Если такое действие попадёт в мирный ход без бюджета, `run_peaceful_turn` может не закрыть ход. Риск низкий, потому что действия `provider_managed` и обычно приходят из UI-кнопок, но флаг стоит вразнобой. Заодно сверить дизайн: `ACTION_SURGE` сделан `COMBAT_ONLY`, а родственный `SECOND_WIND` оставлен `ANY`
- [x] `corpse-nearby-actions` — ~~мёртвое существо показывается в Nearby-панели с кнопками Attack/Talk/Inspect~~ FIXED: добавлен флаг `is_dead` в `NearbyEntity`; в `NpcInspectModal` кнопки действий скрыты для мёртвых, показывается метка «(мёртв)»
- [x] `encounter-spawned-perceiver` — FIXED Sprint 019: `_perceive_encounter_spawned` зарегистрирован в `_DISPATCH`, выдаёт локализованное расплывчатое сообщение без раскрытия roster; RU/EN сценарии покрыты в `test_perception.py` (повторно verified при планировании Sprint 023 Phase 1)
- [x] `battle-map-configs-not-wired` — ~~`battle_map_configs` из `regions.yaml` не передаётся в `EntitiesLayer` при создании сессии в `game_service.py`. Все combat maps дефолтят в 60×60~~ FIXED Sprint 018 (verified Sprint 019 phase 3): `game_service.py:171-183` строит `battle_map_configs` через `_flatten_region_defaults(load_battle_maps(...))` и передаёт в `EntitiesLayer`
- [x] `player-character-no-attacks` — ~~`POST /api/player/sessions/{id}/character` не принимает `attacks`; персонаж дерётся кулаками (1 урон)~~ FIXED Sprint 013 char-creation (verified Sprint 019 phase 3): `create_player` грузит `starting_equipment` оружие, игрок бьёт через `get_weapon_attack()`. Поле `attacks` в `CreatePlayerRequest` вестигиальное для игрока (raw `attacks` — путь монстра/спавна)
- [x] `look-action-i18n-hardcode` — ~~`_cmd_look` в GameService хардкодит строки «Terrain:»/«Weather:» вместо `_()`~~ OBSOLETE Sprint 019 phase 3: `_cmd_look` удалён в раннем рефакторе, строк «Terrain:»/«Weather:» в `service/` нет (остались только устаревшие msgid в `.po`, помечены obsolete в phase 3 task 1)
- [x] `player-xp-not-persisted`: ~~XP и `level_up_available` игрока не переживают save/reload через современный путь~~ FIXED Sprint 020 phase 1 task 1 (сериализационная половина): `experience`/`level_up_available` в `to_full_save_data()` + `PlayerContent`/`_to_player`, round-trip regression-тест. Dev-симптом с WS StrictMode evict→restore закрыт в `session-disconnect-debounce` (транспортная половина)
- [ ] **could** `spawn-role-freetext-enum` — мастерский Spawn Creature диалог (`CreatureForm`) рендерит Role как свободный textbox, но бэкенд `NpcContent.role` — enum (`commoner`/`blacksmith`/`tavern_keeper`/`guard`/`merchant`/`farmer`/`gladiator`). Пустой/произвольный role → HTTP 400 с сырым Pydantic-сообщением прямо в диалоге (E2E sprint 019 phase 1). Сделать Role дропдауном `NpcRole` (и/или маппить ошибку в дружелюбный i18n-тост). Сосед `corpse-nearby-actions` по теме visible-gaps
- [ ] **should** `action-bar-unequip-i18n` — кнопки снятия экипировки в боевом action bar показывают сырые ID и английские описания (E2E sprint 020 phase 1). Оружие: метка «Снять» (RU ✓), но описание «Put away your equipped weapon. You will fight with fists.» (EN ✗). Броня/щит: метки `unequip_armor`/`unequip_shield` — сырые `ActionType`-строки (EN ✗), описания тоже английские. Только weapon-unequip переведён. Фикс: добавить `unequip_armor`/`unequip_shield` в таблицу локализации фронта рядом с `unequip`; перевести описания в `.po`. NB: Sprint 020 phase 3 task 6 сохранил 12 ActionType (реестр сделан бэкенд-internal, коллапс отложен в `equip-action-collapse`) — эти метки не меняются сейчас; при будущем коллапсе синхронизировать оба айтема одним PR
- [ ] **could** `second-wind-zero-heal` — Second Wind показывает «восстанавливаешь 0 ОЗ» когда игрок уже при максимальных HP (E2E sprint 020 phase 1). Сообщение корректно с механической точки зрения (ресурс потрачен, лечение = 0), но выглядит как баг. Подавлять или заменять на «ты уже в полном здравии» когда `healed == 0`.
- [x] `combat-log-i18n-gaps` — ~~при дефолтном `DND_LANGUAGE=ru` боевой лог наполовину английский~~ FIXED: movement-ошибки обёрнуты в `_()` Sprint 019 phase 3; остальные хендлеры (items/equipment/trade/action_surge/loot/combat) + прогон каталога и RU-перевод Sprint 020 phase 1 task 4. Остаточные фронтовые метки — в `action-bar-unequip-i18n`
- [x] `sneak-attack-faction-check` — ~~SA ally-adjacency считала союзником любое живое существо в 5ft без учёта фракции~~ FIXED Sprint 011/014: ally detection через faction relations
- [x] `flaky-initiative-test` — ~~`test_second_attack_does_not_reroll_initiative` падал рандомно~~ FIXED: AC=30 чтобы атаки всегда мазали, c2 не удаляется из turn_order
- [x] **should** `vitest-load-flakes` — mitigated 2026-07-10: `fileParallelism: false` в `frontend/vite.config.ts` (в этом PR) сериализует запуск тестовых файлов, снимая параллельную нагрузку, из-за которой падали 6 тестов в 4 файлах (`CreatureForm.test.tsx` HP current/max, `EntityListEditor.test.tsx` create/edit panel, `CreatureList.test.tsx` brain toggle toast, `LevelUpModal.test.tsx` Paladin fighting styles). Корневая причина — изоляция тестов под нагрузкой (waitFor/timeout при параллельном исполнении тяжёлых 7-17с файлов); правильный долгий фикс — ревизия изоляции тяжёлых файлов (а не только сериализация всего прогона). Та же семья, что `flaky-schemaform-ref-select`
- [ ] **could** `tsc-build-test-looseness` — `tsc -b` даёт 28 ошибок в тест/конфиг-файлах фронта, при зелёном CI-гейте `tsc --noEmit` (baseline orca-воркера 2026-07-04). Не гейтится, но это реальная типовая расхлябанность тестов. Подтянуть или задокументировать, почему гейт именно `--noEmit`
- [ ] **could** `flaky-schemaform-ref-select` — `frontend/src/components/master/__tests__/SchemaForm.test.tsx > renders ref field as select with fetched options` флапает в полном `npx vitest run` (ждёт 3 option, видит 1), но зелёный при изоляции файла и на повторе. Похоже на гонку мока fetch ref-опций / async-рендера select. Замечен на Sprint 018 phase 3 (бэкенд-only коммит, влиять не мог). Стабилизировать ожидание опций (`findBy`/`waitFor`) или изолировать fetch-мок между тестами

## Tech Debt (from audits 2026-03-25, updated 2026-03-29)

- [ ] **could** `equip-action-collapse` — схлопнуть 12 экипировочных ActionType (`equip`/`unequip`/`equip_armor`/… ×6 слотов) в один `EQUIP`/`UNEQUIP` со `slot`-параметром. Sprint 020 phase 3 task 6 сделал бэкенд-часть реестра (модель `Creature.equipped: dict[EquipmentSlot, Item]` + compat-свойства, фабричные хендлеры, `action_defs` циклом), но 12 ActionType и wire-контракт СОХРАНЕНЫ — полный коллапс отложен, т.к. это скоординированное изменение **бэк + фронт + wire + i18n**: фронт (`InventoryPanel.tsx` per-slot дифф `equip_armor`/`unequip_shield`/…, `actionCategories.ts`), wire-схема действий, `.po` описания. Делать одним PR через все три поверхности. Разблокирует `action-bar-unequip-i18n` (те же ActionType-метки)
- [x] `god-class-entities` — ~~EntitiesLayer 1215 строк~~ FIXED Sprint 005: extracted awareness_builder, activation_manager, query_handler, combat_manager, perception
- [x] `god-class-game-service` — ~~GameService 1044 строки, растёт~~ FIXED Sprint 019 phases 2-3: раздроблен 1044 → 357 строк (`WorldBuilderCommands` + `PlayerCommands` mixins, тонкий фасад над `commands_*`). Больше не god-class (verified audit 2026-06-29)
- [x] `god-class-politics` — ~~PoliticsLayer 609 строк~~ FIXED Sprint 014 phase 0: split into diplomacy.py, warfare.py, economy.py submodules
- [x] `test-gaps-critical` — ~~rules/action_handlers.py без unit-тестов~~ FIXED Sprint 005: action_provider, awareness_builder, brain_factory, world isolation tests
- [x] `test-gaps` — ~~Нет тестов: action_provider, awareness, world, brain_factory~~ FIXED Sprint 005 (commands_*, session, store remain)
- [ ] **should** `llm-client-type-ignores` — `# type: ignore[arg-type]` в llm/client.py на вызовах OpenAI SDK
- [x] `any-in-query-answer` — ~~Answer.value: Any~~ FIXED Sprint 005: Answer.value → object
- [x] `action-handlers-growing` — ~~action_handlers.py 605 строк~~ FIXED Sprint 005: split into rules/handlers/ (combat, equipment, items, movement, trade)
- [x] `content-loader-growing` — ~~content_loader.py 815 строк~~ FIXED Sprint 005: split into content_loader/ (world, creatures, items, monsters)
- [x] `long-methods` — ~~query() 125, resolve_attack 186~~ FIXED Sprint 005: query→query_handler, resolve_attack 186→62 lines
- [ ] **should** `test-gap-actions` — rules/actions.py (90 строк) без выделенных unit-тестов
- [ ] **should** `test-gap-weapons` — rules/weapons.py (48 строк) частично покрыт через test_combat/test_proficiency, но нет выделенных тестов
- [x] `session-serialization-duplication` — ~~on_turn, on_action, on_round_end повторяют сериализацию~~ FIXED Sprint 012 phase 4: shared event builder extracted
- [ ] **could** `npc-behaviors-yaml-loading` — layers/entities/npc_behaviors.py загружает YAML на уровне модуля с global state mutation. Перенести в content_loader
- [x] `action-parsing-in-adapter` — ~~Adapter (routes_ws) парсит Action из JSON, должен service layer~~ FIXED Sprint 019 phase 2 task 3: `parse_action`/`ActionParseError` в `service/action_parsing.py`; routes_ws больше не импортирует Action/ActionType из core
- [x] `magic-number-trade` — ~~Magic number 0.08 в politics/layer.py:338~~ FIXED 2026-03-24
- [ ] **should** `thick-adapter-world-state` — routes_master.py оркестрирует 7+ layer queries напрямую. Assert-половина закрыта Sprint 019 phase 1 (fail-fast вместо assert); вынос оркестрации в GameService.get_world_state() остаётся
- [ ] **should** `routes-master-growing` — routes_master.py 560 строк, 34 роута. Разделить content-editing и session-control роуты
- [ ] **should** `test-gap-content-loader` — content_loader/refs, utils, creatures без выделенных unit-тестов (частично покрыты интеграционными)
- [x] `core-brain-imports-rules` — ~~core/brain.py:50,63,141 lazy-imports из rules/~~ FIXED: `RuleBrain` вынесен в `rules/rule_brain.py`, `core/brain.py` больше не импортирует rules (verified audit 2026-06-29). Оставшиеся lazy-import `core/`→`rules/` в `class_features`/`combat`/`monster` — by-design композиция (frozen core делегирует чистую математику в pure rules), не runtime-цикл; принято
- [ ] **should** `test-gap-session` — service/session.py 27+ методов без полного unit-покрытия. Round lifecycle и listener dispatch частично закрыты characterization-сеткой Sprint 019 phase 1; resolve_abstract_move остаётся
- [x] `god-class-combat-manager` — ~~layers/entities/combat_manager.py 481 строка. Выделить initiative/turn logic от combat state management~~ FIXED Sprint 020 phase 3: `combat_manager.py` 481→241, `combat_resolution.py` выделен, `make_relation_fn` вынесен в `rules/reputation.py`. Оставшийся файл — lifecycle/state facade, не god-class
- [ ] **could** `entities-layer-imports-content-loader` — layers/entities/layer.py:465,484,490 lazy-imports из content_loader в load_state. Layers → core only, content_loader — peer module
- [ ] **could** `player-status-in-adapter` — routes_player._player_status() маппит Ability enum → строки, presentation logic в адаптере. Частично закрыто Sprint 020 phase 2 task 4 (единый источник `player_status` → `PlayerStatusData`); остаток — enum-маппинг в адаптере
- [x] `merchant-provider-in-rules` — ~~MerchantActionProvider в rules/ хранит world-query callback (I/O в pure rules)~~ FIXED Sprint 020 phase 1 task 5: merchant/loot провайдеры без world-query в rules
- [x] `dice-os-import` — ~~rules/dice.py import os~~ FIXED audit 2026-03-31: set_global_seed() function
- [x] `base-action-provider-stateful` — ~~BaseActionProvider в rules/ — stateful class с self._types~~ FIXED Sprint 020 phase 1 task 5: standalone-функция / frozen dataclass
- [x] `adapter-imports-core-directly` — ~~routes_player импортирует PlayerCharacter/Ability, routes_master — Query/QueryType напрямую из core~~ FIXED Sprint 019 phase 2 task 3: старые PlayerCharacter/Ability/Query/QueryType импорты убраны при routes_master split (Sprint 016); Action/ActionType вынесены в `service/action_parsing.py` (task 3). Оставшиеся BrainType/FightingStyle — enum-at-boundary в Pydantic-схемах, приняты (аудит 2026-06-28: 0 арх-нарушений, адаптерам можно импортировать enum)
- [ ] **should** `any-to-object-sweep` — dict[str, Any] вместо dict[str, object] (core/models, layers, llm, adapters). Частично закрыт Sprint 020 phase 2 (typed query contract, ~28 cast-сайтов); остатки в llm/ и adapters/
- [x] **should** `layer-rng-threading` — FIXED Sprint 021 phase 1: encounter rolls, squad roam movement и retreat selection в `layers/entities/encounters.py`, `layers/ecology/movement.py`, `layers/ecology/squad_combat.py` используют process-global `random`. Прокинуть RNG явно или через единый seeded источник, чтобы world simulation была воспроизводима для `save-schema` / `gm-interlude` ([simulation-core](brainstorms/simulation-core.md))
- [x] `entity-type-enum` — ~~"player"/"npc"/"creature" строковые сравнения в 5+ файлах~~ FIXED Sprint 016 (`EntityKind(StrEnum)`) + добивка на границах Sprint 020 phase 2 task 3
- [x] `brain-type-enum` — ~~ai_type == "rule_based" строковые сравнения~~ FIXED Sprint 016 (`BrainType(StrEnum)`) + границы Sprint 020 phase 2
- [x] `layer-source-string-cmp` — ~~game_service.py source == "library" вместо enum~~ FIXED Sprint 020 phase 2 task 3: `LayerSource`
- [x] `long-func-run-combat-turn` — ~~round.py run_combat_turn 132 строки~~ FIXED Sprint 012 phase 4: extracted _prepare_combat_turn() + _build_combat_awareness()
- [x] `long-func-choose-combat-action` — ~~core/brain.py _choose_combat_action 114 строк~~ FIXED Sprint 014 phase 0: decomposed into _CombatContext + per-action helpers
- [ ] **should** `round-growing` — round.py 548 строк после Sprint 020 phase 3. Частично закрыто: awareness → `AwarenessBuilder`, `resolve_abstract_move` → `rules/movement`, одна активация за loop. Слияние combat/peaceful отменено по [simulation-core](brainstorms/simulation-core.md): peaceful будет переписан через `intents`
- [ ] **could** `action-defs-growing` — core/action_defs.py 545 строк. Sprint 020 phase 3 сделал backend equipment registry, но 12 equip/unequip ActionType и wire-контракт сохранены; полный `equip-action-collapse` отдельно. Data-driven YAML формат — отдельно
- [ ] **should** `perception-fail-fast` — layers/entities/perception.py 54x .get() с silent defaults. Маскирует отсутствие данных в событиях
- [ ] **could** `test-bare-status-codes` — test_api.py, test_trade_ws.py используют bare 200/404 вместо HTTPStatus
- [ ] **should** `long-func-start-round` — service/session.py start_round 103 строки. Extract closures into named methods
- [x] `perception-dispatch-chain` — ~~perception.py if-elif chain~~ FIXED Sprint 012 phase 4: dict[EventType, handler] dispatch
- [x] `activation-manager-growing` — ~~activation_manager.py 626 строк. Вынести EncounterRoller + materialization~~ FIXED Sprint 020 phase 3: 626→150, encounters/materialization вынесены. Оставшаяся activation-логика сознательно только изолирована, дальнейшая замена идёт через `intents`/`trigger-table`/`anchor-as-property`
- [ ] **could** `deep-nesting-diplomacy` — politics/layer.py _process_diplomacy 7 уровней вложенности
- [x] **should** `silent-failure-autosave` — FIXED Sprint 021 phase 3 (+ гвард на evict-после-DELETE): 3x contextlib.suppress(Exception) вокруг autosave. Логировать ошибки, не глушить
- [x] `silent-failure-awareness` — ~~awareness_builder.py 6x broad except Exception~~ FIXED Sprint 012 phase 4: narrowed to KeyError/LookupError
- [x] `silent-failure-movement` — ~~handle_wait except ValueError: pass~~ FIXED Sprint 020 phase 1 task 2: недостижимый/несуществующий travel-таргет → `ActionResult(success=False)`
- [x] **should** `action-error-kills-round-loop` — FIXED Sprint 023 phase 4: required/type validation возвращает failed `ActionResult`, ожидаемые handler-отказы используют узкий `ActionRejectedError`, live WS regression подтверждает следующий играбельный ход; programming errors не поглощаются.
- [x] `schema-form-growing` — ~~frontend SchemaForm.tsx 488 строк, 30+ nested helpers~~ FIXED Sprint 020 phase 4: `FieldShell`, `schemaResolve.ts`, `localizedCodec.ts`, один `buildDefaults`; `SchemaForm.tsx` 373 строки
- [ ] **should** `llm-imports-layer-models` — llm/brain.py и llm/summarizer.py импортируют из layers.entities.models (Npc, NpcMemory). llm не должен зависеть от layers
- [ ] **should** `round-imports-entities-layer-v2` — round.py:31 напрямую импортирует EntitiesLayer (sprint 012 re-introduced coupling). Взаимодействовать через World/Layer interface
- [ ] **should** `mutable-dataclass-models` — Region, Nation, Settlement, Leader — @dataclass без frozen=True. Аудит: мутируются ли in-place или можно frozen
- [ ] **should** `proficiency-hardcoded-weapons` — rules/proficiency.py:33-34 хардкоженные строки оружия ("rapier", "shortsword"). Использовать enum или catalog ref
- [ ] **should** `perception-hardcoded-weapons` — perception.py:29-31 дублирует названия оружия из YAML каталогов
- [ ] **should** `content-loader-fail-fast` — 31 .get() с дефолтами в content_loader/. Некоторые оправданы (YAML boundary), но bm_data.get("width", 60) молча дефолтит размер карты
- [ ] **should** `dict-str-object-overuse` — dict[str, object] вместо TypedDict/dataclass в query_handler, game_service, combat_manager, schemas. Частично закрыт Sprint 020 phase 2 task 1 (query payload dataclasses); остатки в game_service/schemas
- [x] `world-private-method-access` — ~~world._make_query_fn() вызывается из session.py и round.py~~ FIXED Sprint 019 phase 2 task 3: `World.make_query_fn`/`make_emit_fn` теперь public API
- [ ] **could** `event-log-eslint-suppress` — EventLog.tsx eslint-disable-next-line react-hooks/exhaustive-deps
- [ ] **could** `api-client-growing` — apiClient.ts 365 строк, 35+ методов. Разделить по домену
- [x] `world-overview-growing` — ~~WorldOverview.tsx 331 строка~~ FIXED Sprint 020 phase 4: generic `EditableStatsTable<T>` + typed rows, `WorldOverview.tsx` стал тонким composition layer
- [ ] **should** `class-features-hardcoded` — ClassFeatures/proficiency system hardcoded в Python. Adding new class requires code, not YAML. Vision drift ([ecs-and-content](brainstorms/ecs-and-content.md)); упрётся в рост при заклинаниях (Level 3)

## Security (from audits 2026-03-25)

- [ ] **should** `cors-wildcard` — origins теперь конфигурируются через `CORS_ALLOWED_ORIGINS` env + credentials отключаются при `*` (fixed d459e19). Остаётся: `allow_methods=["*"]`, `allow_headers=["*"]` всё ещё хардкод
- [ ] **should** `no-auth` — Нет аутентификации/авторизации, все эндпоинты открыты по session_id
- [ ] **should** `no-csrf` — Нет CSRF protection на state-changing HTTP; с CORS=* browser-based CSRF тривиален
- [ ] **could** `ws-max-size` — Нет лимита на размер WebSocket сообщений
- [ ] **could** `ws-origin-optional` — WS origin validation через env var, по умолчанию выключена; case-sensitive
- [ ] **could** `frontend-error-endpoint` — POST /api/frontend-error принимает произвольный JSON без валидации
- [ ] **could** `rest-rate-limiting` — Нет rate limiting на REST эндпоинтах (WS имеет token bucket)
- [ ] **could** `action-params-validation` — Action params из клиента без schema validation
- [ ] **could** `llm-prompt-injection` — Player say() текст попадает в NPC memory → system prompt. NB: `inner-self` расширит поверхность (лог мыслей, цели) — учесть при проектировании
- [ ] **could** `ws-stall-vector` — routes_ws.py future.result(timeout=30) блокирует Round thread если клиент не читает
- [ ] **could** `layer-file-max-length` — UpdateLayerFileRequest.content без max_length — произвольный YAML на диск
- [ ] **could** `llm-prompt-no-separation` — NPC memory, entity descriptions интерполируются в system prompt без разделительной границы
- [ ] **could** `ability-scores-no-bounds` — ability_scores и attacks принимают произвольные значения без bounds validation
- [ ] **could** `world-name-path-traversal` — game_service.py:81 world_name from request used in path construction without regex guard at call site
- [ ] **could** `item-create-bounds` — `adapters/api/schemas.py:87` поля создания/выдачи предметов (`base_ac`, `max_dex_bonus`, `strength_req`, `ac_bonus`, `reach`) без `Field(ge=, le=)`, в отличие от player HP/AC. Master-only, game-data. Сосед `ability-scores-no-bounds`

## Dead Code (from audit 2026-03-25)

- [x] `dead-move-away-from-target` — ~~core/brain.py, zero callers~~ FIXED audit 2026-03-31: removed
- [x] `dead-auto-fail-saves` — ~~rules/conditions.py:32~~ FIXED audit 2026-03-31: removed
- [x] `dead-refund` — ~~core/turn_budget.py:58 (tested but unused, future budget mechanic)~~ FIXED Sprint 019 phase 3: removed `TurnBudget.refund()` + test
- [x] `dead-check-reactions` — ~~stubbed~~ FIXED Sprint 012: wired into round loop
- [x] `dead-is-daylight` — ~~rules/geography.py:172, tested but unused in prod. Wire into geography layer or remove~~ FIXED Sprint 018 phase 4: wired into `IS_DAYLIGHT` geography query (location→region→latitude→is_daylight) для time-of-day встреч
- [x] `dead-prone-stand-cost` — ~~rules/conditions.py:27, tested but never integrated into movement handler~~ FIXED Sprint 019 phase 3: removed `prone_stand_cost()` + tests
- [x] `dead-reset-resources` — ~~rules/resources.py, 12 test refs, 0 prod~~ FIXED Sprint 015 phase 1: wired into rest handlers
- [x] `dead-walk-path` — ~~rules/movement.py:201, 12 test refs, 0 prod. Budget-aware path walking~~ FIXED Sprint 019 phase 3: removed `walk_path()`; cost-assertion tests re-expressed via prod `step_cost()` (handler uses `compute_reachable`+`step_cost`)
- [x] `dead-to-save-data` — ~~core/player.py:73, 1 test ref, 0 prod~~ FIXED Sprint 019 phase 3: removed `to_save_data()` + tests. NB: surfaced `player-xp-not-persisted` (закрыт Sprint 020 phase 1)
- [x] `dead-can-opportunity-attack` — ~~rules/reactions.py:15, 0 prod callers, дублирует inline check в find_oa_triggers()~~ FIXED Sprint 019 phase 3 (removed earlier in commit 67f057b audit triage); `rules/reactions.py` now only defines `find_oa_triggers`

## Test Gaps (from audit 2026-03-29)

- [ ] **should** `test-gap-equipment-handlers` — rules/handlers/equipment.py только indirect coverage через test_accessories.py. NB: Sprint 020 phase 3 (реестр экипировки) перепишет хендлеры — тесты писать на новую форму
- [ ] **should** `test-gap-entities-layer` — нет integration test для EntitiesLayer (activation, awareness, combat state, materialization)
- [ ] **should** `test-gap-save-commands` — autosave_all_sessions, delete_save, list_saves без unit-тестов (commands_save round-trip частично закрыт Sprint 019 phase 1)
- [ ] **should** `test-gap-content-routes` — list_catalog_entries, list_schemas, get_schema, list_refs без тестов
- [ ] **should** `test-gap-master-routes` — list_library_templates, fork_world_layer без тестов
- [x] **could** `test-gap-ws-fastforward` — FIXED Sprint 022 phase 2: реальный websocket path проверяет wait → fast-forward → возврат хода без NPC flood
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
- [x] **could** `test-gap-world-rng-determinism` — FIXED Sprint 021 phase 1 (`test_world_seed.py`): нет тестов, фиксирующих seeded deterministic behavior для encounter rolls, squad roam movement и squad retreat selection. Добавить вместе с `layer-rng-threading`

## From audit 2026-04-13 (post Sprint 017)

- [ ] **could** `mutable-turn-budget` — `core/turn_budget.py:18` TurnBudget — `@dataclass` без `frozen=True`. Per-turn value object, мутируется decrement-ом actions. Документировать как stateful или перейти на `replace()`
- [ ] **could** `mutable-resource-pool` — `core/resource.py:16` ResourcePool — `@dataclass` без `frozen=True`. Текущие use-cases мутируют `current_uses`. Документировать или frozen + replace
- [x] `schemas-any-types` — ~~`content_loader/schemas.py` — 5 уз `Any` в валидаторах и `model_post_init`~~ FIXED Sprint 017 phase 5 task 5: replaced with `object` at validator/post_init sites
- [ ] **could** `test-gap-ws-disconnect` — нет теста disconnect во время активного game loop
- [ ] **could** `test-gap-ws-reaction-prompts` — reaction prompt flow по WS не покрыт
- [ ] **could** `test-gap-ws-concurrent-messages` — concurrent message handling по WS не тестируется
- [ ] **could** `test-gap-shutdown-autosave-failure` — поведение shutdown-пути, когда финальный `autosave_all_sessions()` сам бросает, не запинено (audit 2026-07-10)
- [ ] **could** `player-save-bridge-removal` — `player_to_save_data()` остался как compatibility-subset для `parse_player`; когда парсинг игрока переедет целиком на save-модели — убрать мост (audit 2026-07-10)

## From audit 2026-06-28 (post Sprint 018), triaged

- [x] `any-treasure-items` — ~~`content_loader/monsters.py:207` `treasure_items: list[Any]`, хотя `parse_items()` отдаёт `list[Item]`~~ FIXED в триаже 2026-06-28: аннотация `list[Item]` + импорт `Item`
- [x] `test-gap-encounters-rule` — ~~`rules/encounters.py:8` `is_active_at_time` покрыт только косвенно через integration `test_time_of_day_encounters.py`~~ FIXED в триаже 2026-06-28: `tests/unit/test_encounters.py` (3 теста, truth-table)
- [ ] **could** `any-encounter-entries` — `content_loader/monsters.py:128` `_parse_encounter_entries(entries: Any)` на raw-YAML границе. `object`/`list[object]` строже (часть общего `any-to-object-sweep`)
- [ ] **could** `entities-layer-regrowth` — `layers/entities/layer.py` 629→552 после Sprint 020 phase 3 (`entity_serialization.py` выделен), но слой снова выше 400 строк после декомпозиции Sprint 005. Следить за ростом по мере ecology/session-фич; следующий разрез — load/restore helpers, entity CRUD helpers, query facade
- [ ] **should** `test-gap-leveling` — `rules/leveling.py` без выделенных unit-тестов (косвенно через level-up тесты)
- [ ] **could** `schema-form-eslint-suppress` — `frontend SchemaForm.tsx:137` eslint-disable-next-line react-hooks/exhaustive-deps (намеренная зависимость эффекта; см. также `event-log-eslint-suppress`, `schema-form-growing`)
