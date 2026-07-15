"""Awareness rebuild builds the faction relation callback once, not once-per-pair.

Guards the O(N²) allocation regression from sprint 024 task 2: check_faction_hostility
and _resolve_relation used to each construct make_relation_fn(query_fn) for every nearby
entity, so a scene of N creatures rebuilt the closure ~2N times per awareness rebuild.
"""

from __future__ import annotations

import dnd_simulator.layers.entities.awareness_builder as ab
from dnd_simulator.core.character import Character
from dnd_simulator.core.models import Answer, FactionRelation, Query, QueryType
from dnd_simulator.layers.entities.layer import EntitiesLayer


def _hostile_query_fn(target: str, query: Query) -> Answer:
    if target == "politics" and query.question == QueryType.FACTION_RELATION:
        return Answer(value=FactionRelation.HOSTILE)
    if target == "politics" and query.question == QueryType.FACTION_NAME:
        return Answer(value="Some Faction")
    return Answer(value=None)


def test_relation_fn_built_once_per_rebuild(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """One awareness rebuild over N nearby creatures builds the relation fn a constant number
    of times, not O(N)."""
    observer = Character(id="obs", name="Obs", location_id="road", faction_id="humans")
    others = [Character(id=f"g{i}", name=f"G{i}", location_id="road", faction_id="goblins") for i in range(8)]
    layer = EntitiesLayer([observer, *others])

    calls = {"n": 0}
    real_make = ab.make_relation_fn

    def counting_make(query_fn):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return real_make(query_fn)

    monkeypatch.setattr(ab, "make_relation_fn", counting_make)

    result = layer._awareness.build_nearby_entities(observer, hour=10, query_fn=_hostile_query_fn)

    # Sanity: every other creature was surfaced (so the per-pair path really ran N times).
    assert len(result) == 8
    # Built once for the whole rebuild, not once-per-pair (that would be ~16 for hostility+relation).
    assert calls["n"] == 1


def test_hostility_semantics_unchanged_after_rebuild_refactor() -> None:
    """Hostile factions still read as hostile through build_nearby_entities."""
    observer = Character(id="knight", name="Knight", location_id="road", faction_id="kingdom")
    enemy = Character(id="orc", name="Orc", location_id="road", faction_id="horde")
    friend = Character(id="squire", name="Squire", location_id="road", faction_id="kingdom")

    layer = EntitiesLayer([observer, enemy, friend])

    result = layer._awareness.build_nearby_entities(observer, hour=10, query_fn=_hostile_query_fn)
    by_id = {n.id: n for n in result}

    assert by_id["orc"].is_hostile is True
    assert by_id["squire"].is_hostile is False
