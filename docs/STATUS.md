# Project Status

Текущее состояние проекта. Один файл — быстрый ответ на "где мы сейчас".

**Last updated:** 2026-06-29
**Position:** Классовые механики и система уровней доведены до D&D L2 (Fighter / Rogue / Paladin; XP & leveling — Sprint 017). Sprint 018 закрыт (логова, лут/контейнеры, региональные таблицы встреч, время суток). Sprint 019 (control-plane-prep) закрыт — `GameService` раздроблён 1044 → 357 строк (миксины `WorldBuilderCommands`/`PlayerCommands`), core/adapter развязаны, видимые дырки (combat-log i18n, encounter-перцептор, труп-кнопки) закрыты; control-plane готов к разрезу на роли. По [ROADMAP](ROADMAP.md) дальше: Level 2 (расходуемые ресурсы), Level 3 (заклинания, интерактивные объекты), автономные тики NPC.
**Next:** Sprint 020 (`control-interfaces`) спланирован — разрез control-plane на роли worldbuilder/DM/админка (identity keystone + spectator-listener, минимальный вес) + кластер session/save-багов. Дальше по бэклогу: `quest-system`. См. [BACKLOG](BACKLOG.md) / [ROADMAP](ROADMAP.md).
**Blockers:** нет.

## Current Sprint

**Sprint:** 020-control-interfaces
**Goal:** Спроецировать control-ядро на три роли (worldbuilder/DM/админка) через минимальную identity-модель и spectator-listener; попутно закрыть кластер session/save-багов и i18n-лога.
**Started:** 2026-06-29
**Phase:** 4 — Save robustness & i18n polish (tasks generated) — 2026-06-29. Phases 1-3 COMPLETE. Ready to start task 1.

Phase 4 tasks (3): (1) persist player XP/level_up across save/reload — closes `player-xp-not-persisted` (fix `to_full_save_data` + `PlayerContent` + `_to_player` + `load_state` restore); (2) combat/event-log i18n — missing msgids (loot/lay-hands/action-surge/conditions) + faction-id leak fix (`faction_name` into `REPUTATION_CHANGED` via `QueryType.FACTION_NAME`), closes E2E `kingdom` finding; (3) handler error-string sweep — wrap ~23 `ActionResult.error` in `_()` + translate, drops em-dash in `items.py:102`; tasks 2-3 together close `combat-log-i18n-gaps`. Planning note: the bug's three originally-named causes were already fixed by code landed after the ticket; user chose the **full i18n sweep** over combat-log-only, so the handler-error gap (newly found during planning) is folded in rather than deferred to backlog.

Phase 3 CLOSED (2026-06-29): integration 166 passed (5 spectator-WS + 1 grace-period test added during implementation, 0 failures); E2E green ([phase3-report](sprints/020-control-interfaces/e2e/phase3-report.md)) — DM/admin Live observe feed verified end-to-end across two browser tabs (player generates combat events → admin+DM spectator streams them read-only with event-type badges + RU descriptions), spectator connect/disconnect churn never evicts the session while a player is connected, player-WS identity propagation regression green. 0 blockers. One minor finding deferred to Phase 4: `kingdom` faction id leaks untranslated into the RU reputation log line (known `combat-log-i18n-gaps`).

Phase 3 task 4 DONE (2026-06-29): frontend live observe stream — `components/master/SessionLiveFeed.tsx` opens a dedicated `new WsClient()` spectator socket (`?spectate=true`), accumulates `events` from `turn`/`action_result`/`round_result` into a read-only scrolling feed; `SessionView` gets a `live` tab for DM + admin. `WsClient.connect` now takes `{ playerId?, spectate? }`. Broke the latent `wsClient ↔ gameStore` import cycle (surfaced by importing `WsClient` from a component loaded before gameStore): `wsClient.ts` reads identity via `loadIdentity()` from `identitySlice` (type-only gameStore import) instead of `useGameStore.getState()`. 4 new unit tests; `make check` green (backend 2303, frontend 260).

Phase 3 task 1 DONE (2026-06-29): spectator-listener primitive in `GameSession` — `add_spectator`/`remove_spectator` (read-only broadcast via `_fire`, never drive the round or `_on_empty`), `has_player_listeners()` predicate keys the "session empty" decision on player listeners only. 7 new unit tests.

Phase 3 task 2 DONE (2026-06-29): disconnect grace-period — closes backlog `session-disconnect-debounce`. `remove_listener` arms a deferred `threading.Timer` (`_evict_grace_seconds`, default 1.5s, env `DND_EVICT_GRACE_SECONDS`) instead of stopping+evicting synchronously; `_run_evict_check` re-verifies player-empty before stop+`_on_empty`; `add_listener`/`stop_round` cancel the pending timer (reconnect/deliberate-stop cancels evict). 4 new unit tests + 1 integration; 2 task-1/characterization tests updated to the deferred contract. `make check` green (backend 2303, frontend 256); integration 161 passed.

Phase 3 task 3 DONE (2026-06-29): spectator WS endpoint — `?spectate=true` on `/api/ws/{session_id}` registers a read-only observer (`_run_spectator` helper) after session validation, before player resolution / `start_round`: replays last turn, `add_spectator`, rate-limited receive loop that rejects `action`/`reaction` with "Spectators cannot submit actions", `finally remove_spectator` (never evicts). Player path unchanged. 5 new integration tests; `make check` green (2303/256); integration 166 passed.

Phase 3 tasks (4): (1) spectator-listener primitive in `GameSession` (read-only broadcast, lifecycle keyed on player listeners); (2) disconnect grace-period — closes `session-disconnect-debounce` via deferred `threading.Timer` evict, reconnect cancels; (3) spectator WS endpoint (`?spectate=true`, no `start_round`, actions rejected); (4) frontend live observe feed in `SessionView` for DM/admin. Backend-first, then frontend. `player-xp-not-persisted` stays in Phase 4 (grace-period only removes the dev evict→restore that *triggers* it).

Phase 1 COMPLETE (2026-06-29): world/session attribution (`creator`/`created_by`), `service/identity.py` + `get_identity` request-seam (header `X-User-Id`/`X-Role`, invalid role → 400, default ADMIN), frontend identity slice + header/WS propagation + role selector. Integration 157 passed; E2E green ([phase1-report](sprints/020-control-interfaces/e2e/phase1-report.md)).

Phase 2 COMPLETE (2026-06-29): projection-only lens cut (creator = attribution, role not enforced; no 403s). Backend scoping primitives (`list_worlds(creator=)` filter + `?creator=` query-param, `list_sessions` enriched with `created_by`/`time`); frontend role routing in `MasterScreen` — worldbuilder (own worlds, no sessions), DM (own worlds + own sessions scoped by `created_by` + hot-controls), admin (read-only cross-session park view, write affordances stripped, observe-only `SessionView`), player/null fallback (full god-mode); inline creature inventory in observe list closes `master-panel-creature-inventory` remnant. Integration 160 passed (3 new lens-scoping tests); E2E green ([phase2-report](sprints/020-control-interfaces/e2e/phase2-report.md)) — 4 lenses + core-flow regression, 0 blockers.

### Phases

1. Identity & role keystone — Role + owner-тег на мирах + request-seam «кто звонит» (header/config, без auth/БД) + фронт-селектор роли
2. Three-lens projection of `/api/master/*` — разрез god-mode по ролям (worldbuilder/DM/админка) + `master-panel-creature-inventory`
3. Spectator-listener + disconnect-debounce — read-only подписка на сессию (DM/админка/зрители) + grace-period evict-фикс
4. Save robustness & i18n polish — `player-xp-not-persisted` + `combat-log-i18n-gaps` + сверка бэклога

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
