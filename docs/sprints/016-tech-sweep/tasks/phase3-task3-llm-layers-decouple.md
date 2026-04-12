# Task: Remove llm/ → layers/ dependency (move NpcMemory, Protocol for Npc)

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 3 — Core Boundaries

## Description

Two violations where `llm/` reaches into `layers/entities/models.py`:

1. `llm/brain.py:49` — `from dnd_simulator.layers.entities.models import Npc as NpcModel`. Used for `isinstance(creature, NpcModel)` to access `scheduled_activity(hour)`.
2. `llm/summarizer.py:10` — `from dnd_simulator.layers.entities.models import NpcMemory`. Used as factory (`from_dict`), constructor, and mutation target.

**Fix 1 (summarizer):** move `NpcMemory` to `core/npc_memory.py`. It's pure domain data (tags, recent, inner_state, current_conversation) — structured creature-attached memory with no layer-specific dependencies. `layers/entities/models.py` re-imports it for `Npc`'s field annotation (or `Npc` directly imports from core — preferred, no re-export).

**Fix 2 (brain):** define a narrow Protocol `ScheduledNpc` in `llm/brain.py` (or `core/`) with `scheduled_activity(hour: int) -> str | None`. Replace `isinstance(creature, NpcModel)` with `hasattr(creature, 'scheduled_activity')` or a Protocol + `isinstance` with `@runtime_checkable`. `Npc` already implements this method, so no change on the layer side.

## Tests First

1. **Integration test: LLM brain gets scheduled activity in prompt context** — spawn an LLM-driven NPC with a schedule, call `LlmBrain._build_context` (or trigger a turn), assert the prompt/context includes the schedule string for the current in-game hour. Exercises the new Protocol path without concrete `Npc` import.

2. **Integration test: memory summarizer compresses combat events** — run a short combat with an LLM NPC, trigger `MemorySummarizer.summarize`, assert the returned `NpcMemory` has non-empty `recent` or `tags`. Exercises `NpcMemory.from_dict` / construction from its new location.

3. **Architecture test:** `grep -rn "from dnd_simulator.layers" src/dnd_simulator/llm/` returns empty.

## Implementation

1. Create `src/dnd_simulator/core/npc_memory.py`. Move the `NpcMemory` class (frozen dataclass with `tags`, `recent`, `inner_state`, `current_conversation`, `to_dict`, `from_dict`) from `layers/entities/models.py`.
2. Update `layers/entities/models.py` to import `NpcMemory` from `core.npc_memory` and use it as `Npc.memory` field type. Do NOT re-export — update every import site to use the new canonical path.
3. In `llm/summarizer.py`, change import to `from dnd_simulator.core.npc_memory import NpcMemory`.
4. Define `ScheduledNpc` Protocol in `llm/brain.py` (or `core/protocols.py` if other LLM needs arise). Signature: `def scheduled_activity(self, hour: int) -> str | None`.
5. Replace `isinstance(creature, NpcModel)` with a `scheduled_activity` attribute check or Protocol isinstance. Remove the `NpcModel` import.
6. Fix any other import sites revealed by grep.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `grep -rn "from dnd_simulator.layers" src/dnd_simulator/llm/` → empty
- [ ] `NpcMemory` lives in `core/npc_memory.py`; no re-export from layers
- [ ] `ScheduledNpc` Protocol documented with a docstring

## Status

`pending`
