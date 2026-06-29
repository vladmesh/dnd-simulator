# E2E Report: sprint020-post-audit

**Date:** 2026-06-29
**Flags:** --no-llm
**Sections tested:** core regression (1,2,3,6,10,13,15) + sprint-020 auto-discovered (identity, 3-lens projection, spectator feed, XP persistence)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, DND_LANGUAGE=ru (default)

## Summary

- Scenarios: 28 tested, 28 passed, 0 failed
- Quick fixes: 0 applied
- Blockers: **0**

Post-audit regression for Sprint 020 (control-interfaces). All four phases verified end-to-end through the real UI: identity/role keystone, three-lens master projection, spectator live feed, and the save/i18n cluster. Core gameplay (char creation, combat, leveling) regression-green. Backend log clean — 0 tracebacks, no server crashes, no unexpected 4xx/5xx. UI renders fully in Russian. Findings are all minor and mostly pre-existing.

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.2 | Quick start → create char → enter game | pass | sword_vale session, WS connected, first turn rendered |
| 1.3 | Language (RU default) | pass | Entire app RU end-to-end; EN/RU toggle present on every screen |
| 1.4 | Character creation — point buy | pass | STR 15 (+ disabled), CON 14, 3/27 left; preview HP 12, AC 19 (ChainMail 16 + Shield 2 + Defense 1), Gold 1000 |
| 1.5 | Class-specific UI (Fighter style selector) | pass | Defense/Dueling/GWF options; equipment Chain Mail/Longsword/Shield |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.2 | Talk to NPC (rule-based) | pass | «Что будете заказывать?» canned RU reply |
| 2.4 | Move between locations | pass | Tavern → Docks; location panel updated; NPC `lira` materialized on entry |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | "Бой начался! Порядок инициативы: …"; CombatPanel + BattleMap shown |
| 3.2 | Attack and damage | pass | Full RU breakdown: `[d20(15)+4=19 vs КЗ 10], 4 урона (1d8 рубящий + +2 str)` |
| 3.3 | End turn and NPC response | pass | lira moved, attacked (rapier thrust, miss), dashed; round advanced 1→2 |
| 3.4 | Combat ends | pass | "человек погибает", "Бой окончен.", sidebar returns to peaceful + Loot panel |

### Section 6: Master Panel

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.11 | Save and load | pass | Save "xptest" created; load confirm dialog; state replaced from disk |

### Section 10: Dashboard Layout

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | Nearby / Character+Inventory / Location all visible |
| 10.2 | Compact log + expand overlay | pass | Overlay opens with full log + close button |
| 10.5 | Combat layout switch | pass | Right column → BattleMap grid (@ = player, 1 = enemy); CombatPanel left |
| 10.6 | Action bar budget display | pass | "Действия 1 · Бонус 1 · Движение 30фт · Реакция 1" |

### Section 13: Faction Relations & Reputation

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 13.2 | Kill reputation drop | pass | `reputation_changed` with faction display name + delta (see Phase 4 below) |
| 13.3 | Auto-hostility | pass | Attacking peaceful NPC (marta) auto-started combat with correct sides |

### Section 15: Lairs, Encounters & Loot

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 15.1 | Loot via `take` (empty corpse) | pass | Dead marta → "Забрать всё" disabled, "Пусто" |
| 15.5 | Corpse action buttons | pass | Dead creature in Nearby shows only Inspect — no Attack/Talk |
| 15.6 | Combat-log i18n | pass (minor nits) | Template strings fully RU, no placeholder leaks; content-name nits below |

### Auto-discovered scenarios (Sprint 020)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Phase 1 — role selector | identity keystone | pass | Landing selector: Worldbuilder/DM/Admin/Player; persisted in localStorage `identity` |
| Phase 1 — WS identity propagation | request-seam | pass | WS URL carries `user_id=admin1&role=…`; header propagation confirmed |
| Phase 2 — worldbuilder lens | 3-lens projection | pass | Only Worlds tab (no Sessions); worlds filtered to `creator==userId` |
| Phase 2 — DM lens | 3-lens projection | pass | Worlds + Sessions tabs; sessions scoped by `created_by`; New Session gated on owned worlds |
| Phase 2 — admin lens | 3-lens projection | pass | All worlds (no Fork/Delete), all sessions (observe-only "Управление"); SessionView = "Наблюдение (только чтение)", only Мир/Существа/Лента tabs |
| Phase 2 — player/null god-mode | 3-lens projection | pass | Full SessionView: Мир/Существа/Лента/Время/Сохранения + "Изменить" edit affordances |
| Phase 3 — spectator live feed | spectator-listener | pass | Admin "Лента" streamed live combat read-only with event-type badges (`combat_started`/`entity_attack`/`entity_move`/`entity_dash`/`round_start`) + RU text across rounds 1–2 |
| Phase 3 — spectator never evicts | grace-period | pass | `add_spectator`/`remove_spectator` logged; spectator churn left player session running |
| Phase 4 — faction display name | combat-log i18n | pass | sword_vale rep line: **«Твоя репутация с Силы Королевства изменилась (100 → 80)»** — display name, not raw `kingdom` slug |
| Phase 4 — XP persistence | save/reload | pass | experience 500 + level_up_available round-trip save→load (verified in `xptest.json` on disk + API); reloaded eligible Fighter levels up L1→L2 (HP 10→16), `POST /level-up → 200` (was 400 before fix) |
| XP/leveling — gain + modal | leveling | pass | "Ты получаешь 500 опыта…"; auto level-up modal "Повышение до 2 уровня" (HP +6, Action Surge) |

## Quick Fixes

None.

## Findings

### Blockers

None.

### Minor

- **WS StrictMode double-mount artifacts (dev-only).** Browser console shows "WebSocket is closed before the connection is established" warnings, and the backend logged one `listener_error` on `on_turn` during a player reconnect (two WS connections opened, one wrote to a socket the React StrictMode cleanup was already closing → that listener dropped; the surviving listener works and the session continues). The `finally remove_spectator`/`remove_listener` lifecycle keeps counts correct. Production builds don't double-invoke effects, so this won't occur outside dev. No functional impact.
- **Content names stay English inside the RU combat log.** The weapon attack name (`longsword slash`) and ability source (`+2 str`) render in English within otherwise-Russian lines. These are content/attack proper names, not gettext msgids, so they're outside the Phase 4 i18n scope. The 15.6 requirement (no `{weapon}`/`{roll}`/`{oa}` placeholder leaks) passes — values interpolate correctly. Localizing content names is a separate, larger effort.
- **Perceive naming inconsistency in the combat log (pre-existing).** Attack/death lines use the perceived race label in the nominative (`Ты атакуешь человек` — should be accusative `человека`; `человек погибает`), while initiative/move/loot lines use the actual name (`Марта` / `Лира` / `XP-манекен`). Mixed naming + a grammatical case mismatch from injecting a nominative label into an accusative slot. Predates Sprint 020 (perceive behavior); the i18n work translated the template but not the interpolated label's case.
- **Reputation faction display name falls back to the raw id when the world has no politics definition for that faction.** level_up arena rep line shows `monsters` (raw faction id) because the arena world defines no nation/faction named `monsters`. This is the documented fallback (`QueryType.FACTION_NAME` → raw `faction_id` when unresolvable); the headline case (sword_vale → «Силы Королевства») resolves correctly.

## Log Analysis

- 0 tracebacks/exceptions in the backend log; no server crashes (health stayed up throughout).
- 1 `level=error` event: the StrictMode `listener_error` described above (benign, dev-only).
- The only 4xx were two `GET /api/worlds` / `GET /api/sessions` 404s — manual wrong-endpoint curl probes during setup (correct routes are `/api/master/*`), not app behavior.
- Spectator lifecycle confirmed in structured logs: `ws_connected (spectate:true)` → `add_spectator spectator_count:1`, with the dev double-mount visible as connect→disconnect→reconnect settling at count 1.
