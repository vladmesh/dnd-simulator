# Project Status

Текущее состояние проекта. Один файл — быстрый ответ на "где мы сейчас".

**Last updated:** 2026-07-14
**Position:** Sprint 023 Phase 8 planned: post-audit E2E playbook расходится с установленным Paladin L1→L2 contract.
**Next:** Исправить Paladin E2E expectations, затем повторить полный обязательный post-audit E2E.
**Blockers:** §14.1 ошибочно требует Fighting Style и spell slot у Paladin L1; продукт следует SRD/PHB 2014, где они появляются на L2. nearby-creature race label остаётся отдельным non-blocking контрактом `DND_LANGUAGE`.

## Current Sprint

**Sprint:** 023-trigger-table
**Goal:** Парные триггеры `{on, until}` на типизированной таксономии событий активируют и гасят существ; ecology получает событийный write-back смертей логова (прототип detail-ladder).
**Started:** 2026-07-12
**Phase:** 8 — Follow-up post-audit E2E Paladin (task 1 done, task 2 pending) — 2026-07-14

Phase 8 Task 1 done: §14.1 теперь проверяет Paladin L1 без Fighting Style и spell slots; §3.5
остаётся единственным L2 flow для Fighting Style, slots и Divine Smite. Далее повторить весь
required non-LLM post-audit E2E. Product code не менялся: Fighting Style, Divine Smite и spell
slots остаются L2 features.

Phase 7 closed: targeted post-audit E2E passed 4/4, including EN live action failure `Target too far (10 ft, reach 5 ft).`; nearby-creature race label remains deferred as non-blocking because content-name locale stays a separate `DND_LANGUAGE` contract. All phases complete; a follow-up audit is required after the final locale fix.

Follow-up [post-audit E2E](e2e-reports/2026-07-14-sprint023-post-audit.md) passed 10/11 targeted scenarios, then stopped because §14.1 incorrectly required a Paladin L1 Fighting Style selector. Phase 8 corrects that stale E2E expectation and repeats the dependent Paladin L2/Smite flow; Sprint 023 is not ready for close-sprint until the rerun is green.

Phase 6 Task 1 done: live WS payloads use the current session locale and `COMBAT_ENDED` has typed perception. Task 2 done: Master lists only sessions managed in memory, excluding stale disk saves.

Phase 6: [post-audit E2E report](e2e-reports/2026-07-13-sprint023-post-audit.md) зафиксировал два блокера: синхронизация frontend/session locale для live WS + typed `COMBAT_ENDED` perception и исключение stale disk saves из Master session list.

Phase 5 closed: единый typed event-контракт; trigger runtime, event-log и perception split; transport builders; non-object WS JSON protocol containment; final shutdown-autosave failure logging.

**Audit:** Triaged follow-up 2026-07-14: quick-fix 0, sprint-relevant 0, backlog 11 already tracked. Предыдущий triage 2026-07-13: quick-fix 0, sprint-relevant 0 deferred, один подпункт добавлен в `any-to-object-sweep`; остальные findings уже отслеживаются.

Phase 4 Task 1 done: сохраняемый GM override и управление trigger armed state через master API под world gate.

Phase 4 Task 2 done: минимальные live controls активности и trigger armed state в существующем списке существ.

Phase 4 Task 3 done: malformed action параметры изолированы в failed `ActionResult`; round thread и следующий ход живы.

Phase 4 Task 4 done: Dash metadata только пополняет movement budget и требует отдельного `move`/`move_to`.

### Phases

1. Типизированная таксономия событий (+ `encounter-spawned-perceiver`)
2. Событийный write-back — смерти логова (`lair-death-event`)
3. Trigger table (`{on, until}`, самогашение, сейв)
4. Ручка ГМ + failure containment (`action-error-kills-round-loop`, `dash-actiondef-movement-conflation`)
5. Post-audit refactor (`typed-event-compat-bridge`, entities/perception/session/transport decomposition, два test-gap)
6. Post-audit E2E fixes (`live-ws-locale-combat-ended`, `stale-master-sessions`)
7. Follow-up post-audit E2E locale (`live-action-failure-locale`; race label deferred non-blocking)
8. Follow-up post-audit E2E Paladin (`paladin-e2e-contract`, full Paladin post-audit rerun)

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
