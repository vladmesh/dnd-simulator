# Task: BrainType(StrEnum) — typed `ai_type` field + factory dispatch

**Date:** 2026-04-13
**Sprint:** 016-tech-sweep
**Phase:** 4 — Enums & Fail-Fast

## Description

Replace `ai_type: str` with `ai_type: BrainType` on Npc and in BrainFactory.

- `src/dnd_simulator/layers/entities/models.py:48` — `ai_type: str = "rule_based"` → `BrainType = BrainType.RULE_BASED`.
- `src/dnd_simulator/service/brain_factory.py:20-39` — `create(ai_type: str)` → `create(ai_type: BrainType)`. Replace `if ai_type == "rule_based"` / `"llm"` chain with `match` on the enum. Drop the `ValueError(f"Unknown ai_type: ...")` branch — enum constructor already rejects unknowns.

Define `BrainType(StrEnum)` in `core/brain.py` (next to `Brain` ABC) with members `RULE_BASED = "rule_based"`, `LLM = "llm"`. Rationale: brain module owns brain taxonomy.

YAML / save data still carries the strings `"rule_based"` / `"llm"`. Parsing path must call `BrainType(value)` which fails-fast on unknown values.

## Tests First

- Integration: load a world with one NPC using `ai: rule_based` and one using `ai: llm` (no LLM configured → falls back to RuleBrain per existing behavior). Both assigned brains behave correctly on a test turn.
- Unit: `BrainFactory.create(BrainType.RULE_BASED)` returns `RuleBrain`.
- Unit: `BrainFactory.create(BrainType.LLM, strict=True)` with `llm=None` raises `ValueError` with "LLM not configured".
- Unit: YAML/save data with `ai_type: "garbage"` raises `ValueError` at parse time (fail-fast), not at brain creation time.

## Implementation

1. Add `BrainType(StrEnum)` to `core/brain.py`.
2. Change `Npc.ai_type` type annotation + default to enum.
3. Update NPC parser (`content_loader/...`) to wrap raw string via `BrainType(...)`.
4. Update `BrainFactory.create` signature + body; drop manual "unknown" branch.
5. Update all callers (search for `ai_type=` and `"rule_based"` / `"llm"` literals in service/).
6. Save/load: since StrEnum serializes as its string value, on-disk format unchanged. Load wraps via `BrainType(...)`.

## Acceptance Criteria

- [ ] Tests written and RED before implementation
- [ ] `grep -rn '"rule_based"\|"llm"' src/dnd_simulator/` returns nothing except the enum definition and docstrings
- [ ] Unknown `ai_type` in YAML raises at parse time
- [ ] `make check` passes
- [ ] Existing NPCs still load with correct brain

## Status

`done`

## Developer Notes

- `BrainType(StrEnum)` added to `core/brain.py`.
- Typed `Npc.ai_type`, `NpcContent.ai`, `BrainFactory.create`, `SetBrainRequest.type`, `SpawnCreatureRequest.ai` as `BrainType`.
- `BrainFactory.create` rewritten with `match` on the enum; dropped the "Unknown ai_type" branch — `BrainType(value)` (or Pydantic's enum validation) fails fast at parse/load time instead.
- Save/load path in `EntitiesLayer.load_state` wraps the restored string via `BrainType(...)`.
- Pre-existing test `test_paladin_infra.py` passed `"ai": "rule"` — a silent typo the old `str` field accepted. Fixed to `"rule_based"`; this is exactly the fail-fast the task targeted.
- StrEnum means on-disk JSON format is unchanged (`"rule_based"` / `"llm"` strings), so save compatibility is preserved.
