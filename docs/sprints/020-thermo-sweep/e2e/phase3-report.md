# E2E Report: sprint020-phase3

**Date:** 2026-07-04
**Flags:** --no-llm
**Sections tested:** 2 (Peaceful), 3 (Combat), 5 (Equipment)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs (worktree thermo-phase3-back, backend :8001, frontend :5173)

Phase 3 is behaviour-preserving backend decomposition (serialization dedup, combat_manager split, round.py cleanup, activation/ecology splits, equipment registry). E2E scope: confirm the behaviour-sensitive flows those touched still work end-to-end — equipment (task 6), combat (task 2), round loop/travel/activation (tasks 3-4), and RU i18n.

## Summary

- Scenarios: 9 tested, 9 passed, 0 failed
- Quick fixes: 0
- Blockers: 0

## Results

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | marta shown with Attack/Talk/Inspect at The Salty Anchor |
| 2.2 | Talk to NPC (rule-based) | pass | «Ты говоришь: Привет» → «человек говорит: Тихая ночка, а?» (canned RU response) |
| 2.3 | Wait and time advance | pass | 10:00 → 11:00; round loop + fast-forward + activation intact, no errors |
| 2.4 | Move between locations | pass | Salty Anchor → Silverport Docks; Location Panel + paths update; NPC `lira` activated at docks (activation/encounters/materialization split works) |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | «Бой начался! Порядок инициативы: Adventurer, Marta» |
| 3.2 | Attack and damage | pass | «Ты атакуешь человек (longsword slash) [d20(11)+4=15 vs КЗ 10], 4 урона (1d8 рубящий + +2 str)» — full breakdown; longsword attack via equipment registry, STR+2 modifier |
| 3.3/3.4 | Death + combat end | pass | «человек погибает» → «Твоя репутация с kingdom изменилась (50 → 30)» → «Бой окончен». Reputation drop on kill via `combat_resolution.handle_death` + `make_relation_fn`. Corpse becomes lootable |

### Section 5: Equipment

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 5.1 | Equip weapon | pass | Longsword attack used in combat (3.2); equip/unequip through factory handlers |
| 5.2 | Equip armor and shield | pass | Unequip Shield: «Ты убираешь Shield», AC 19→17. Re-equip: «Ты экипируешь Shield», AC 17→19. Modifier pipeline recomputes from `Creature.equipped` dict. Char-creation AC 18→19 with Defense fighting style |
| 5.3 | Use healing potion | skip | No potion in starting inventory; `use_item` handler untouched by phase 3 |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Equipment registry round-trip (task 6) | `Creature.equipped: dict` + compat props, factory handlers | pass | equip/unequip/AC-recompute + 12 ActionType wire contract all intact via UI; frontend (phase 4, unchanged) drives `equip_shield`/`unequip` as before |
| Combat death → reputation/XP (task 2) | resolvers + death moved to `combat_resolution.py` | pass | full kill cycle + rep drop correct |
| Travel + activation (tasks 3-4) | round loop dedup, activation/encounters/materialization split | pass | move + NPC activation at destination works |

## Quick Fixes

- None.

## Findings

### Blockers
- None.

### Minor
- **WS reconnect race on page reload** (pre-existing, out of scope). One `WsEventListener.on_turn` `listener_error` fired at the moment of a manual page reload (WS closed-before-established), and the reload re-synced session state to an earlier checkpoint. This is the known `session-disconnect-debounce` transport-half bug (explicitly Scope OUT in sprint.md; documented in backlog `session-disconnect-debounce` / `player-xp-not-persisted`). Not triggered by normal play — only by a hard reload. A first move-to-Docks showed a transient «Waiting for turn…» tied to this reconnect; a clean re-test of the same move (no reload) worked immediately with a proper turn. No backend logic error, no data corruption in normal flow.
- Console: 1 warning throughout — the same WS-reconnect artifact (`wsClient.ts:30`). Cosmetic dev warning.

## Log Analysis

- 1 error-level backend event total across the session: the single `listener_error` above (reload-time WS race). No exceptions in round loop, combat, activation, materialization, or serialization paths.
- All in-game strings rendered in RU (combat log, equip/unequip, reputation, canned dialogue, damage types) — i18n intact after the handler/action_defs refactor.
