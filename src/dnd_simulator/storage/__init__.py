"""Save/load game state.

Abstracts how world state is persisted:
- SaveStore: abstract interface (save, load, list, delete)
- JsonFileStore: saves as JSON files in a directory

Layers produce and consume plain dicts via get_state()/load_state().
World serializes the full state tree. This module handles the rest.
"""
