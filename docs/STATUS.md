# Project Status

Текущее состояние проекта. Один файл — быстрый ответ на "где мы сейчас".

**Last updated:** 2026-07-16
**Position:** Sprint 024 (playtest-quick-wins) в планировании: быстрые UX-фиксы из живой партии 2026-07-15, план готов.
**Next:** Генерация задач Phase 1.
**Blockers:** Нет.

## Current Sprint

**Sprint:** 024-playtest-quick-wins
**Goal:** Быстрые UX-победы из живой партии 2026-07-15 — боевое движение и чистота лога/боевого UI, полировка торговли и i18n снаряжения, панель свойств предметов
**Started:** 2026-07-16
**Phase:** 1 — Читаемость и тактика боя (task 3 done, все задачи фазы 1 готовы) — 2026-07-16

Task 1 (единый учёт бюджета движения) done: `MOVE`→FREE, `handle_move` списывает `moved_ft` атомарно, `check_movement_available` держит «0 движения → MOVE недоступен», внятная отбивка `move_to`, остаток движения + достижимость целей в LLM-промпт. Премиса `combat-move-budget-not-consumed` оказалась неверной (бюджет уже списывал диспетчер) — таск переформулирован в унификацию раздвоенного учёта. `make check` зелёный (backend 2550, frontend 289).

Task 2 (чистота боевого лога) done: on_action вынесен в `build_action_result` (transport_payloads), `error`/`budget` гейтятся на игрока — чужие технические отказы (заблокированный ход волка) больше не текут в лог игрока. В awareness `make_relation_fn` строится один раз на ребилд (было ~2N на пару): hostility вынесен в приватный `_hostility_from_relation(relation_fn)`, публичная сигнатура `check_faction_hostility` сохранена. `faction_hostility_check` INFO→DEBUG. `make check` зелёный (backend 2554, frontend 289).

Task 3 (Second Wind без «0 ОЗ») done: `_perceive_second_wind` получил ветку `healed == 0` (self/other) с сообщением о полном здоровье вместо «regaining 0 HP»; ненулевой путь не тронут. Новые EN-строки + RU-перевод, `.pot`/`.mo` перекомпилированы. `make check` зелёный (backend 2558, frontend 289). Фаза 1 полностью закрыта по задачам.

### Phases

1. Читаемость и тактика боя (movement budget, enemy-error log gate, faction-log spam, second-wind zero heal)
2. Полировка торговли и экипировки (catalog prices, equip/unequip i18n)
3. Панель свойств предметов (item-properties-ui)

`hide-world-travel-in-combat` снят с фазы 1: буквальный гейт уже на месте (GameScreen right-column swap), остаток — десинк режима (`combat-status-single-source`, вне скоупа).

## Recent activity (non-sprint)

- 2026-07-10 — Sprint 021 save-schema закрыт: unit 2429, integration 160, два E2E-прогона, audit triaged (свежий риск `save-round-concurrency` в бэклоге), PR в main.

- 2026-07-10: перенесены ценные фичи из `sprint/020-control-interfaces`: disconnect grace-period закрыл `session-disconnect-debounce`, spectator-listener добавил read-only WS `?spectate=true` и live-вкладку в master session view.
- 2026-07-10 — Sprint 020 thermo-sweep закрыт: integration 154 passed, post-audit E2E smoke 5/5, audit triaged, PR opened to main.
- 2026-07-04 — брейншторм [simulation-core](brainstorms/simulation-core.md): консенсус-модель времени/активности/внутреннего я/лестницы детализации. VISION.md переписан, BACKLOG реструктурирован (секция Simulation Core, поглощённые/переформулированные айтемы, чекбоксы фаз 1-2 спринта 020), ROADMAP Planned обновлён, указатели-актуализации в старых брейнштормах.
- 2026-06-20 — CORS origins сделаны конфигурируемыми (`CORS_ALLOWED_ORIGINS`); Docker base-image запинен по digest.
- 2026-04-24 — post-017 cleanup: `perceive()` без вшитых ран в имя, REST `player_status` отдаёт equipped + inventory, убрана Cancel-кнопка в LevelUpModal.

## Sprint History

| Sprint | Goal | Started | Completed |
|--------|------|---------|-----------|
| 023-trigger-table | Парные триггеры `{on, until}` на типизированной таксономии событий; событийный write-back смертей логова | 2026-07-12 | 2026-07-14 |
| 022-intents-travel | Player-agnostic якоря и сохраняемые wait/sleep/travel intent; travel по рёбрам; согласованный lifecycle save/load/autosave | 2026-07-10 | 2026-07-12 |
| 021-save-schema | Версионированная Pydantic-схема сейва (schema_version=1, RNG в сейве, combat sides), воспроизводимость мира от DND_WORLD_SEED, периодический автосейв | 2026-07-10 | 2026-07-10 |
| 020-thermo-sweep | Закрыть структурный долг из термоядерного ревью: корректность + чистота rules, типизация границ, backend/frontend decomposition, сверка с simulation-core | 2026-06-30 | 2026-07-10 |
| 019-control-plane-prep | Отвердить control-plane под разрез на роли: GameService 1044→357 (миксины WorldBuilderCommands/PlayerCommands), тест-сетка на session, развязка core/adapter (action_parsing seam, public World query API), видимые дырки (combat-log i18n, encounter-перцептор, труп-кнопки) | 2026-06-28 | 2026-06-29 |
| 018-lairs-encounters-loot | Логова (active→depleted), лут/контейнеры (`take`, `transfer_items`), региональные таблицы встреч, время суток; закрыт `monster-spawn` | 2026-06-28 | 2026-06-28 |
| 017-xp-leveling | XP-by-CR и система уровней, level-up модалка; Paladin L1→L2 fix, Fighter Action Surge, Rogue L2 HP | 2026-04-13 | 2026-04-13 |
| 016-tech-sweep | Fix E2E/backlog bugs, resolve architecture violations, add enums + harden fail-fast | 2026-04-12 | 2026-04-13 |
| 015-paladin-spell-slots | Paladin L1-L2: spell slots as ResourcePool, Divine Smite, Lay on Hands, multi-damage weapons, target scope enums | 2026-04-10 | 2026-04-12 |
| 014-faction-reputation | Combat sides from faction relations, personal reputation, auto-hostility, friendly OA fix | 2026-04-09 | 2026-04-10 |
| 013-char-creation | Character creation overhaul — point buy, derived HP/AC, starting equipment, Fighter/Rogue only | 2026-04-01 | 2026-04-09 |
| 012-reactions-oa | D&D 5e reactions — opportunity attacks, Disengage, Brain.choose_reaction, reaction prompt UI | 2026-03-30 | 2026-03-31 |
| 011-class-mechanics-l1 | Structured dice, weapon/armor properties, GWF, Cunning Action choice, SA faction, SRD catalogs | 2026-03-28 | 2026-03-30 |
| 010-e2e-polish | UX-баги из e2e sprint 009 + ActionBar decomposition | 2026-03-28 | 2026-03-28 |
| 009-ui-layout | Dashboard layout + combat map + click-to-move | 2026-03-27 | 2026-03-27 |
| 008-content-schema | Pydantic content models, catalogs, schema-driven forms, DM restructure | 2026-03-26 | 2026-03-27 |
| 007-world-session | Save/load, give item, fork UI, layer editor, partial worlds | 2026-03-26 | 2026-03-27 |
| 006-layer-composition | Library templates, manifest, world builder wizard | 2026-03-26 | 2026-03-26 |
| 005-tech-sweep | God classes split, test gaps, architecture fixes | 2026-03-26 | 2026-03-26 |
| 004-monster-encounters | Squads, ecology layer, faction relations, encounters | 2026-03-25 | 2026-03-26 |
| 003-inventory-trading | Inventory, equip slots, accessories, trading | 2026-03-25 | 2026-03-25 |
| 002-meta-pipeline | Sprint pipeline, skills, integration tests | 2026-03-24 | 2026-03-25 |
| 001-class-mechanics | Fighter/Rogue L1 infrastructure (phases 1-3.5, phase 4 deferred → sprint 011) | 2026-03-24 | 2026-03-25 |
