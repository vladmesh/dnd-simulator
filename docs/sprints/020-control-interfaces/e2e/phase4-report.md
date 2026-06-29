# E2E Report: sprint020-phase4

**Date:** 2026-06-29
**Flags:** --no-llm
**Sections tested:** Phase 4 new functionality (combat/event-log i18n + handler-error i18n + faction-name leak fix) + targeted regression (session setup, peaceful move, combat, trade panel)
**Stack:** `DND_LANGUAGE=ru`, LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 9 tested, 9 passed, 0 failed
- Quick fixes: 1 applied (frontend EventLog i18n — Round / moved)
- Blockers: 0
- Minor findings: 1 (stale combat turn after combat ends)

Phase 4's headline fix — the `kingdom` faction-id leak in the reputation log line — is verified end-to-end: a kill now renders «Твоя репутация с **Силы Королевства** изменилась (100 → 80)», the faction's localized display name, not the raw slug. The combat/event log renders in Russian across attack, damage breakdown, death, reputation, and combat-end. Action-failure handler errors render in Russian (two observed live).

## Results

### Phase 4 — combat/event-log i18n (RU)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| P4.1 | Combat start line RU | pass | «Бой начался! Порядок инициативы: …» |
| P4.2 | Attack line + damage breakdown RU | pass | «Ты атакуешь человек (longsword slash) [d20(18)+4=22 vs КЗ 10], 8 урона (1d8 рубящий + +2 str)». Weapon `attack_name` ("longsword slash") and the `str` ability tag stay English — content data / ability abbreviation, expected. |
| P4.3 | Death line RU | pass | «человек погибает» |
| P4.4 | **Reputation line — faction display name (the leak fix)** | pass | «Твоя репутация с Силы Королевства изменилась (100 → 80)» — display name, NOT the `kingdom` slug. Closes the phase-3 finding. |
| P4.5 | Combat-end line RU | pass | «Бой окончен.» |
| P4.6 | Wound status RU | pass | enemy shown as «человек(ранен)» |

### Phase 4 — handler-error i18n (RU)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| P4.7 | Action-failure error renders RU | pass | Two observed live: «'wait' недоступно в бою» and «Цель слишком далеко (35 ft, досягаемость 5 ft).». Both `action_failed` events confirmed RU in backend logs. `ft` unit stays English (pre-existing, not in scope). |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Combat-log round header / move aggregation in RU | Phase 4 i18n sweep; EventLog.tsx renders these two client-side | **fixed** | Were hardcoded English ("Round N", "{name} moved (X ft)"). Fixed (quick fix below). Round header verified rendering «Раунд 1» after the fix. |
| Trade panel render (RU) | merchant nearby | pass | «Торговля», «Купить», prices; item names English (content). |

### Regression

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.x | Landing + world list + character creation (RU, Fighter/Defense, point buy) | pass | Fully RU. Preview HP 10 / AC 19 / Gold 1000, equipment list. |
| 2.x | Peaceful move between locations | pass | Tavern → Market, location panel + paths update. |
| 3.x | Combat init / attack / kill | pass | Two kills (marta, gretta engaged). Battle map, budget bar, sides all correct. |

## Quick Fixes

- **frontend/src/components/game/EventLog.tsx** — `DisplayEntryRow` rendered two combat-log strings as hardcoded English at `DND_LANGUAGE=ru`: the round divider (`Round {n}`, line ~129) and the aggregated-move summary (`{actor} moved ({ft} ft)`, line ~161). Wired `useTranslation(["game"])` into the component, switched the round divider to the existing `game:round` key, and added a new `game:moved` key (en: `"{{name}} moved ({{ft}} ft)"`, ru: `"{{name}} переместился ({{ft}} фт)"`). Round divider verified rendering «Раунд 1» live; move string is the same component/`t()` mechanism. These were the remaining client-side half of the `combat-log-i18n-gaps` symptom (the backend half was closed by tasks 2-3).

## Findings

### Blockers
- None.

### Minor
- **Stale combat turn after combat ends.** After the killing blow ends combat, the player is left mid-turn with an exhausted budget (action bar shows «Действия: 0» + «Конец хода» instead of the peaceful bar); a location-move click in that state is rejected with «'wait' недоступно в бою». Pressing «Конец хода» returns to the peaceful action bar and movement works normally. Pre-existing, not introduced by phase 4. Candidate backlog item.
- **Loot-take RU string not exercised live.** Marta's corpse was empty (no inventory/gold), so the localized `entity_take` line («Ты обираешь …») could not be triggered through the UI. Covered by unit tests (`test_perception.py::TestCombatLogLocalizesRussian::test_loot_line_russian`). The LootPanel chrome itself renders RU («Добыча», «Забрать всё», «Пусто»).
- **XP persistence (task 1) not re-validated in E2E.** Not UI-visible beyond a number; covered by unit tests + integration `test_player_state_xp` (green). Kills did grant XP via the normal path.

## Log Analysis

- Backend: no errors/exceptions/tracebacks. Only two `action_failed` INFO entries, both expected and both rendered in Russian («'wait' недоступно в бою», «Цель слишком далеко (35 ft, досягаемость 5 ft).»).
- Browser console: 0 errors, 1 warning (unrelated).
