"""Save/load game state.

Abstracts how world state is persisted:
- SaveStore: abstract interface (save, load, list, delete)
- JsonFileStore: saves as JSON files in a directory
- save_schema: versioned Pydantic envelope — SaveGame(schema_version=1, meta,
  world) with typed layer states, world seed and RNG states; legacy saves
  without schema_version are rejected on load

Layers produce and consume plain dicts via get_state()/load_state(), validated
internally through per-layer state models. World serializes the full state tree;
the envelope here is the single source of truth for the on-disk format.
"""
