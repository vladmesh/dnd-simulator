# Backlog

Приоритеты: **must** — блокирует следующие уровни или играбельность, **should** — заметно улучшает качество, **could** — nice to have.

Механики и контент с зависимостями — в [ecs-and-content.md](brainstorms/ecs-and-content.md).
Валидация и инварианты — в [world-state-machine.md](brainstorms/world-state-machine.md).
Что сделано — в [ROADMAP.md](ROADMAP.md).
Свежие находки аудита живут в [audit.md](audit.md) до триажа; `/audit-triage` переносит их сюда.

---

## Gameplay

- [x] `monster-spawn` — ~~Система спавна монстров: триггеры (proximity, time, event), таблицы встреч по региону/локации, CR-бюджет~~ FIXED Sprint 018: логова (`core/lair.py`, core-death depletion), региональные encounter-таблицы (region→location fallthrough), time-of-day гейт (day/night). CR-бюджет/авто-скейлинг сознательно отброшен (кенши-стиль). Event-триггер вынесен в `spawn-event-trigger`
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
- [x] `master-panel-creature-inventory` — ~~`CreatureResponse` / `all_entities` query не включают inventory/equipped_weapon; мастер не видит предметы существ~~ RESOLVED: backend поля (`inventory`/`equipped_weapon`) и рендер в edit-диалоге — Sprint 007 (`c5fe924`/`7976363`); inline-показ предметов в read-only observation-списке (`CreatureList`) — Sprint 020 phase 2 task 3
- [x] `master-give-item-ui` — ~~endpoint для give_item есть, кнопки нет~~ FIXED Sprint 007 phase 2: кнопка «Выдать предмет» в карточке существа
- [x] `inspect-as-idle-param` — ~~inspect шёл как `Action(IDLE, {inspect_target})`~~ FIXED Sprint 009 phase 4: клиентская NpcInspectModal из awareness
- [x] `world-builder-js-modules` — ~~world-builder.js 1700+ строк~~ OBSOLETE Sprint 008 phase 4: legacy vanilla JS заменён React SPA

## Engine & Session

- [ ] **should** `travel-action-type` — `go`/travel реализован как хак: `LocationPanel` шлёт `Action(WAIT, {hours: 0, travel_to})`. Нужен отдельный `ActionType.TRAVEL` с хендлером, валидацией маршрута и расчётом времени
- [ ] **should** `npc-instant-say-response` — после `say` тикнуть NPC в локации (1 раунд), чтобы RuleBrain/LlmBrain ответил в том же запросе. Сейчас NPC отвечают только при `advance_time`
- [ ] **could** `list-npcs-iterate-entities` — `list_npcs` итерирует по регионам; NPC в несуществующем регионе выпадает из списка. Итерировать по entities напрямую
- [ ] **could** `periodic-autosave-scheduler` — фоновый asyncio таск в FastAPI lifespan каждые ~2 мин вызывает `autosave_all_sessions()`; cancel на shutdown перед финальным autosave. Дополняет per-action и shutdown автосейв
- [x] **should** `session-disconnect-debounce` — FIXED Sprint 020 phase 3 task 2: grace-period evict — `remove_listener` армит отложенный `threading.Timer` (`_evict_grace_seconds`, default 1.5s, env `DND_EVICT_GRACE_SECONDS`) вместо синхронного stop+evict; `_run_evict_check` перепроверяет player-empty под `_lock` перед stop_round+`_on_empty`; `add_listener`/`stop_round` отменяют таймер (reconnect/deliberate-stop отменяет evict). `has_player_listeners()` ключит «session empty» только на player-listeners (spectators исключены). 4 unit + 1 integration теста. ~~быстрый disconnect+reconnect (React StrictMode remount, сетевой блип) гонит лишний evict: `remove_listener` останавливает раунд и `_on_session_empty` выселяет сессию из реестра. Симптом GAME OVER устранён в post-audit sprint 018 (раунд-луп больше не шлёт `on_game_over` при административном `stop()` — `Round.is_stopped`), но сессия всё равно выселяется и живёт орфаном на reconnect-WS (прогресс может не попасть в реестровый autosave; reload поднимает старый autosave). Простой re-check `has_listeners()` в `_on_session_empty` пробовали и откатили: на module-scoped WS-тестах он сохранял сессию вместо evict→reload-reset, и арена-бой накапливался до `game_over` (5 падений `test_websocket.py` в CI, timing-зависимо). Полноценный фикс — grace-period: при опустошении не выселять сразу, а отложенно (1–2с через `threading.Timer`) перепроверить пустоту и только тогда `stop_round`+evict; reconnect внутри окна отменяет (+ переработать module-scoped арена-фикстуру, чтобы не зависеть от evict-reset). Прод (без StrictMode-двумаунта) почти не задет, поэтому not-must~~

## DevOps / Infra

- [ ] **should** `containerized-stack` — Воспроизводимый контейнерный сетап для подъёма всего стека (фронт + бэк) одной командой. Двойная польза: локально быстро поднять перед E2E и переиспользовать на проде. Сейчас `docker-compose.test.yml` — только `backend` + `integration-tests` (pytest), без фронта и без проброса портов наружу, поэтому браузерный E2E гоняется на хостовых `uvicorn`/`vite`: ловит убийство процесса песочницей при бинде порта и зависит от хостовых Node/uv. План: добавить сервис `frontend` (собранный бандл через `vite build` + `vite preview` или nginx со статикой, не dev-сервер — заодно тестируем прод-бандл), пробросить `8001`/`5173`, оформить профилем `--profile e2e` чтобы не мешать `integration-tests`, и перевести шаг «Start the stack» в скилле `/e2e` на `docker compose --profile e2e up`. Прод-вариант: тот же образ фронта (nginx) + бэкенд, общий базовый compose. Не закрывает E2E-в-CI (нужен отдельно Playwright-в-контейнере + написанные спеки) — это про воспроизводимость стека, не про сами тесты

## Performance

- [ ] **could** `awareness-rebuild-cache` — `build_awareness()` делает 4-5 query к нижним слоям на каждый ход каждого существа (O(N)/раунд), bottleneck при >20 LlmBrain NPC. Решение: WorldSnapshot per (region, tick) для weather/region/settlements/politics + dirty-flag per location для nearby entities. Делать когда начнёт тормозить

## Bugs

- [ ] **should** `dash-actiondef-movement-conflation` — `ActionDef` для `ActionType.DASH` (`core/action_defs.py:218`) рекламирует Dash как «move up to double your speed» и объявляет параметры движения `toward`/`away_from`/`direction` («Same parameters as move»), но реальная механика корректна по D&D и этого не делает: `handle_dash` (`rules/handlers/movement.py:180`) только добавляет `effective_speed(actor)` к `budget.movement_remaining` и эмитит `ENTITY_DASH`, параметры движения игнорирует. `round.py:338` резолвит abstract-move (`toward`/`away_from` → направление) **только** для `MOVE`, не для `DASH` → эти три параметра у Dash мёртвые. RuleBrain делает правильно (Dash добавляет бюджет, отдельный `move` тратит его), но `llm_hint`/`description` вводят LLM в заблуждение: модель пошлёт `dash(toward=...)`, ожидая сдвиг, а персонаж останется на месте. Фикс: убрать `toward`/`away_from`/`direction` из params Dash, переписать `description`/`llm_hint` в духе «добавляет твою скорость к остатку перемещения; двигаться — отдельным `move`». Хендлер не трогать
- [ ] **should** `equip-in-combat-free` — всё семейство экипировки слотов в `core/action_defs.py` (`EQUIP`/`UNEQUIP` оружие, `EQUIP_ARMOR`/`SHIELD`/`HEAD`/`FEET`/`RING` + unequip) объявлено `cost_type=CostType.FREE` **и** без `combat_mode` (= дефолт `CombatMode.ANY`). Доступность в бою задаётся двумя полями `ActionDef`: `combat_mode` (энфорс в `check_action_mode`, `validation.py:90`) и `cost_type` (энфорс/списание в `check_budget` + `ActionDispatcher.dispatch`). Сейчас броню можно надеть в бою бесплатно, хоть каждый раунд, не тратя ни действия, ни хода — по D&D надевание брони это минуты вне боя (лёгкая 1 мин / средняя 5 / тяжёлая 10), в бою недопустимо. Фикс: `EQUIP_ARMOR`/`UNEQUIP_ARMOR` (и accessory-слоты `HEAD`/`FEET`/`RING`) → `combat_mode=PEACEFUL_ONLY`; щит по D&D надевается/снимается за **действие** → `EQUIP_SHIELD`/`UNEQUIP_SHIELD` `cost_type=ACTION` (combat — ок); оружейные `EQUIP`/`UNEQUIP` как `FREE` ближе к правде (object interaction, в D&D 1/ход — лимит опционально). Хендлеры (`rules/handlers/equipment.py`) не трогать, gate в `ActionDef`. Связанная мелочь: `ends_peaceful_turn` стоит у оружейных equip, но не у брони/щита/accessory — рассинхрон поведения мирного хода
- [ ] **could** `take-action-cost-vestigial` — `ActionType.TAKE` (`core/action_defs.py:494`) объявлен `cost_type=CostType.ACTION`, но `combat_mode=PEACEFUL_ONLY`. В мирном ходу бюджета нет (`check_budget` возвращает `None` при `turn_budget is None`, `validation.py:126`), так что ACTION-стоимость никогда не списывается — мёртвая. Либо лут должен быть доступен в бою (тогда ACTION работает, убрать `PEACEFUL_ONLY`), либо снять стоимость как вестигиальную. Сейчас она ничего не значит
- [ ] **could** `peaceful-turn-end-flag-gaps` — рассинхрон `ends_peaceful_turn` у action/bonus-action действий с `combat_mode=ANY` (`core/action_defs.py`): `USE_ITEM` имеет флаг, а `BLESS`/`SECOND_WIND`/`LAY_ON_HANDS` — нет. Если такое действие попадёт в мирный ход (бюджета нет), оно не пометится завершающим, и `run_peaceful_turn` не закроет ход. Низкий риск (все `provider_managed`, дёргаются кнопками UI, брейны вне боя их обычно не выбирают), но флаг проставлен вразнобой. Заодно асимметрия дизайна: `ACTION_SURGE` сделан `COMBAT_ONLY` (вне боя лишнее действие бессмысленно), а родственный `SECOND_WIND` оставлен `ANY` — свериться, намеренно ли
- [ ] **could** `corpse-nearby-actions` — мёртвое существо показывается в Nearby-панели с кнопками Attack/Talk/Inspect (E2E sprint 018 phase 2). Лут идёт через отдельный LootPanel; атака трупа возвращает корректное «уже мертва», так что ничего не ломается — но Attack/Talk на трупе бессмысленны. Скрывать их для мёртвых (или убирать трупы из Nearby, раз есть LootPanel)
- [ ] **should** `encounter-spawned-perceiver` — `EncounterSpawned` события не имеют перцептора в `perception.py` `_DISPATCH`, в логе игрока выводится мусорный фолбэк `Something happened (encounter_spawned)` (E2E post-audit sprint 018; срабатывает на каждый региональный/локационный спавн встречи). Добавить `_perceive_encounter_spawned` (напр. «Рядом что-то зашевелилось») и зарегистрировать в `_DISPATCH`
- [x] `battle-map-configs-not-wired` — ~~`battle_map_configs` из `regions.yaml` не передаётся в `EntitiesLayer` при создании сессии в `game_service.py`. Все combat maps дефолтят в 60×60~~ FIXED Sprint 018 (verified Sprint 019 phase 3): `game_service.py:171-183` строит `battle_map_configs` через `_flatten_region_defaults(load_battle_maps(...))` и передаёт в `EntitiesLayer`
- [x] `player-character-no-attacks` — ~~`POST /api/player/sessions/{id}/character` не принимает `attacks`; персонаж дерётся кулаками (1 урон)~~ FIXED Sprint 013 char-creation (verified Sprint 019 phase 3): `create_player` грузит `starting_equipment` оружие, игрок бьёт через `get_weapon_attack()`. Поле `attacks` в `CreatePlayerRequest` вестигиальное для игрока (raw `attacks` — путь монстра/спавна)
- [x] `look-action-i18n-hardcode` — ~~`_cmd_look` в GameService хардкодит строки «Terrain:»/«Weather:» вместо `_()`~~ OBSOLETE Sprint 019 phase 3: `_cmd_look` удалён в раннем рефакторе, строк «Terrain:»/«Weather:» в `service/` нет (остались только устаревшие msgid в `.po`, помечены obsolete в phase 3 task 1)
- [x] `player-xp-not-persisted` — FIXED Sprint 020 phase 4 task 1: `experience`/`level_up_available` теперь round-trip через современный путь (`to_full_save_data` + `PlayerContent` + `_to_player` + `load_state` re-apply), как `current_hp`. 3 unit-теста в `test_commands_save.py` (same-session re-apply, fresh `parse_player`, autosave→fresh-session dev-evict path). XP и `level_up_available` игрока НЕ переживают save/reload через современный путь (обнаружено Sprint 019 phase 3 task 3 при удалении dead-`to_save_data`). `save_game`/`autosave_session` пишут `{"world": ...}`; `to_full_save_data()` (`core/player.py`) НЕ сериализует `experience`/`level_up_available`, а `PlayerContent`/`_to_player`/`parse_player` их не читают. На reload XP сбрасывается к значению из контента (0). Старый round-trip жил в `to_save_data`+`load_save_data`, но тот завязан только на backward-compat ветку `load_game` для СТАРЫХ сейвов. Фикс: добавить `experience`/`level_up_available` в `to_full_save_data()` и в `PlayerContent`+`_to_player`. **Подтверждено в post-audit E2E (Sprint 019, `e2e-reports/2026-06-29-sprint019-post-audit.md`):** в dev ломает не только save/reload, а live level-up целиком — dev-only WS StrictMode evict→restore (см. `session-disconnect-debounce`) гоняет игрока через этот же save-путь, XP теряется, `player_status` отдаёт `experience=0`, `POST /level-up` → 400. В prod (без StrictMode-двумаунта) проявляется на рестарте/ручном load. Чинить вместе с/после `session-disconnect-debounce`
- [ ] **could** `stale-combat-turn-after-end` — после убийства, завершающего бой, игрок остаётся в своём незакрытом ходу с исчерпанным бюджетом: action bar показывает «Действия: 0» + «Конец хода» вместо мирного бара, а клик по пути-перемещению отклоняется тостом «'wait' недоступно в бою». Нажатие «Конец хода» возвращает мирный бар, перемещение работает. Преэкзистинг, замечен на E2E sprint 020 phase 4. Авто-завершать ход игрока при `combat_ended`, либо возвращать мирный action bar сразу
- [ ] **could** `spawn-role-freetext-enum` — мастерский Spawn Creature диалог (`CreatureForm`) рендерит Role как свободный textbox, но бэкенд `NpcContent.role` — enum (`commoner`/`blacksmith`/`tavern_keeper`/`guard`/`merchant`/`farmer`/`gladiator`). Пустой/произвольный role → HTTP 400 с сырым Pydantic-сообщением прямо в диалоге (E2E sprint 019 phase 1). Сделать Role дропдауном `NpcRole` (и/или маппить ошибку в дружелюбный i18n-тост). Сосед `corpse-nearby-actions` по теме visible-gaps
- [x] **should** `combat-log-i18n-gaps` — ~~при дефолтном `DND_LANGUAGE=ru` боевой лог наполовину английский (E2E post-audit sprint 018). Три причины: (1) дрейф каталога — msgid в коде несут лишний `{oa}` (`perception.py:141,145`), не совпадают с записью в `.po` («You attack {target}{weapon}{roll}{outcome}») → фолбэк на английский; нужен `make messages` + перевод + `make compile-messages`; (2) непереведены строки репутации (`perception.py:505`) и «moved (X ft)»; (3) код-баг: `rules/handlers/movement.py:52,56` возвращают сырой английский `error=...` не обёрнутый в `_()` («Not on the battle map», «Cannot move there — blocked» — последняя ещё и с em-dash) → никогда не локализуется. В основном преэкзистинг (строки спринтов 012/014), но очень заметно~~ RESOLVED Sprint 020 phase 4: причины 1-3 закрыты ещё до спринта (msgid/move/movement-errors уже переведены); phase 4 task 2 добавил недостающие записи каталога (loot/lay-on-hands/action-surge/conditions) и починил утечку faction-id в строке репутации (`faction_name` через `QueryType.FACTION_NAME`); task 3 — полный свип: ~20 `ActionResult.error` в `rules/handlers/` обёрнуты в `_()` + переведены, убран em-dash в `items.py`; phase-4 close E2E поймал последнюю клиентскую половину — `EventLog.tsx` рендерил разделитель раунда («Round N») и сводку движения («{name} moved (X ft)») хардкодом, переведены через `game:round` + новый `game:moved`
- [x] `sneak-attack-faction-check` — ~~SA ally-adjacency считала союзником любое живое существо в 5ft без учёта фракции~~ FIXED Sprint 011/014: ally detection через faction relations
- [x] `flaky-initiative-test` — ~~`test_second_attack_does_not_reroll_initiative` падал рандомно~~ FIXED: AC=30 чтобы атаки всегда мазали, c2 не удаляется из turn_order
- [ ] **could** `flaky-schemaform-ref-select` — `frontend/src/components/master/__tests__/SchemaForm.test.tsx > renders ref field as select with fetched options` флапает в полном `npx vitest run` (ждёт 3 option, видит 1), но зелёный при изоляции файла и на повторе. Похоже на гонку мока fetch ref-опций / async-рендера select. Замечен на Sprint 018 phase 3 (бэкенд-only коммит, влиять не мог). Стабилизировать ожидание опций (`findBy`/`waitFor`) или изолировать fetch-мок между тестами

## Tech Debt (from audits 2026-03-25, updated 2026-03-29)

- [x] `god-class-entities` — ~~EntitiesLayer 1215 строк~~ FIXED Sprint 005: extracted awareness_builder, activation_manager, query_handler, combat_manager, perception
- [x] `god-class-game-service` — ~~GameService 1044 строки, растёт~~ FIXED Sprint 019 phases 2-3: раздроблен 1044 → 357 строк (`WorldBuilderCommands` + `PlayerCommands` mixins, тонкий фасад над `commands_*`). Больше не god-class (verified audit 2026-06-29)
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
- [x] `action-parsing-in-adapter` — ~~Adapter (routes_ws) парсит Action из JSON, должен service layer~~ FIXED Sprint 019 phase 2 task 3: `parse_action`/`ActionParseError` в `service/action_parsing.py`; routes_ws больше не импортирует Action/ActionType из core
- [x] `magic-number-trade` — ~~Magic number 0.08 в politics/layer.py:338~~ FIXED 2026-03-24
- [ ] **should** `thick-adapter-world-state` — routes_master.py:290-330 оркестрирует 7+ layer queries напрямую + assert-based validation (500 при плохих данных). Вынести в GameService.get_world_state()
- [ ] **should** `routes-master-growing` — routes_master.py 560 строк, 34 роута. Разделить content-editing и session-control роуты
- [ ] **should** `test-gap-content-loader` — content_loader/refs, utils, creatures без выделенных unit-тестов (частично покрыты интеграционными)
- [x] `core-brain-imports-rules` — ~~core/brain.py:50,63,141 lazy-imports из rules/~~ FIXED: `RuleBrain` вынесен в `rules/rule_brain.py`, `core/brain.py` больше не импортирует rules (verified audit 2026-06-29). Оставшиеся lazy-import `core/`→`rules/` в `class_features`/`combat`/`monster` — by-design композиция (frozen core делегирует чистую математику в pure rules), не runtime-цикл; принято
- [ ] **should** `test-gap-session` — service/session.py 457 строк, 27 методов без выделенных unit-тестов. Round lifecycle, listener dispatch, resolve_abstract_move непокрыты
- [ ] **should** `god-class-combat-manager` — layers/entities/combat_manager.py 535 строк. Выделить initiative/turn logic от combat state management
- [ ] **could** `entities-layer-imports-content-loader` — layers/entities/layer.py:465,484,490 lazy-imports из content_loader в load_state. Layers → core only, content_loader — peer module
- [ ] **could** `player-status-in-adapter` — routes_player._player_status() маппит Ability enum → строки, presentation logic в адаптере
- [ ] **should** `merchant-provider-in-rules` — MerchantActionProvider в rules/ хранит world-query callback (I/O в pure rules). Перенести в service/ или передавать данные аргументом
- [x] `dice-os-import` — ~~rules/dice.py import os~~ FIXED audit 2026-03-31: set_global_seed() function
- [ ] **should** `base-action-provider-stateful` — BaseActionProvider в rules/ — stateful class с self._types. Сделать standalone функцией или frozen dataclass
- [x] `adapter-imports-core-directly` — ~~routes_player импортирует PlayerCharacter/Ability, routes_master — Query/QueryType напрямую из core~~ FIXED Sprint 019 phase 2 task 3: старые PlayerCharacter/Ability/Query/QueryType импорты убраны при routes_master split (Sprint 016); Action/ActionType вынесены в `service/action_parsing.py` (task 3). Оставшиеся BrainType/FightingStyle — enum-at-boundary в Pydantic-схемах, приняты (аудит 2026-06-28: 0 арх-нарушений, адаптерам можно импортировать enum)
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
- [x] `world-private-method-access` — ~~world._make_query_fn() вызывается из session.py и round.py~~ FIXED Sprint 019 phase 2 task 3: `World.make_query_fn`/`make_emit_fn` теперь public API
- [ ] **could** `event-log-eslint-suppress` — EventLog.tsx eslint-disable-next-line react-hooks/exhaustive-deps
- [ ] **could** `api-client-growing` — apiClient.ts 365 строк, 35+ методов. Разделить по домену
- [ ] **could** `world-overview-growing` — WorldOverview.tsx 331 строка. Split sub-components
- [ ] **should** `class-features-hardcoded` — ClassFeatures/proficiency system hardcoded в Python. Adding new class requires code, not YAML. Vision drift.

## Security (from audits 2026-03-25)

- [ ] **should** `cors-wildcard` — origins теперь конфигурируются через `CORS_ALLOWED_ORIGINS` env + credentials отключаются при `*` (fixed d459e19). Остаётся: `allow_methods=["*"]`, `allow_headers=["*"]` всё ещё хардкод
- [ ] **should** `no-auth` — Нет аутентификации/авторизации, все эндпоинты открыты по session_id. Sprint 020 добавил identity-seam (`service/identity.py` + `get_identity`): заголовки `X-User-Id`/`X-Role` доверяются без проверки, пустая роль → дефолт `ADMIN` (god-mode), любой клиент может назвать любую роль. By-design для keystone-фазы (projection-only, роль не энфорсится), но перед любым не-локальным деплоем нужна реальная auth. Связано с дизайн-заметкой «creator = атрибуция, доступ = будущий M2M»
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
- [x] `dead-refund` — ~~core/turn_budget.py:58 (tested but unused, future budget mechanic)~~ FIXED Sprint 019 phase 3: removed `TurnBudget.refund()` + test
- [x] `dead-check-reactions` — ~~stubbed~~ FIXED Sprint 012: wired into round loop
- [x] `dead-is-daylight` — ~~rules/geography.py:172, tested but unused in prod. Wire into geography layer or remove~~ FIXED Sprint 018 phase 4: wired into `IS_DAYLIGHT` geography query (location→region→latitude→is_daylight) для time-of-day встреч
- [x] `dead-prone-stand-cost` — ~~rules/conditions.py:27, tested but never integrated into movement handler~~ FIXED Sprint 019 phase 3: removed `prone_stand_cost()` + tests
- [x] `dead-reset-resources` — ~~rules/resources.py, 12 test refs, 0 prod~~ FIXED Sprint 015 phase 1: wired into rest handlers
- [x] `dead-walk-path` — ~~rules/movement.py:201, 12 test refs, 0 prod. Budget-aware path walking~~ FIXED Sprint 019 phase 3: removed `walk_path()`; cost-assertion tests re-expressed via prod `step_cost()` (handler uses `compute_reachable`+`step_cost`)
- [x] `dead-to-save-data` — ~~core/player.py:73, 1 test ref, 0 prod~~ FIXED Sprint 019 phase 3: removed `to_save_data()` + tests. NB: surfaced `player-xp-not-persisted` (modern save path via `to_full_save_data` drops experience)
- [x] `dead-can-opportunity-attack` — ~~rules/reactions.py:15, 0 prod callers, дублирует inline check в find_oa_triggers()~~ FIXED Sprint 019 phase 3 (removed earlier in commit 67f057b audit triage); `rules/reactions.py` now only defines `find_oa_triggers`

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

## From audit 2026-06-29 (post Sprint 020), triaged

- [ ] **could** `ws-rate-limit-dup` — `adapters/api/routes_ws.py:101-117, 198-215` константы token-bucket (`20.0 / 20.0 / 5.0`) + цикл budget/refill скопированы между `_run_spectator` и `websocket_game` (spectator-путь Sprint 020 продублировал player-путь). Выделить `TokenBucket`-хелпер (или общий receive-loop). Оба пути корректны, низкий приоритет
