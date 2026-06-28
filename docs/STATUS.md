# Project Status

Текущее состояние проекта. Один файл — быстрый ответ на "где мы сейчас".

**Last updated:** 2026-06-28
**Position:** Классовые механики и система уровней доведены до D&D L2 (Fighter / Rogue / Paladin; XP & leveling — Sprint 017). Sprint 018 Phases 1–3 закрыты (логова, лут/контейнеры, региональные таблицы встреч). По [ROADMAP](ROADMAP.md) дальше: Level 2 (расходуемые ресурсы), Level 3 (заклинания, интерактивные объекты), Phase 3 (автономные тики NPC).
**Next:** Sprint 018 Phase 4 (время суток — тег `time_of_day` на встречах; scope сужен до встреч, логова отложены) — задачи сгенерированы (1 задача). Дальше — `/implement`.
**Blockers:** нет.

## Current Sprint

**Sprint:** 018-lairs-encounters-loot
**Goal:** Монстры населяют мир независимо от игрока: постоянные логова (зачищаются убийством ядра), региональные таблицы встреч, опасность по времени суток и лутаемые контейнеры/трупы.
**Started:** 2026-06-28
**Phase:** 4 — Время суток (tasks generated) — 2026-06-28. Ready to start task 1.

Phase 4 scope сужен на планировании до **встреч** (лог-активность день/ночь → бэклог `lair-time-of-day`). Один таск: `time_of_day`-тег на encounter-entry, новый geography-запрос `IS_DAYLIGHT`, чистое правило `is_active_at_time`, фильтр в `ActivationManager._roll_encounters`. Жёсткий гейт по тегу (untagged = всегда, как сейчас). Финальный полный E2E спринта — при `/close-phase`.

Phase 3 closed: region encounter tables resolve region → location at load time (`_flatten_region_defaults[T]`, shared with battle maps); `ActivationManager` untouched. Integration 149 → 152 green (`test_encounters.py` + `encounter_world`: fallthrough, override, empty region); `make check` green (2237 backend, 238 frontend); E2E regression on the activation/round/combat path 12/12, 0 blockers ([e2e/phase3-report.md](sprints/018-lairs-encounters-loot/e2e/phase3-report.md)).

Phase 1 closed (materialization, respawn, depletion; integration 146 green, E2E 12/12). Phase 2 closed: (1) InventoryHolder substrate + `transfer_items` ✓, (2) `Container` entity + persistence ✓, (3) `take` action ✓, (4) lair treasury ✓. Close-phase: docker `make test-integration` 149 green (incl. `TestLairTreasury` ×3), `make check` green (2228 backend unit, 238 frontend), E2E 7/7 (kill → corpse loot → Take all transfers gold+item; report in `e2e/phase2-report.md`). Two fixes landed during close: (a) **product** — WS disconnect no longer blocks the asyncio loop (`routes_ws.py`: `remove_listener` via `asyncio.to_thread`; was a ≤5s freeze of all sessions on every disconnect, deadlock between the round thread's `_send` and `stop_round`'s join); (b) **test** — `test_lairs.py` drains the auto re-prompt after a turn-ending `take` (off-by-one turn stream). Minor non-blocking finding: dead creatures still show Attack/Talk in the Nearby panel (loot handled by LootPanel; attacking a corpse returns a clean "already dead").

### Phases

1. Логова — машина состояний `active → depleted`, core-gating, respawn, опц. `depletion_chance`
2. Лут и контейнеры — `InventoryHolder`/`Lootable`, `Container`, `transfer_items`, action `take`, казна логова
3. Региональные таблицы встреч — таблицы по региону с fallthrough от локации
4. Время суток — встречи и активность логов варьируются день/ночь; финальный E2E

## Recent activity (non-sprint)

- 2026-06-20 — CORS origins сделаны конфигурируемыми (`CORS_ALLOWED_ORIGINS`); Docker base-image запинен по digest.
- 2026-04-24 — post-017 cleanup: `perceive()` без вшитых ран в имя, REST `player_status` отдаёт equipped + inventory, убрана Cancel-кнопка в LevelUpModal.

## Sprint History

| Sprint | Goal | Started | Completed |
|--------|------|---------|-----------|
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
