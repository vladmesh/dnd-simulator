# Task: Service mixin Protocol base

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 4 — Architecture Violations + Type Safety

## Description

The 4 service mixin classes (`SaveCommands`, `CreatureCommands`, `TimeCommands`, `PoliticsCommands`) access parent attributes (`_get_session`, `_store`, `_sessions`, `_brain_factory`, `_get_entities_layer`, etc.) with no declared contract. Every access has `# type: ignore[attr-defined]` — 24 total.

Create a `GameServiceProtocol` (Protocol or ABC) in `service/` that declares all shared attributes the mixins need. Each mixin inherits from it. `GameService` still inherits all mixins and satisfies the protocol by providing the real implementations.

The 3 `type: ignore[arg-type]` in `llm/client.py` are OpenRouter SDK stub mismatches — out of scope.

## Tests First

- **mypy strict passes with zero `type: ignore[attr-defined]`** in `service/commands_*.py` — this is the primary acceptance check.
- Unit test: instantiate `GameService`, call a method from each mixin (`save_game`, `list_creatures`, `advance_time`, a politics method) — verify no runtime errors from the new inheritance chain.

## Implementation

1. Create `service/base.py` with a Protocol or ABC declaring: `_get_session(session_id: str) -> GameSession`, `_store: SaveStore`, `_sessions: dict[str, GameSession]`, `_brain_factory: BrainFactory`, `_get_entities_layer(session: GameSession) -> EntitiesLayer`, `_get_politics_layer(...)`, `_get_settlements_layer(...)`.
2. Each mixin class inherits from this base.
3. Remove all `type: ignore[attr-defined]` from the 4 mixin files.
4. `GameService` keeps its current MRO — mixins + the base protocol.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Zero `type: ignore[attr-defined]` in `service/commands_*.py`
- [ ] `make typecheck` passes

## Status

`done`

## Developer Notes

Created `service/base.py` with `GameServiceProtocol` (a `typing.Protocol`) declaring all shared attributes: `_store`, `_sessions`, `_brain_factory`, `_get_session()`, `_get_entities_layer()`, `_get_politics_layer()`, `_get_settlements_layer()`. Each mixin now inherits from it. Removed the `NotImplementedError` stubs from `CreatureCommands` and `PoliticsCommands` since the Protocol declares those methods. Removed all 24 `type: ignore[attr-defined]` comments and 3 now-unused imports that ruff flagged.
