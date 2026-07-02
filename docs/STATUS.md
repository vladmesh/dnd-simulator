# Project Status

Текущее состояние проекта. Один файл — быстрый ответ на "где мы сейчас".

**Last updated:** 2026-06-30
**Position:** Классовые механики и система уровней доведены до D&D L2 (Fighter / Rogue / Paladin; XP & leveling — Sprint 017). Sprint 018 закрыт (логова, лут/контейнеры, региональные таблицы встреч, время суток). Sprint 019 (control-plane-prep) закрыт — `GameService` раздроблён 1044 → 357 строк (миксины `WorldBuilderCommands`/`PlayerCommands`), core/adapter развязаны, видимые дырки (combat-log i18n, encounter-перцептор, труп-кнопки) закрыты; control-plane готов к разрезу на роли. По [ROADMAP](ROADMAP.md) дальше: Level 2 (расходуемые ресурсы), Level 3 (заклинания, интерактивные объекты), автономные тики NPC.
**Next:** активного спринта нет. Топ-кандидат — `control-interfaces` (разрез control-plane на роли worldbuilder/DM/админка, ради чего готовился Sprint 019); далее `quest-system`. См. [BACKLOG](BACKLOG.md) / [ROADMAP](ROADMAP.md).
**Blockers:** нет.

## Current Sprint

**Sprint:** 020-thermo-sweep
**Goal:** закрыть кластер структурного долга и багов из термоядерного ревью — чистота `rules/`, типизация межслойных границ, декомпозиция выросших модулей и фронтовых god-компонентов; поведение неизменно
**Started:** 2026-06-30
**Phase:** 2 — Типизация границ + enums (tasks generated) — 2026-07-02

Полный sweep (выбран пользователем), целится в `control-interfaces`. Источник — [thermo-nuclear-review.md](thermo-nuclear-review.md). Phase 1 закрыта (5 задач). Phase 2 разбита на 4 задачи: typed query contract / SquadInfo-LairInfo / enum-добивка + get_layer / exception handlers + player-status. Ready to start task 1.

### Phases

1. Корректность и инварианты — баги ревью (BLOCKER порчи данных, иконка, тихий travel, HTTP-статус) + чистота rules/ (structlog/I-O вон, gettext, RNG) под regression-тестами
2. Типизация границ + enums — query-контракт, EntityType/BrainType/LayerSource, World.get_layer, exception handlers, player-status (фундамент под control-interfaces)
3. Декомпозиция бэка — round/combat/ecology/activation split, реестр экипировки, дедуп сериализации, разрыв цикла core/player→content_loader
4. Декомпозиция фронта — TargetDropdown/SchemaForm/EventLog/WorldOverview, общие типы, дедуп slice'ов

## Recent activity (non-sprint)

- 2026-06-20 — CORS origins сделаны конфигурируемыми (`CORS_ALLOWED_ORIGINS`); Docker base-image запинен по digest.
- 2026-04-24 — post-017 cleanup: `perceive()` без вшитых ран в имя, REST `player_status` отдаёт equipped + inventory, убрана Cancel-кнопка в LevelUpModal.

## Sprint History

| Sprint | Goal | Started | Completed |
|--------|------|---------|-----------|
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
