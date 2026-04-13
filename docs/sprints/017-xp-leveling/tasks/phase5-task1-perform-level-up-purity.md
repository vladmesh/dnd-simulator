# Task: perform_level_up purity

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 5 — Post-audit cleanup

## Description

`rules/perform_level_up.py:28` mutates `Character` in-place. `rules/` are pure functions by contract — this is the second non-pure rules function (the other is documented). Two valid resolutions:

- **A** — refactor to return a new `Character` (or a dataclass of deltas) and let the caller in `service` apply it.
- **B** — keep the in-place mutation, document explicitly as a stateful operation, and pin the contract with a test that asserts identity (caller still sees the same Character object).

`Character` is a mutable dataclass already (HP, level, equipment all mutate during play), so a full `replace()` rewrite is invasive — option B is the realistic choice. Document the exception, add a docstring noting "this is the only mutation entry-point for level-up", and add a regression test.

## Tests First

Behavioural test in `tests/unit/test_rules_perform_level_up_purity.py`:

- A Fighter at L1 with `level_up_available=True`, called via `perform_level_up(c, fighting_style=None)`, returns `None` (the function does not return a new object) AND the same `Character` instance now reports `level=2`.
- After the call, `level_up_available` is False on the same instance.
- A second call without resetting the flag raises `ValueError("No level-up available")`.

These tests pin the in-place contract so a future "refactor to return new" doesn't silently break callers.

## Implementation

1. Update the docstring of `perform_level_up` to call out: "Mutates `character` in-place. This is an explicit exception to the rules/ purity rule — level-up is the canonical mutation point for class progression." Add a one-line `# noqa: <none-needed>` comment is not required; just the docstring.
2. Add the test file above.
3. No code change to the function itself unless the user prefers option A.

## Acceptance Criteria

- [ ] Tests written and RED initially (purity test fails if function returns a copy)
- [ ] Implementation makes tests GREEN (docstring update only)
- [ ] Existing tests still pass (`make check`)
- [ ] Docstring on `perform_level_up` explicitly notes the in-place contract

## Status

`done`

## Developer Notes

Went with option B as the task recommended. Updated module docstring and function docstring on `perform_level_up` to explicitly note the in-place contract and why `rules/` purity is waived here. Added `tests/unit/test_rules_perform_level_up_purity.py` with three regression pins (returns None + mutates same instance, flag cleared, second call raises). Tests passed immediately — they are regression pins for the current contract, not failing specs awaiting implementation; the task acceptance criterion anticipated this ("Implementation makes tests GREEN (docstring update only)"). Full `make check` passed (2138 py + 238 fe).
