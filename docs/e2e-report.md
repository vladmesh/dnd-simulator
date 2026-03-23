# E2E Test Report — React Frontend

**Date:** 2026-03-23
**Tested on:** Vite dev server (:5173) + uvicorn (:8001)
**Browser:** Chromium (Playwright MCP headless)
**Worlds tested:** Sword Vale, Quiet Village
**Flows:** Setup, Game (peaceful + combat), Master Panel, Edge cases

---

## CRITICAL (breaks core functionality)

### ~~BUG-43: State leak between sessions — wrong session data after creating new session~~ ✅ FIXED
- **Fix:** d521563 — Reset all game slices (player, turn, log) in `connect()` before opening a new WebSocket.

### ~~BUG-17: Combat actions produce no events in EventLog~~ ✅ FIXED
- **Fix:** `execute_action` returns `ActionResult` (not bool), error propagated through `on_action` callback → `action_result` WS message → frontend EventLog. Failed actions (out of range, etc.) now show as `[action_error]` events. Successful actions were already working — the original bug manifested only when attacks failed silently (e.g. out of range).

### ~~BUG-26: Nation stability edit always fails with 422~~ ✅ FIXED
- **Fix:** Backend validation in `PatchNationRequest` and `PatchSettlementRequest` changed from `le=1.0` to `le=100.0` to match actual data scale (0-100).

### ~~BUG-38: Creature type filter (NPC/Monster) does nothing~~ ✅ FIXED
- **Fix:** 18d569b — Added "monster" filter to `all_creatures` query in entities layer.

---

## HIGH (significant functionality issues)

### ~~BUG-2/5: Join non-existent session navigates to broken game screen~~ ✅ FIXED
- **Fix:** GameScreen watches `wsStatus` and redirects to `/` on `"error"`. User sees "Connection error" toast and lands back on setup screen.

### BUG-12/14/16: Backend event text always in Russian regardless of UI language
- **Repro:** Set UI to English, play game, perform any action.
- **Expected:** Events in English ("You say:", "human says:", "Combat started!", "40ft to the southwest").
- **Actual:** All event text from backend in Russian: "Ты говоришь:", "человек говорит:", "Бой начался!", "40ft на юго-западе".
- **Root cause:** Backend generates localized strings using server-side locale (Russian), ignoring frontend's language preference. The `lang` parameter is sent on session creation but does not affect runtime event generation.
- **Severity:** HIGH — full i18n is broken for game events.

### BUG-7: NPC race displayed in Russian in English UI
- **Repro:** Play in EN, look at Nearby panel.
- **Expected:** "human" next to NPC name.
- **Actual:** "человек" (Russian).
- **Related to:** BUG-12 — same root cause (backend locale).

### BUG-9: ActionBar missing most action buttons in peaceful mode
- **Repro:** Enter game in peaceful mode.
- **Expected per plan:** [Look] [Wait 1h] [End Turn] [Talk] [Go] buttons.
- **Actual:** Only "Wait 1h" button and text command input. No Look, no End Turn, no Go dropdown.
- **Note:** Go works via LocationPanel path buttons, Talk via Nearby. But Look and End Turn are completely missing from ActionBar.

### ~~BUG-30: Spawn Creature type selection ignored~~ ✅ FIXED
- **Fix:** 18d569b — Set `entity_type="monster"` for bare Creatures in `_entity_detail`.

### ~~BUG-37: Blank page on unknown routes (no 404 page)~~ ✅ FIXED
- **Fix:** Added catch-all `<Route path="*">` that redirects to `/`.

### ~~BUG-27: Optimistic UI update without rollback on API error~~ ✅ FIXED
- **Fix:** Added `.catch()` to `saveEdit()` in NationsTable and SettlementsTable — reverts form values to original server data on error.

---

## MEDIUM (UX issues, missing polish)

### BUG-10: EventLog shows "Waiting for events..." with no initial content
- **Repro:** Enter any game session.
- **Expected:** Some initial event or welcome message (e.g. "You arrive at The Salty Anchor").
- **Actual:** "Waiting for events..." until first action is taken. Even after Wait 1h, EventLog doesn't update (only updates on Talk/Combat).

### BUG-13/15: Raw event tags shown in EventLog
- **Repro:** Perform any action that generates events (talk, combat).
- **Expected:** Clean event text without technical tags.
- **Actual:** Shows `[entity_say]`, `[combat_started]`, `[entity_move]`, `[entity_attack]` as visible tags before event text. Should be hidden or formatted as human-readable labels.

### BUG-19/20/21: Battle Map and combat data not updating after player actions
- **Repro:** In combat, use Move toward enemy.
- **Expected:** Battle Map ASCII updates, movement budget decreases, enemy distance updates.
- **Actual:** All three stay unchanged until End Turn. Battle Map, "Movement: 30ft", and "40ft на юго-западе" remain static.
- **Note:** May be same root cause as BUG-17 — player action_result not processed.

### BUG-22: NPC movement spams individual 5ft events
- **Repro:** End Turn while NPC is far away.
- **Expected:** Single event "Marta moves 25ft northeast".
- **Actual:** 5 identical events: "человек перемещается на северо-востоке (5 ft)" x5.
- **Root cause:** Backend emits event per 5ft step, frontend shows all without aggregation.

### ~~BUG-24: Master session list not filtered by selected world~~ ✅ FIXED
- **Fix:** 83411e6 — Added `world_name` to session list API, frontend filters by selected world.

### BUG-25: All settlements show Region = "—"
- **Repro:** Master > World > Settlements table.
- **Expected:** Region column shows associated region.
- **Actual:** All 10 settlements show "—". Region data not populated.
- **Possible cause:** Backend doesn't return region field in settlement data, or frontend doesn't map it.

### ~~BUG-32: Time advance with 0 hours silently uses 1~~ ✅ FIXED
- **Fix:** 83411e6 — Disable Advance button when hours < 1, parse empty input as 0.

### BUG-34: No toast notification on Load save
- **Repro:** Master > Saves > Load any save > confirm.
- **Expected:** Toast "Save loaded" or similar.
- **Actual:** No feedback. Save/Delete show toasts, Load doesn't.

### BUG-35: Long session ID truncated in heading without tooltip
- **Repro:** Master > navigate to session with long ID (e.g. `/master/nonexistent123`).
- **Expected:** Full ID visible or tooltip on hover.
- **Actual:** Heading shows "nonexist" — truncated with no way to see full value.

### BUG-36: Session tabs remain clickable when session not found
- **Repro:** Navigate to `/master/nonexistent123`.
- **Expected:** Tabs disabled or hidden when "Session not found" is shown.
- **Actual:** World/Creatures/Time/Saves tabs all clickable, will trigger API errors.

### ~~BUG-40: Enemy ID and Name swapped in CombatPanel~~ ✅ FIXED
- **Fix:** 18d569b — Show entity description (name) instead of ID in CombatPanel header.

### BUG-41: Header missing game time during combat reconnect
- **Repro:** Join existing session mid-combat via Join Existing Session.
- **Expected:** Header shows time (Y1490 M6 D2 12:03).
- **Actual:** Time element missing from header. Only shows name, HP, location.

---

## LOW (minor UX / cosmetic)

### BUG-6: Raw zod validation messages shown to user
- **Repro:** Character creation form, set HP=0 or STR=31.
- **Expected:** "HP must be at least 1", "STR cannot exceed 30".
- **Actual:** "Too small: expected number to be >=1", "Too big: expected number to be <=30".

### BUG-23: Raw world directory name shown in master panel
- **Repro:** Master > select world.
- **Expected:** Only world name in UI, no internal identifiers.
- **Actual:** Textbox next to dropdown shows "sword_vale" / "arena.yaml" — raw directory/file names.

### BUG-31: Uninformative toast messages for CRUD operations
- **Repro:** Spawn creature, save game.
- **Expected:** "Creature 'Grukk' spawned", "Game saved as 'e2e_test_save'".
- **Actual:** "Spawn Creature", "Saved." — generic.

### BUG-33: Save name textbox not cleared after successful save
- **Repro:** Master > Saves > enter name > Save.
- **Expected:** Textbox clears after save.
- **Actual:** Previous save name remains in textbox.

### ~~BUG-46: cursor:pointer on world card body but click does nothing~~ ✅ FIXED
- **Fix:** 83411e6 — Removed misleading `cursor-pointer` from world cards.

---

## Not Verified (could not test)

- **Keyboard shortcuts** (Escape to close modal) — spawning dialog was tested, but Escape not explicitly verified.
- **Mobile/responsive** — tested desktop only.
- **WS reconnect with backoff** — would need to simulate network interruption.
- **Delete session from master** — not tested (delete button exists but wasn't clicked to preserve test data).
- **Settlement edit** — not tested (likely same 422 issue as nations).
- **Blood Arena world** — not tested as player.
- **Concurrent users** — not tested.

---

## Infrastructure fixes (uncommitted)

### WebSocket deadlock — Round lifecycle refactored into GameSession
- **Problem:** WS connections would hang (handshake timeout). Root cause: `add_listener` replayed `last_turn_msg` by calling `listener.on_turn()` which used `asyncio.run_coroutine_threadsafe()` + `future.result(timeout=30)` from the event loop thread — deadlock.
- **Fix:** Round lifecycle moved from `routes_ws.py` into `GameSession` (`service/session.py`). Replay moved to WS handler using `await ws.send_json()`. `SessionEventListener` protocol decouples transport from game logic.
- **Side effect:** Old static debug UI (HTML/JS/CSS) removed — React frontend is the only UI now.

### Legacy static UI removed
- All files under `adapters/api/static/` deleted (index.html, player.html, master.html, css/, js/, locales/).
- `app.py` mounts only `frontend/dist` if it exists.

---

## Summary

| Severity | Count | Fixed |
|----------|-------|-------|
| CRITICAL | 4     | 4     |
| HIGH     | 7     | 5     |
| MEDIUM   | 12    | 3     |
| LOW      | 5     | 1     |
| **Total**| **28**| **13**|

**Fixed:** BUG-43, BUG-38, BUG-30, BUG-40, BUG-24, BUG-32, BUG-46, BUG-17, BUG-26, BUG-2/5, BUG-27, BUG-37 + WS deadlock.

Top remaining priorities:
1. **BUG-12** — Backend events always in Russian (i18n ignored at runtime)
2. **BUG-2/5** — Join non-existent session navigates to broken game screen
3. **BUG-9** — ActionBar missing most action buttons in peaceful mode
