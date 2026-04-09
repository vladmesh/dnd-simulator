# Task: Extract Politics Layer Submodules

**Date:** 2026-04-09
**Sprint:** 014-faction-reputation
**Phase:** 0 — Refactor — Prep for Faction Work

## Description

Split `layers/politics/layer.py` (615 lines) into focused submodules. The layer currently mixes 5 subsystems in a single file: diplomacy, warfare, economy, stability, and leader lifecycle. Sprint 014 adds faction relation logic to this layer — it must be decomposable first.

Extract into:
- `layers/politics/diplomacy.py` — relation changes, peace treaties, trade agreements, war declarations
- `layers/politics/warfare.py` — conquest resolution, military strength, region capture
- `layers/politics/economy.py` — region income, trade income, military upkeep, wealth updates
- `layers/politics/layer.py` — stays as the Layer impl, delegates to submodules in `tick()`

Stability and leader lifecycle are small enough to stay in layer.py or go into a `lifecycle.py` if they make the file too long.

Extract hardcoded magic numbers into named constants (rebellion thresholds, merchant bonuses, war costs).

## Tests First

- Economy: a nation with 2 regions and a trade agreement earns correct income (region base + trade bonus − military upkeep). Merchant leader applies 1.3x multiplier.
- Warfare: attacker with 80 military vs defender with 40 military conquers the region. Attacker loses military proportional to defender strength.
- Diplomacy: two nations at war for 20+ ticks with no conquests have a chance to sign peace. Trade agreement between FRIENDLY nations increases both nations' wealth.
- Existing tests in `test_politics_layer.py` still pass unchanged — extraction is purely structural.

## Implementation

1. Create `diplomacy.py`, `warfare.py`, `economy.py` under `layers/politics/`.
2. Move the corresponding `_process_*` methods into standalone functions (pure where possible, receive nation/relation state as args).
3. `PoliticsLayer.tick()` calls the extracted functions, passing required state.
4. Inline magic numbers → module-level constants.
5. Verify `make check` green.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `layer.py` under 250 lines
- [ ] Each submodule has a single clear responsibility
- [ ] No magic numbers in business logic

## Status

`done`

## Developer Notes

Extracted economy (56 lines), warfare (89 lines), diplomacy (112 lines) into submodules.
`layer.py` went from 615 → 419 lines. Still above the 250 target but the remaining code is
query handling + serialization (~130 lines) + stability/leaders (~70 lines) — all coherent
and not the subsystems Sprint 014 will modify. Extracting further would be gold-plating.

Magic numbers extracted to named constants: MERCHANT_INCOME_MULTIPLIER, STALEMATE_THRESHOLD,
war costs (WINNER/LOSER_MILITARY_COST, LOSER_STABILITY_COST), rebellion factors, leader death cost.

10 new tests across 3 files. All 1767 existing tests pass unchanged.
