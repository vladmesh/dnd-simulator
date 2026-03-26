# Sprint 007 Status

**Sprint:** 007-world-session
**Phase:** 1.5 — Save/Load Gaps
**Updated:** 2026-03-26

## Current

Phase 1.5, Task 1: Recreate Spawned Entities from Save Data — done. get_state/load_state now include entity_type discriminator and reconstruct missing NPCs/Creatures from save data.

## Next Steps

- Task 2: Reassign brains after load (extract _assign_brains helper, call after world.load)
- Task 3: Integration tests — remove xfail, add spawned creature round-trip tests
