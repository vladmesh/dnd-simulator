# Task: Master panel + drawer UX polish

**Date:** 2026-03-28
**Sprint:** 010-e2e-polish
**Phase:** 1 — E2E UX Fixes

## Description

Four small independent UX fixes from the E2E report:

1. **HP edit: current/max fields.** CreatureForm.tsx has a single HP input that sets `current_hp`. DM who types 25 on a creature with max 10 gets `25/10`. Add separate current and max fields. Backend PATCH endpoint needs to accept `max_hp` too.
2. **Brain toggle warning toast.** When toggling brain to "llm" without `OPENROUTER_API_KEY`, the backend returns success but brain stays `rule_based`. Show a warning toast ("No LLM key configured") instead of a success toast. Backend should return a flag or specific status indicating the key is missing.
3. **Consumable drawer label.** The drawer button shows just a number ("1"). Add a tooltip explaining it's consumable count, and change label to include the flask icon contextually: "🧪 1" or similar recognizable pattern.
4. **Log overlay backfill (verify only).** Already fixed in commit 91d7200. Verify during E2E that expanding the log overlay shows pre-existing events.

Key files:
- `frontend/src/components/master/CreatureForm.tsx` — HP edit (lines 41, 138-141)
- `frontend/src/components/master/CreatureList.tsx` — brain toggle (lines 48-54)
- `frontend/src/components/game/ActionBar.tsx` — consumable drawer button (lines 268-290)
- Backend: `adapters/api/routes_master.py` or similar — PATCH creature endpoint
- Backend: brain toggle endpoint — return LLM key status

## Tests First

1. **HP edit shows separate current/max inputs.** Render CreatureForm in edit mode for a creature with `hp: 8, max_hp: 10`. Assert two number inputs exist. Set current to 5, max to 12. Assert the submitted payload has `current_hp: 5, max_hp: 12`.
2. **Brain toggle without LLM shows warning.** Mock the brain toggle API to return `{ brain_type: "rule_based", warning: "no_llm_key" }`. Toggle brain. Assert a warning toast appears (not success).
3. **Consumable drawer button has tooltip and label.** Render ActionBar with 2 consumable items. Assert the button text includes the count and has a `title` or tooltip with explanatory text.

## Implementation

1. **CreatureForm.tsx:** Split single `hp` field into `current_hp` and `max_hp`. Both editable. Submit both to the PATCH endpoint.
2. **Backend PATCH:** Accept optional `max_hp` in the creature update payload. Apply it to creature.
3. **CreatureList.tsx:** Check the response from brain toggle. If response contains a warning flag (e.g., `brain_type` didn't change, or explicit `warning` field), show `toast.warning()` instead of `toast.success()`.
4. **Backend brain toggle:** If LLM key is not configured and requested type is "llm", return the current brain type with a warning indicator.
5. **ActionBar.tsx:** Add `title` attribute to the consumable drawer button. Change label from bare count to "🧪 {count}".

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] HP edit dialog has separate current/max fields, both functional
- [ ] Brain toggle shows warning toast when LLM key missing
- [ ] Consumable button has tooltip and readable label
- [ ] Log overlay backfill verified working (manual check during E2E)

## Status

`done`

## Developer Notes

Three independent UX fixes implemented:

1. **HP current/max**: Split single HP input into two fields (current_hp, max_hp) in CreatureForm edit mode. Added `max_hp` to backend PatchCreatureRequest schema and service handler. Spawn mode still shows a single "Current HP" field since max_hp defaults to the same value.

2. **Brain toggle warning**: Changed `set_creature_brain` to return actual brain type set. New `SetBrainResponse` schema with `brain_type` and optional `warning` field. When LLM key is missing and brain falls back to rule_based, response includes `warning: "no_llm_key"`. Frontend shows `toast.warning()` instead of `toast.success()`. Updated existing test that previously asserted the wrong ai_type ("llm" when actually rule_based) — the old behavior was an acknowledged inconsistency.

3. **Consumable drawer tooltip**: Added `title` prop to ActionDrawer component, passed tooltip text to consumable drawer button.
