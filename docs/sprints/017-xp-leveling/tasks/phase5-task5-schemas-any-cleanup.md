# Task: schemas.py Any → object/typed

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 5 — Post-audit cleanup

## Description

`content_loader/schemas.py` uses `Any` in 4 spots, all framework-shaped:

- `:40` `_coerce_localized_text(v: Any) -> dict[str, str]` — Pydantic validator input
- `:96` `_coerce_ability_scores(v: Any) -> AbilityScoresContent` — Pydantic validator input
- `:212` `model_post_init(self, _context: Any) -> None`
- `:340` `model_post_init(self, __context: Any) -> None`

CLAUDE.md prefers `object` over `Any` for strict mypy. Pydantic accepts `object` here for both validators (still need `isinstance` checks at runtime — already present) and `model_post_init` (Pydantic types it as `Any | None` but `object` is a strict subtype that mypy and Pydantic both accept).

## Tests First

No new tests — this is a typing change. Verification:

- `make typecheck` (mypy) passes after the change.
- `make test` passes — runtime behavior identical (all four sites use `isinstance` before downcasting).

## Implementation

1. Replace `Any` with `object` at the four sites.
2. Drop the `from typing import Any` import if it becomes unused.
3. Run `make check` and confirm green.

If Pydantic complains about `model_post_init` signature mismatch (it requires `Any` per its protocol), revert that pair and document with a one-line `# noqa` or comment. Validators (`v: Any`) are the higher-value change anyway.

## Acceptance Criteria

- [ ] `Any` removed from at least the two validator signatures (lines 40, 96)
- [ ] `model_post_init` signatures changed if Pydantic accepts `object` (verify by running typecheck)
- [ ] `make check` clean — no mypy regressions, no test failures
- [ ] Import of `Any` removed if no longer used

## Status

`done`

## Developer Notes

Replaced `Any` with `object` at all four target sites (lines 40, 96, 212, 340): both `BeforeValidator` callbacks and both `model_post_init` methods. Pydantic accepts `object` for `model_post_init` without complaint. `from typing import Any` import kept — still needed by out-of-scope uses at lines 152, 396, 427 (`modifiers`, `class_features` dicts, which hold heterogeneous content and weren't listed in task scope). `make check` green (2174 py + 238 fe), no mypy regressions.
