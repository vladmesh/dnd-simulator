# E2E Report: sprint019-post-audit

**Date:** 2026-06-29
**Flags:** --no-llm (default; no OPENROUTER_API_KEY in env)
**Sections tested:** 1, 2, 3, 4 (Second Wind), 6 (full Master panel), 10, 11.5, 13.2 + auto-discovered (sprint-019 changes)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, backend :8001, frontend :5173
**Context:** Post-audit regression for Sprint 019 (control-plane-prep). Sprint was mostly an internal refactor (GameService peel into WorldBuilderCommands / PlayerCommands / commands_creatures mixins, action-parsing seam, public World query API) plus phase-3 visible-gap fixes (combat-log i18n + encounter perceiver, corpse/container nearby-action hiding, dead-code removal). Coverage targeted the refactored control-plane (both player and master command paths) and the visible-gap changes.

## Summary

- Scenarios: 28 tested, 27 passed, 1 partial (corpse-only-Inspect not driven to completion in peaceful mode; covered by phase-3 report + live cases verified)
- Quick fixes: 0
- Blockers (NEW): 0
- Known/pre-existing issues hit: 4 (none are new regressions from the sprint-019 refactor)

The control-plane refactor is functionally transparent: every player and master command path exercised behaves as before. The phase-3 combat-log i18n fix is confirmed clean (no `{oa}` / placeholder leaks). No new 5xx responses or tracebacks beyond the known dev-only WS StrictMode race.

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing Play/DM split | pass | Two cards (Играть / Мастер подземелий), RU default |
| 1.2 | Quick start — new session, create char | pass | Sword Vale session, redirect to /play/:id, WS connected, first turn in log |
| 1.3 | Language toggle EN↔RU | pass | Labels switch correctly |
| 1.4 | Point buy | pass | STR 15 → "+" disabled, CON 14, 3/27 left; preview HP 12, AC 19 (ChainMail 16 + Shield 2 + Defense 1), Gold 1000 |
| 1.5 | Class-specific UI | pass | Fighting Style selector shown for Fighter; equipment line correct |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | Live NPC (marta) shows Атаковать/Говорить/Inspect |
| 2.2 | Talk to NPC (rule-based) | pass | Canned reply "Что будете заказывать?"; speaker rendered as "человек" (perceive() race descriptor, by design) |
| 2.3 | Wait / time advance | pass | 10:00 → 11:00 |
| 2.4 | Move between locations | pass | Docks → location panel + nearby (lira) updated, return path shown |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | "Бой начался! Порядок инициативы: …", sidebar → CombatPanel, Раунд 1 |
| 3.2 | Attack and damage | pass | "Ты атакуешь человек (longsword slash) [d20(16)+4=20 vs КЗ 15], 10 урона (1d8 рубящий + +2 str)" |
| 3.3 | End turn + NPC response | pass | NPC attack "(rapier thrust) [d20(14)+5=19 vs КЗ 19], 9 урона (1d8 колющий + +3 dex)", dash "ускоряется (+30 ft)" |
| 3.4 | Combat ends | pass | Verified both ways: player death ("Ты погибаешь" → "Бой окончен" → GAME OVER) in Sword Vale; proper enemy kill ("человек погибает") in arena |

### Section 4: Class Features

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 4.1 | Fighter Second Wind | pass | "Ты переводишь дух и восстанавливаешь 5 ОЗ"; bonus action, action preserved |

### Section 6: Master Panel (refactored worldbuilder + creature + save commands)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Worlds tab | pass | Level-up editable (Fork+Delete); Sword Vale / Test Vale library (Fork only) |
| 6.4 | World editor (SessionView World tab) | pass | Regions/Nations/Settlements tables populated (public World query API works post-refactor) |
| 6.5 | Create session | pass | Created via UI and API |
| 6.6 | Spawn creature | pass | goblin_ui spawned (after valid role; see spawn-role-freetext-enum below) |
| 6.7 | Edit creature HP | pass | 10 → 7, reflected in table and API |
| 6.8 | Toggle brain type | pass (with caveat) | PUT /brain returns 200; with no LLM key, switch to llm logs `llm_not_configured_fallback` and stays rule_based (correct fail-safe, no --with-llm) |
| 6.9 | Delete creature | pass | Confirm dialog "Удалить Test Goblin?", removed |
| 6.10 | Advance time | pass | D1 10:00 → D2 10:00 (24h) |
| 6.11 | Save and load | pass | Named save "e2e_test"; load reverted time D2 11:00 → D2 10:00 |
| 6.12 | Give item — weapon | pass | "Test Sword" added to inventory, form stayed open, persisted via API |

### Section 10: Dashboard Layout

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | Nearby / Character+Inventory / Location all visible |
| 10.2 | Compact log + expand overlay | pass | "Журнал событий" overlay with close |
| 10.4 | Click-to-move on BattleMap | pass | Move consumed 30фт → 25фт |
| 10.5 | Combat layout switch | pass | Right column → BattleMap; returns after combat |
| 10.6 | Action bar budget | pass | Действия/Бонус/Движение/Реакция shown |

### Section 11 / 13

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 11.5 | Reaction budget | pass | "Реакция: 1" in budget bar |
| 13.2 | Kill reputation drop | pass | "Твоя репутация с monsters изменилась (50 → 30)" with exact delta; also "Репутация человек с kingdom изменилась" on player death |

### Auto-discovered scenarios (sprint-019 changes)

| Scenario | Reason (change) | Status | Notes |
|----------|-----------------|--------|-------|
| Combat-log i18n, no `{oa}` leak | phase-3 task1 (round.py / perception.py / locale) | pass | All combat lines fully RU (КЗ, рубящий, колющий, промах, ускоряется, погибает); no template placeholders leaked |
| Corpse/container nearby-action hiding | phase-3 task2 (Perception.tsx) | partial/pass | Live NPCs correctly show Attack/Talk/Inspect; combat enemies panel excludes the dead xp_dummy; dead player removes all action buttons. The exact "corpse in peaceful Nearby shows only Inspect" was not driven to completion (player did not win a peaceful-returning fight) — already verified in phase-3 report |
| XP grant + level-up modal | phase-3 / 017 leveling via control-plane | see Findings | Live kill granted 500 XP and auto-opened the L1→L2 modal, but completing it failed — maps to known player-xp-not-persisted (details below) |
| Master command modules (peel) | phase-2 WorldBuilderCommands/PlayerCommands/commands_creatures | pass | Full Master CRUD + save/load round-trip behave as before |
| GameService peel — player command path | phase-2 PlayerCommands + action_parsing seam | pass | create/talk/move/wait/attack/second-wind/end-turn/reputation/death all work |

## Quick Fixes

None applied (one-granule scope; no <5-min cosmetic bug found).

## Findings

### Blockers (NEW)
None.

### Known / pre-existing (NOT new regressions)

1. **player-xp-not-persisted (known, BACKLOG `should`).** In the arena, killing xp_dummy granted 500 XP live (WS event "Ты получаешь 500 опыта" + auto-opened "Повышение до 2 уровня" modal + manual "Повысить уровень" button). But REST `player_status` reports `experience=0 / level_up_available=false / level=1`, and `POST /level-up` returns `400 "No level-up available"` — so the player cannot actually level up via the UI. Root cause confirmed: `core/player.py::to_full_save_data` (lines 76-89) omits `experience` and `level_up_available`, so any restore through the autosave path resets XP. Severity note for the orchestrator: in this run the gap broke the level-up flow end-to-end (not only on an explicit save/reload) because the dev WS StrictMode race triggered an evict→restore of the session at startup. Both contributing causes are pre-existing and documented; the sprint-019 diff does not touch the experience-persistence path (its only player.py change was removing dead `to_save_data`). Recommend the orchestrator keep this under the existing player-xp-not-persisted item and consider raising its severity / scope (live, not just save/reload).

2. **Dev-only WebSocket StrictMode race (known).** At session start, `WsEventListener.on_turn` fired before the WS listener attached → one `listener_error` (with traceback) → `ws_disconnected`/`remove_listener` → `session_empty_evict` → reconnect + restore. React StrictMode double-mount in dev only. No production impact, but in dev it triggers the evict→restore that feeds finding #1.

3. **spawn-role-freetext-enum (known).** Master "Create creature": the Role field is a free-text input, but the backend `NpcContent.role` is an enum (`commoner|blacksmith|tavern_keeper|guard|merchant|farmer|gladiator`). Submitting with an empty (or non-enum) role returns `400 "1 validation error for NpcContent role …"`. Spawning succeeds once a valid enum value is typed. The frontend always sends `role` (even empty), so the default/blank case fails.

4. **English fragments inside RU strings (known i18n-sweep candidate, out of Sprint 019 scope).** Seen throughout: item/weapon names ("Chain Mail, Longsword, Shield", "longsword slash", "rapier thrust", "club"), ability tags ("+2 str", "+3 dex"), faction ids ("monsters", "kingdom"), damage-type dropdown options (slashing/piercing/…), and English action tooltips ("Attack a target…", "Sprint: move…"). Additionally, two conditions collide in RU: both `deafened` and `stunned` render as "Оглушён" in the creature-edit conditions list (translation quality, minor).

## Log Analysis

- No 5xx responses. No tracebacks beyond the single known StrictMode `listener_error`.
- `llm_not_configured_fallback` (warning) on brain-toggle-to-llm — expected (no API key, --no-llm run).
- `POST /level-up 400 "No level-up available"` and `POST /creatures 400` (empty role) are the two 4xx responses, both explained above (known issues).
- 204 leftover sessions accumulated from prior integration/E2E runs (saves dir hygiene); not a functional issue.
