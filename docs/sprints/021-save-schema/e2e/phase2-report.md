# E2E Report: sprint021-phase2

**Date:** 2026-07-10
**Flags:** --no-llm
**Sections tested:** targeted phase 2 save/load + short smoke from sections 1, 3, 6, 9
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, backend :8001, frontend :5173

## Summary

- Scenarios: 7 tested, 5 passed, 1 partial, 1 failed
- Quick fixes: 0 applied
- Blockers: 0 found
- Note: Playwright MCP tools were not visible in this worker session, so the same browser scenarios were executed with the repo-local Playwright package. No code was changed.

## Results

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1 | Landing page | pass | `/` shows Play and Dungeon Master entry points. |
| 2 | Character creation smoke | pass | Sword Vale fighter was created with STR 15 / CON 14, Defense style. Runtime status: HP 12/12, AC 19, gold 1000, Longsword + Chain Mail + Shield equipped. |
| 3 | save -> load -> continue | pass | Moved from The Salty Anchor to Silverport Market Square, saved through `/master/:sessionId` as `phase2_current_c2132f2b`, mutated HP/gold/XP, loaded through the master UI. Load restored HP 12/12, gold 1000, XP 0, location `silverport_city_market`, equipment and empty inventory. `Wait` then advanced time to 11:00, so the session continued. |
| 4 | Save envelope contents | pass | `saves/sword_vale/phase2_current_c2132f2b.json` has `schema_version: 1` and `world.dice_rng_state`. |
| 5 | Mid-combat save JSON | pass | Spawned `training_ogre_9119f459`, attacked through UI, saved as `000_phase2_midcombat_9119f459`. Save has `schema_version: 1`, RNG state, and `world.layers.entities.combats.silverport_city_tavern` with `turn_order`, `round_number`, `sides`, and `entity_to_side`. |
| 6 | Mid-combat load and continue | partial | Loading the combat save kept the game in combat layout and combat continued, but reconnect/load advanced the fight beyond the saved Round 1 before the page became stable. See Finding 1. |
| 7 | Trading smoke | pass | Moved to Silverport Market Square and bought Health Potion. Player gold changed 1000 -> 950, potion appeared in inventory and sell list, merchant gold changed 500 -> 550. |

## Findings

### Major

- Mid-combat load/reconnect can advance combat before the UI is ready.
  - Repro:
    1. Create Sword Vale fighter.
    2. Spawn a 30 HP monster in `silverport_city_tavern`.
    3. Attack the monster through the nearby list.
    4. Save in master Saves tab as `000_phase2_midcombat_<session>`.
    5. End turn once so the world advances.
    6. Load the saved combat save through master UI, then reconnect `/play/<session>`.
  - Expected: state returns to saved Round 1 turn order: player, Marta, Training Ogre, and waits at the saved turn.
  - Actual: combat remains alive, but the page showed later rounds after reconnect. Logs show the round loop continuing around disconnect/reconnect, including `listener_error` in `WsEventListener.on_turn` for session `9119f459`.
  - Evidence: save JSON contains the correct saved combat state, including `round_number: 1`, `turn_order: ["player_4d92d4fd", "marta", "training_ogre_9119f459"]`, and sides `{0: ["marta", "player_4d92d4fd"], 1: ["training_ogre_9119f459"]}`. UI after load later showed Round 3/4.

### Minor

- The UI mixes languages in EN mode. Nearby NPC type appears as `человек`, combat log uses Russian fragments such as `Бой начался`, `КЗ`, `промах`, and `урона`, while the shell UI remains English.
- Character creation point-buy screen starts with all abilities at 10 and shows `Remaining points: 15 / 27`. The playbook currently expects the initial counter to be 27 and explicit 15 -> 9 point behavior.
- Vite logs repeated WebSocket proxy `EPIPE` and `ECONNRESET` during headless page reconnects. These correlated with test page lifecycle but should stay visible because the backend also logged `listener_error`.

## Log Analysis

- Backend grep found two `listener_error` records:
  - `session_670276e3`, peaceful `WsEventListener.on_turn`, during a short-lived combat smoke page.
  - `session_9119f459`, combat `WsEventListener.on_turn`, during mid-combat load/reconnect.
- Structured logs for `session_9119f459` show combat did continue after load, but the round loop also advanced on disconnect/reconnect and eventually evicted the empty session after the browser closed.
- `llm_not_configured_fallback` warnings appeared for world NPCs with LLM brain type. LLM scenarios were not run.

## Artifacts

- Main restored save: `saves/sword_vale/phase2_current_c2132f2b.json`
- Mid-combat save inspected: `saves/sword_vale/000_phase2_midcombat_9119f459.json`
- Backend log: `/tmp/dnd-e2e-backend.log`
- Frontend log: `/tmp/dnd-e2e-frontend.log`
- Structured logs: `/tmp/dnd-e2e-logs/session_9119f459/full.jsonl`, `/tmp/dnd-e2e-logs/session_c2132f2b/full.jsonl`, `/tmp/dnd-e2e-logs/session_8273a543/full.jsonl`
