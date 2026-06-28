# Task: Adapter hygiene — action parsing + public World query API

**Date:** 2026-06-28
**Sprint:** 019-control-plane-prep
**Phase:** 2 — GameService deeper peel + adapter hygiene

## Description

Two concrete coupling fixes plus a backlog reconcile. Pragmatic scope (per planning
decision): only remove genuinely-removable core imports; enum-at-boundary in Pydantic
schemas stays.

### A. `action-parsing-in-adapter`

`routes_ws.py` builds `Action(name=ActionType(...), params=...)` from the raw JSON
message inline (lines ~162–179), the only reason it imports `Action, ActionType` from
core. Move the parse into the service layer.

- Add `service/action_parsing.py` with a pure function:
  `parse_action(raw: dict[str, object], *, default_name: str) -> Action` that builds the
  `Action`, defaulting the name (`"idle"` for actions, `"skip"` for reactions), and
  raises a typed `ActionParseError` (new, carries the offending name) when the name is
  not a valid `ActionType`.
  - Put it in a new module, NOT in `session.py` — session.py is already 536 lines and
    flagged for growth (`long-func-start-round`).
- `routes_ws.py`: import only `parse_action` / `ActionParseError` from the service. Drop
  the `from dnd_simulator.core.action import Action, ActionType` import. Keep the i18n
  error replies in the adapter — catch `ActionParseError` and send the existing
  `_("Unknown action: {}")` / `_("Unknown reaction: {}")` messages with `err.name`.

### B. `world-private-method-access`

`world._make_query_fn()` / `_make_emit_fn()` are called from outside `World`
(`round.py` ×4, `session.py` ×1). Promote them to public API.

- Rename `World._make_query_fn` → `make_query_fn` and `World._make_emit_fn` →
  `make_emit_fn`. Update World's own internal callers (in `_propagate_events`, layer
  init) and the external callers in `round.py` (lines ~521, 563) and `session.py`
  (line ~374). No signature or behavior change — just the public name.

### C. Backlog reconcile

In `docs/BACKLOG.md`, mark resolved with rationale:
- `action-parsing-in-adapter` → `[x]` (moved to service in A).
- `world-private-method-access` → `[x]` (public API in B).
- `adapter-imports-core-directly` → `[x]` with note: the old `PlayerCharacter/Ability/
  Query/QueryType` adapter imports are already gone (routes_master split in Sprint 016);
  the `Action/ActionType` import is removed by A. The remaining `BrainType` /
  `FightingStyle` imports are enum-at-boundary in Pydantic schemas — accepted (audit
  2026-06-28 reports 0 architecture violations; adapters may import enums).

## Tests First

- **Action parsing (new unit test `tests/unit/test_action_parsing.py`):** describe the
  boundary behavior, not the implementation.
  - A raw message `{"name": "attack", "params": {"target_id": "x"}}` parses to an
    `Action` with `name == ActionType.ATTACK` and the params passed through.
  - A raw message with no `name` and `default_name="idle"` parses to an idle `Action`;
    with `default_name="skip"` parses to a skip `Action`.
  - A raw message `{"name": "not_a_real_action"}` raises `ActionParseError` whose `.name`
    is `"not_a_real_action"` (so the adapter can echo it in the i18n reply).
- **World public API:** the rename is guarded by the existing round/session suite
  (`test_game_loop.py`, `test_session_lifecycle.py`, integration round tests). Confirm
  green before and after; no new test needed for a rename.

## Implementation

1. Create `service/action_parsing.py` (`ActionParseError` + `parse_action`). Add the unit test, watch it pass.
2. Rewire `routes_ws.py` to use it; remove the core `Action/ActionType` import.
3. Rename the two `World` methods + update all 7 call sites (world.py internal, round.py,
   session.py).
4. Reconcile `docs/BACKLOG.md`.
5. `make check` + `make test-integration` (WS round-trip + round lifecycle touch both
   changes) → log to file per CLAUDE.md.

## Acceptance Criteria

- [ ] `parse_action` / `ActionParseError` in `service/action_parsing.py`; unit test green
- [ ] `routes_ws.py` no longer imports `Action`/`ActionType` from core; WS action +
      reaction submit still work; unknown-name still returns the i18n error reply
- [ ] `World.make_query_fn` / `make_emit_fn` public; no remaining `_make_query_fn` /
      `_make_emit_fn` references (`grep` clean)
- [ ] Three backlog items marked `[x]` with rationale
- [ ] `make check` green, integration green, mypy strict clean

## Status

`done`

## Developer Notes

Done as planned, all three parts.

- **A (action parsing):** `service/action_parsing.py` — `parse_action(raw, *, default_name)` +
  `ActionParseError(ValueError)` carrying `.name`. Added a non-dict `params` guard (falls back to
  `{}`) so a malformed `params` field can't break the frozen `Action`; not in the plan but cheap and
  defensive. `routes_ws.py` now imports only the service symbols and keeps both i18n replies
  (`Unknown action` / `Unknown reaction`) via `err.name`. 5 unit tests in `test_action_parsing.py`.
- **B (World public API):** plain rename `_make_query_fn`→`make_query_fn`, `_make_emit_fn`→`make_emit_fn`.
  src call sites: world.py (4 internal), round.py (×4), session.py (×1) — all updated, grep clean in src.
- **Old tests:** the rename is an intentional contract change, so I updated the 7 test modules that
  call the method on a real/mocked `world` (test_world, test_multi_action, test_dead_creature_mid_turn,
  test_time_of_day_encounters, test_region_encounters, test_session_round_state, test_turn_budget_on_creature).
  Left untouched: `test_auto_hostility.py`, `test_wire_sides_combat.py`, `test_settlements_layer.py` —
  each defines its own unrelated module-level `def _make_query_fn(...)` helper (faction/weather query
  builder, bare calls, nothing to do with `World`). Renaming those would be scope creep, so the grep
  for `_make_query_fn` is intentionally non-empty in those three files only.
- **C:** three backlog items marked `[x]` with rationale.

`make check` green (ruff/format/mypy clean, 2273 backend + 238 frontend). Integration 154/154 — the WS
`test_invalid_action_name` / `test_unknown_message_type` paths exercise the new parser.
