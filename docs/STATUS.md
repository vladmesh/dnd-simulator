# Project Status

Текущее состояние проекта. Один файл — быстрый ответ на "где мы сейчас".

**Last updated:** 2026-06-29
**Position:** Классовые механики и система уровней доведены до D&D L2 (Fighter / Rogue / Paladin; XP & leveling — Sprint 017). Sprint 018 закрыт (логова, лут/контейнеры, региональные таблицы встреч, время суток) — backlog must-айтем `monster-spawn` закрыт. По [ROADMAP](ROADMAP.md) дальше: Level 2 (расходуемые ресурсы), Level 3 (заклинания, интерактивные объекты), автономные тики NPC.
**Next:** Sprint 019 (control-plane-prep) — техспринт, готовит control-plane к разрезу на роли в следующем спринте `control-interfaces`. После него топ-кандидаты: `control-interfaces`, `quest-system`. См. [BACKLOG](BACKLOG.md) / [ROADMAP](ROADMAP.md).
**Blockers:** нет.

## Current Sprint

**Sprint:** 019-control-plane-prep
**Goal:** Отвердить control-plane (GameService / session / commands / адаптеры) под будущий разрез на роли в `control-interfaces` — раздробить god-class, покрыть тестами, утончить адаптеры; попутно закрыть видимые дырки и свести бэклог.
**Started:** 2026-06-28
**Phase:** 3 — Visible gaps + backlog reconcile + dead code (COMPLETE) — 2026-06-29. Все 3 фазы закрыты. Ready for audit.

Phase 1 closed: integration 154/154, E2E 9/9 (0 blockers, см. `sprints/019-control-plane-prep/e2e/phase1-report.md`), `make check` зелёный. Phase 2 closed: все 3 таски done, GameService 1044 → 357 (`WorldBuilderCommands` + `PlayerCommands` mixins; `autosave_session` в `GameServiceProtocol`), `parse_action`/`ActionParseError` вынесены в `service/action_parsing.py` (routes_ws больше не импортирует Action/ActionType из core), `World.make_query_fn`/`make_emit_fn` public; три backlog-айтема (`action-parsing-in-adapter`, `world-private-method-access`, `adapter-imports-core-directly`) помечены fixed. Integration 154/154, E2E 18/18 (0 блокеров, `sprints/019-control-plane-prep/e2e/phase2-report.md`), `make check` зелёный.

Phase 3 closed (2026-06-29): все 3 таски done — (1) combat-log i18n + encounter-spawned перцептор (commit d3a2193); (2) фронт-гейт Attack/Talk на трупах в `Perception.tsx` (commit 17d2fb6); (3) удаление 4 мёртвых функций (`refund`/`walk_path`/`prone_stand_cost`/`to_save_data`) + сверка бэклога (8 айтемов помечены). Integration 154/154, E2E 6/6 (0 NEW-блокеров, `sprints/019-control-plane-prep/e2e/phase3-report.md`: RU-лог атаки без утечки `{oa}`, encounter-флейвор «Поблизости что-то шевелится» вместо фоллбэка с скрытым ростером, у трупа только Inspect), `make check` зелёный (backend 2267, frontend 240, mypy чисто). Латентный баг `player-xp-not-persisted` (XP/level_up не переживают современный save/reload — `to_full_save_data` не сериализует `experience`) занесён в BACKLOG как **should**, фикс вне гранулы. Все 3 фазы закрыты — ready for audit.

**Audit:** Triaged 2026-06-29 (`audit.md` commit 27973bf, 17 findings, 0 new of note). Quick-fix: 2 applied (BACKLOG-гигиена, doc-only — `god-class-game-service` помечен FIXED [1044→357], `core-brain-imports-rules` помечен FIXED [RuleBrain в `rules/rule_brain.py`]; 0 правок кода). Sprint-relevant: 0 — цель control-plane (peel GameService) достигнута; растущие модули (`round-growing`, `activation-manager-growing`, `perception-fail-fast`, `action-defs-growing`, `god-class-combat-manager`) — combat/ecology/core, не control-plane → отложены в будущий tech-sweep. Backlog: 0 новых — все 17 находок уже в BACKLOG.md (cross-ref по id). Refactor-фаза НЕ нужна. Триаж завершён.

### Phases

1. Session lifecycle test net — characterization-сетка на `session.py` (listener dispatch + round lifecycle) + commands_save + get_world_state fail-fast. Сетка под peel.
2. GameService deeper peel + adapter hygiene — раздробить god-class на суб-фасады, развязать core/adapter, public World-query API.
3. Visible gaps + backlog reconcile + dead code — combat-log i18n, encounter-perceiver, corpse-actions, удаление dead code, сверка бэклога (вкл. устаревшие `thick-adapter-world-state` + test-gap).

## Recent activity (non-sprint)

- 2026-06-20 — CORS origins сделаны конфигурируемыми (`CORS_ALLOWED_ORIGINS`); Docker base-image запинен по digest.
- 2026-04-24 — post-017 cleanup: `perceive()` без вшитых ран в имя, REST `player_status` отдаёт equipped + inventory, убрана Cancel-кнопка в LevelUpModal.

## Sprint History

| Sprint | Goal | Started | Completed |
|--------|------|---------|-----------|
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
