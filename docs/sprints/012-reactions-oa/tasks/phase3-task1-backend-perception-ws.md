# Task: Backend — Perception Handlers + WS Reaction Wiring

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 3 — Frontend + Content

## Description

Two backend gaps blocking the frontend:

1. **Perception handlers** for `OPPORTUNITY_ATTACK` and `ENTITY_DISENGAGE` — currently fall through to "Something happened (…)" fallback. OA is tricky: the handler emits `ENTITY_ATTACK` first (with full roll data), then `OPPORTUNITY_ATTACK` (minimal marker). To get "X attacks Y (opportunity attack) [d20…]" in one line, add `is_opportunity_attack: True` to the `ENTITY_ATTACK` event data in `handle_opportunity_attack`, and modify `_perceive_attack` to append "(opportunity attack)" when that flag is set. The separate `OPPORTUNITY_ATTACK` perception handler should be a brief contextual note ("X seizes the opening!") or suppressed if redundant. `ENTITY_DISENGAGE` is simple: "X disengages."

2. **WS reaction wiring** — `PlayerBrain.choose_reaction` has `_on_reaction` callback + queue ready, but `GameSession.start_round()` doesn't wire it. Need: `on_reaction` closure (like `on_turn`) that builds a `reaction_prompt` message with trigger info and options, `SessionEventListener.on_reaction` protocol method, `WsEventListener.on_reaction` implementation, `"reaction"` message type handler in WS endpoint that calls `session.submit_player_reaction()`, and `submit_player_reaction` method on `GameSession`. After wiring, remove the auto-SKIP fallback in `PlayerBrain.choose_reaction` (line ~382).

## Tests First

**Perception tests** (unit, in `tests/unit/test_perception.py`):
- OA event: creature A attacks creature B as opportunity attack → observer sees text containing attacker name, target name, "(opportunity attack)", and roll details (d20, total, AC)
- Disengage event: creature A disengages → observer sees text with creature name and "disengage" concept
- Regular attack still works without "(opportunity attack)" annotation when `is_opportunity_attack` flag is absent

**WS reaction wiring tests** (unit):
- `GameSession.submit_player_reaction(action)` puts action on `PlayerBrain._reaction_queue`
- When `PlayerBrain.choose_reaction` is called with `_on_reaction` wired, it fires the callback with creature, trigger, and options — does NOT auto-skip
- Reaction prompt message has correct structure: `type: "reaction_prompt"`, trigger info, options list
- WS endpoint routes `{"type": "reaction", "name": "opportunity_attack", "params": {"target_id": "x"}}` to `submit_player_reaction`
- WS endpoint routes `{"type": "reaction", "name": "skip"}` to `submit_player_reaction`

## Implementation

1. **`rules/handlers/reactions.py`** — add `"is_opportunity_attack": True` to the ENTITY_ATTACK event data dict
2. **`layers/entities/perception.py`** — modify `_perceive_attack` to check `data.get("is_opportunity_attack")` and append "(opportunity attack)". Add `_perceive_disengage` handler. Add `_perceive_opportunity_attack` handler (brief or no-op if redundant with annotated attack).
3. **`service/session.py`** — add `on_reaction` closure in `start_round()`, call `brain.set_on_reaction(on_reaction)`. Add `submit_player_reaction` method. Add `on_reaction` to `SessionEventListener` protocol.
4. **`adapters/api/routes_ws.py`** — add `msg_type == "reaction"` branch, add `on_reaction` to `WsEventListener`.
5. **`core/brain.py`** — remove auto-SKIP fallback from `PlayerBrain.choose_reaction` (the `else` branch).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] OA appears in combat log as annotated attack, not "Something happened"
- [ ] Disengage appears in combat log as readable text
- [ ] WS reaction prompt flows end-to-end: Round → PlayerBrain → callback → WS → client

## Status

`done`

## Developer Notes

All changes straightforward, no deviations from plan:
- Added `is_opportunity_attack: True` flag to ENTITY_ATTACK event data in `handle_opportunity_attack`
- `_perceive_attack` annotates with "(opportunity attack)" when flag present
- `_perceive_disengage` and `_perceive_opportunity_attack` handlers added
- PlayerBrain.choose_reaction now raises RuntimeError if `_on_reaction` not wired (was auto-SKIP)
- GameSession wires `on_reaction` callback in `start_round()`, adds `submit_player_reaction`
- SessionEventListener protocol extended with `on_reaction`
- WsEventListener and WS endpoint handle `"reaction"` message type
- `_reaction_to_dict` serializes trigger + options for the client
