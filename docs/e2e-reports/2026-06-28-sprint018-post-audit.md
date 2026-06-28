# E2E Report: sprint018-post-audit

**Date:** 2026-06-28
**Flags:** --no-llm
**Sections tested:** 1 (setup) + 2.4 (move) + 3 (combat) + 10 (combat layout) + 13.2 (reputation) + auto-discovered loot/take + region-encounter spawn (live)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, world = Test Vale (lairs/encounters/loot content)

## Summary

- Scenarios: 14 tested, 13 passed, 1 partial
- Blockers: 1 found → **FIXED + re-verified** (see "Blocker fix" below)
- Quick fixes: 1 applied (the blocker); 3 minor findings → backlog

> **Status after fix (2026-06-28):** the GAME OVER blocker was fixed and re-verified in a second
> E2E pass — creating a character now enters the game cleanly (no GAME OVER), the round drives
> turns, Wait advanced time 10:00 → 11:00. `make check` green (ruff, mypy 146 files, **2249** backend
> tests incl. 5 new, frontend). The three minor findings were sent to the backlog per request.

This is the post-audit regression gating Sprint 018 close. Audit-triage changes (a `treasure_items: list[Item]`
annotation in `monsters.py` and a `is_active_at_time` unit test) touch no runtime UI path. The sprint's
headline feature — looting a corpse via the `take` action and LootPanel — was driven end-to-end in the
browser: 200g + a Health Potion transferred from the killed merchant to the player. Region encounters
(Phase 3) were observed materializing goblins live. The run surfaced one serious lifecycle bug and three
minor findings (two pre-existing, one sprint-introduced).

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing — Play/DM split | pass | Two cards + EN/RU toggle |
| 1.4 | Character creation — point buy | pass | Remaining 15/27 at all-10s; STR 14 = +2, CON 14 = +2, math correct; HP 12 (d10 + CON +2), AC 18→19, Gold 1000 (test_vale starting_gold) |
| 1.5 | Class-specific UI | pass | Fighter shows Fighting Style selector; starting equipment Chain Mail/Longsword/Shield |
| 4.2 | Fighting Style (Defense) | pass | Selecting Defense bumped preview AC 18 → 19 (+1) live |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.4 | Move between locations | pass | Tavern → Crossroads Market; Location panel + paths updated |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | Attacking the merchant started combat (auto-hostility via forced_opponents); initiative order shown, sidebar → CombatPanel, Round 1 |
| 3.2 | Attack and damage | pass | `[d20(7)+4=11 vs КЗ 10], 8 урона (1d8 рубящий + +2 str)` — full breakdown, merchant AC 10 correct; one-shot kill |
| 3.4 | Combat ends | pass | `человек погибает`; after enemies cleared, `Бой окончен.`, sidebar returns to peaceful |

### Section 10: Dashboard / Combat layout

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | Nearby / Character+Inventory / Location all visible |
| 10.5 | Combat layout switch | pass | Right column → interactive BattleMap grid, CombatPanel left |
| 10.6 | Action bar budget | pass | Actions 1 / Bonus 1 / Movement 30ft / Reaction 1; rejected (out-of-reach) attack left budget untouched |

### Section 13: Reputation

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 13.2 | Kill reputation drop | pass | `reputation_changed` militia 50 → 30 on the merchant kill |

### Section 9: Trading

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 9.1 | Trade panel renders | partial | Merchant TradePanel showed "Pip the Merchant / 200g / Health Potion 50g / Buy" before the kill. Buy/Sell flow itself not exercised this run. |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Region encounter spawns goblins | Phase 3 region_encounters (`crossroads`) | pass | Entering tavern/market rolled goblins live (`encounter_check_moved` → goblin_1..6 across crossroads) |
| Kill → corpse becomes lootable | Phase 2 `is_lootable` + awareness | pass | After combat ended, LOOT panel showed "Pip the Merchant" with "Take all" |
| LootPanel renders loot | Phase 2 LootPanel | pass | "200g" + "Health Potion" displayed |
| Take all → transfer | Phase 2 `take` action + `transfer_items` | pass | Player gold 1000 → 1200, Health Potion added to BAG (with USE), corpse → "Empty" |

## Findings

### Blockers

- **Transient "GAME OVER" on a brand-new session (session-eviction race).**
  Immediately after creating a character, the player saw a "GAME OVER" banner while at full HP (12/12),
  peaceful phase. Root cause (from backend log, session 9ed44ab2):
  1. WS1 connects → `add_listener` (count 1), round starts.
  2. React **StrictMode** dev double-mount tears WS1 down ~18ms later → `ws_disconnected`.
  3. `remove_listener` runs (via `asyncio.to_thread`) → listeners empty → `stop_round=True` → stops the round
     thread, which fires `on_game_over` to whatever listeners exist when it returns.
  4. WS2 (StrictMode remount) reconnects → `add_listener` (count 1 again).
  5. `_on_session_empty` fires anyway → `session_empty_evict` (autosave + pop from registry), and the
     already-stopped round's `on_game_over` reaches the live WS2 → "GAME OVER".

  `GameService._on_session_empty` (`service/game_service.py:250`) and `GameSession.remove_listener`
  (`service/session.py:333`) never re-check that a listener reconnected before evicting / stopping the
  round. The window was widened by the Phase-2 disconnect fix (`asyncio.to_thread(remove_listener)`,
  commit b80c104), which delays the eviction so a StrictMode remount lands inside it. Reproduced twice
  (`session_empty_evict` ×2). **Recovers on page reload** (the reconnecting WS reloads the session from the
  autosave and restarts the round).

  Production impact is lower than dev: StrictMode double-invoke is dev-only, so a production build won't
  double-mount on initial character creation. But the underlying logic — evict/stop without re-checking
  reconnected listeners — is a real bug that bites on any quick disconnect→reconnect (network blip, tab
  backgrounding) with a needless evict+autosave+reload, and a transient GAME OVER until reconnect settles.

  Suggested fix: in `_on_session_empty` (and the `stop_round` decision in `remove_listener`), re-check
  `session` still has zero listeners under the lock before evicting/stopping; or debounce disconnect
  handling with a short grace period to absorb reconnects.

  **Blocker fix (applied + re-verified).** `service/session.py` — `run_round_loop` now fires `on_game_over`
  only when the loop ended on its own (`if not game_round.is_stopped`). `stop_round()` sets the flag for
  administrative stops (last listener gone), so a transient disconnect no longer reports game over. New
  `Round.is_stopped` property (`round.py`). On real player death the loop exits naturally (`_stop_flag`
  stays False), so the genuine game-over still fires — covered by `tests/unit/test_game_loop.py::TestRoundStopFlag`.

  Re-verified in a second E2E pass: character creation entered the game with **no GAME OVER**, the round
  drove the player's turn, and Wait advanced time 10:00 → 11:00. Backend log confirmed `run_round_loop` did
  not emit game over on the StrictMode disconnect — even though the evict still fired (won the race vs the
  reconnect), the `is_stopped` gate alone is sufficient to kill the symptom.

  An additional robustness change was tried (re-checking `has_listeners()` in `_on_session_empty` to skip
  eviction on a fast reconnect) but **reverted**: it kept the module-scoped arena session alive across the
  WS integration tests' connect/disconnect cycles instead of the expected evict→reload-reset, letting arena
  combat accumulate to a `game_over` state (5 `test_websocket.py` failures in CI, timing-dependent — passed
  locally). The `is_stopped` gate stands alone for the blocker; the eviction-on-transient-reconnect cleanup
  is filed as `session-disconnect-debounce` (needs a grace-period debounce + fixture rework; production
  without a StrictMode double-mount is barely affected).

### Minor

_All three sent to the backlog per request (non-critical / longer than a quick fix)._

- **`encounter_spawned` has no player-facing description (sprint-introduced).** → backlog `encounter-spawned-perceiver`. The new event type is
  absent from the perceiver dispatch table (`layers/entities/perception.py:520-548`), so it falls through
  to the generic `_("Something happened ({type})")` fallback (`:565`). The log showed "Что-то произошло
  (encounter_spawned)" on every region-encounter spawn. Add a `_perceive_encounter_spawned` (e.g. "You
  sense something stirring nearby") and register it.

- **i18n leakage in the combat log under the default `DND_LANGUAGE=ru` (mostly pre-existing).** → backlog `combat-log-i18n-gaps`. With the
  backend defaulting to `ru` (`i18n.py:9`), the combat log mixed Russian and English, sometimes in one
  sentence ("You attack человек … 8 урона", "Your reputation with militia changed (50 → 30)",
  "Goblin moved (15 ft)", "Cannot move there — blocked", "Goblin attacks you …"). Causes:
  - Stale catalog: code msgids carry an extra `{oa}` placeholder (`perception.py:141`, `:145`) that no
    longer matches the `.po` entry (`msgid "You attack {target}{weapon}{roll}{outcome}"`) → English
    fallback. `make messages` / re-translate / `make compile-messages` needed.
  - Untranslated strings: reputation (`perception.py:505`) and the "moved (X ft)" message have no RU entry.
  - **Genuine code bug:** `rules/handlers/movement.py:52` and `:56` return raw English errors **not wrapped
    in `_()`** ("Not on the battle map", "Cannot move there — blocked") — can never localize. (The `:56`
    string also uses an em dash.)
  - The EN-frontend / RU-backend split is itself partly a stack artifact (the E2E start command doesn't set
    `DND_LANGUAGE=en`), but the untranslated strings are real gaps for the ru-default audience.

- **Dead creature still shown in NEARBY with Attack/Talk (known, still present).** → already backlogged as `corpse-nearby-actions`. The merchant corpse
  remained in the Nearby panel with Attack/Talk buttons after death; loot is handled by the separate
  LootPanel. Same minor finding flagged in the Phase-2 report; not regressed, not fixed.

## Log Analysis

- No tracebacks, no `round_loop_error`, no `listener_error`, no `ws_send` failures in the backend debug log.
- `session_empty_evict` ×2 — the eviction race above (initial create + the reload).
- Browser console: 0 errors on the happy path; the only warnings are StrictMode "WebSocket is closed before
  the connection is established" for session 9ed44ab2 — the same double-mount that drives the GAME OVER race.

## Coverage notes

Not re-driven through the UI this run (already covered by Sprint-018 phase reports + integration suite, or
out of scope for a focused post-audit regression): Phase 1 lairs (server sim; `TestLairTreasury` +
phase1-report), Phase 4 time-of-day (`TestTimeOfDayEncounter` + phase4-report), Master panel (§6),
Equipment (§5), Accessories (§8), Reactions/OA (§11), Paladin/Smite (§14), Conditions (§7). LLM (§12)
skipped — no `--with-llm`.
