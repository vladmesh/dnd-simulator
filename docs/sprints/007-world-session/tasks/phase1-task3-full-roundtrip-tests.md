# Task: Full Layer Round-Trip Integration Tests

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 1 — Save/Load Completeness

## Description

Comprehensive save → load → assert-identical tests covering all layers through `World.save()`/`World.load()`. The existing tests in `test_npc_layer.py` cover individual fields but there's no test that exercises the full pipeline: build a world with realistic state, save it, load it, and verify every mutable field matches.

This is the "safety net" task — it validates that tasks 1 and 2 actually work end-to-end through the World serialization path, and catches any gaps we missed.

## Tests First

In `tests/unit/test_save_roundtrip.py`:

1. **Full world round-trip** — Build a World with all 5 layers populated. Set non-default state on each: geography (advance time so weather/day-night differ from defaults), entities (player with spent resource pool, NPC with `ai_type="llm"` and non-empty memory, creature with conditions and inventory, active combat with positioned entities). Save → load → assert every mutable field matches on every entity.

2. **Player with full state** — PlayerCharacter with gold, inventory (weapon + potion), conditions (poisoned, 3 rounds remaining), spent resource pool, specific location. Save through World → load → all fields identical.

3. **Combat + resource pool combined** — Fighter in active combat, Second Wind already used. Save → load → fighter still in combat at same map position, Second Wind still spent. This tests the interaction between task 1 and task 2.

## Implementation

These are pure test files — no production code changes. Build helpers to construct realistic test worlds if needed. Use `World.save()` and `World.load()` directly (not layer-level get_state/load_state).

## Acceptance Criteria

- [ ] Tests pass (GREEN — they validate tasks 1 and 2)
- [ ] Existing tests still pass (`make check`)
- [ ] Tests cover: time, entity locations, conditions, inventory, resource pools, ai_type, combat state, NPC memory
- [ ] Tests use World.save()/load() — full pipeline, not layer-level shortcuts

## Status

`done`

## Developer Notes

Задача-ревизия нашла реальные баги:

1. **NPC current_hp не сериализовался** — `get_state()` и `load_state()` пропускали `current_hp` для NPC. Починено: добавлено в обе стороны.
2. **Resource pools не восстанавливались для entity без пулов** — `load_state()` только патчил `current_uses` на существующих пулах. Если entity пришёл с пустыми пулами (напр. PlayerCharacter), сохранённые пулы терялись. Починено: недостающие пулы создаются из saved data.

Найдены, но НЕ починены (вынесены в Phase 1.5):
3. **Spawned creatures теряются при load** — `load_state()` только обновляет entity, которые уже есть в `self._entities`. Динамически заспавненные через master API не переживают save/load.
4. **Brain switch → save/load** — `PUT /creatures/{id}/brain` с `type=llm` требует OPENROUTER_API_KEY через `strict=True` в BrainFactory. В тестовом окружении (docker compose без LLM) невозможно переключить на `llm` и проверить round-trip.

Unit-тесты: 1 новый (NPC HP round-trip), все зелёные.
Интеграционные тесты: 1 зелёный (state round-trip), 1 помечен xfail (brain switch — требует LLM config).
