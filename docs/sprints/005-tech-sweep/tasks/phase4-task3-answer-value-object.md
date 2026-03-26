# Task: Answer.value Any → object

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 4 — Architecture Violations + Type Safety

## Description

`Answer.value` is typed `Any`, which disables type checking at all ~7 consumer sites. Change it to `object` so mypy forces explicit `isinstance` checks or casts before use.

`Query.params: dict[str, Any]` stays as-is — it's caller-constructed plumbing where `object` would add noise without safety.

Scope: ~33 producer sites (layers returning `Answer`) need no changes (everything is already a valid `object`). ~7 consumer sites need explicit isinstance/cast where they don't already have one.

## Tests First

- `make typecheck` is the primary test — it must pass with `Answer.value: object` and no new `type: ignore` comments.
- Verify each consumer site handles the type correctly: write a unit test that creates an `Answer(value=...)` with each actual return type used in the codebase (str, dict, list, bool, int, None) and confirms the consumer logic works after casting.

## Implementation

1. Change `Answer.value: Any` to `Answer.value: object` in `core/models.py`.
2. Run `make typecheck` — it will flag all consumer sites that use `.value` without narrowing.
3. Fix each site: add `isinstance` check or `cast()` as appropriate. Most consumers already do isinstance checks (awareness_builder, activation_manager) — verify those satisfy mypy. Fix the ones that don't.
4. Remove the `Any` import from `core/models.py` if no longer needed.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `Answer.value` typed as `object`, not `Any`
- [ ] Zero new `type: ignore` comments added
- [ ] `make typecheck` passes

## Status

`done`

## Developer Notes

Changed `Answer.value: Any` to `Answer.value: object` in `core/models.py`. Fixed 14 mypy errors across 5 files: `commands_creatures.py` (assert isinstance for list/dict), `routes_master.py` (assert isinstance for all query results), `settlements/layer.py` (isinstance checks for weather dict and nation dict), `awareness_builder.py` (isinstance for settlements list), `activation_manager.py` (assert isinstance for squad list). Zero new `type: ignore` comments. `session.py` consumer sites already had isinstance checks and needed no changes.
