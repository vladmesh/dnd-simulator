# Task: Reaction Infrastructure — Triggers + Brain.choose_reaction

**Date:** 2026-03-30
**Sprint:** 012-reactions-oa
**Phase:** 1 — Reaction Infrastructure + OA Mechanics

## Description

Build the reaction system's type foundation and the Brain interface for reactions. This is the generic infrastructure — not OA-specific. Any future reaction (Counterspell, Shield, Ready) will use the same trigger/choose_reaction pathway.

### Concrete changes

- `core/reactions.py` — new module:
  - `TriggerType(StrEnum)`: `LEAVING_REACH` (for OA). Extensible for future `SPELL_CAST`, `BEING_ATTACKED`.
  - `ReactionTrigger(frozen dataclass)`: `trigger_type: TriggerType`, `source_creature_id: str`, `data: dict[str, object]` (e.g. `{"mover_id": "...", "from_pos": (x,y), "to_pos": (x,y)}`).
  - `ReactionOption(frozen dataclass)`: `action_type: ActionType`, `description: str`, `params: dict[str, object]` — what the creature CAN do as a reaction. Pre-built by the caller (Round), not by the brain.
- `Brain.choose_reaction(creature, trigger, options: list[ReactionOption]) -> Action` — new abstract method. Default implementation returns `Action(ActionType.SKIP)`. Subclasses override.
  - `RuleBrain`: deterministic — for `LEAVING_REACH`, always attack if an OA option is present.
  - `LlmBrain`: LLM call with reaction-specific tool schema (options converted to tools). One call, no retry loop.
  - `PlayerBrain`: same queue+callback pattern as `choose_action`. New callback `_on_reaction: OnReactionCallback | None`, new `submit_reaction(action)` method, `choose_reaction` fires callback and blocks on queue.
- `llm/tools.py` — `get_reaction_tools(options: list[ReactionOption]) -> list[dict]` — builds tool schema from ReactionOption list. Simpler than action tools — no param introspection, just option descriptions.

## Tests First

Scenarios (in `tests/unit/test_reaction_infrastructure.py`):

1. **ReactionTrigger construction.** Build a LEAVING_REACH trigger with source creature ID and position data. Verify fields, immutability.
2. **RuleBrain.choose_reaction returns OA for LEAVING_REACH.** Give RuleBrain a LEAVING_REACH trigger with an OPPORTUNITY_ATTACK option — it picks the attack. Give it a trigger with only SKIP-equivalent options — it skips.
3. **RuleBrain.choose_reaction skips for unknown trigger types.** If we add a future trigger type that RuleBrain doesn't handle, it should skip (default safe behavior).
4. **LlmBrain.choose_reaction calls LLM with reaction tools.** Mock LlmClient. Verify it builds correct tool schema from ReactionOptions and returns the LLM's chosen action. Verify it returns SKIP if LLM returns no tool call.
5. **PlayerBrain.choose_reaction fires callback and blocks.** Create PlayerBrain, set on_reaction callback. Call choose_reaction in a thread. Verify callback fires with trigger info. Submit a reaction — verify choose_reaction returns it.
6. **Brain ABC default choose_reaction returns SKIP.** A minimal Brain subclass that only implements choose_action — calling choose_reaction returns SKIP (safe default for brains that don't support reactions yet).

## Implementation

1. Create `core/reactions.py` with `TriggerType`, `ReactionTrigger`, `ReactionOption`.
2. Add `choose_reaction` to Brain ABC with default SKIP implementation.
3. Implement in RuleBrain, LlmBrain, PlayerBrain.
4. Add `get_reaction_tools()` to `llm/tools.py`.
5. Add `_on_reaction` callback + `submit_reaction` to PlayerBrain.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] All three brains implement choose_reaction
- [ ] PlayerBrain reaction follows same queue+callback pattern as choose_action
- [ ] LLM tool schema correctly represents reaction options
- [ ] Brain ABC default returns SKIP (no forced override for future brain types)

## Status

`pending`
