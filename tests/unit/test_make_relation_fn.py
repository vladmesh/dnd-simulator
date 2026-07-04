"""make_relation_fn: the shared query_fn -> FactionRelation adapter (phase 3 task 2)."""

from __future__ import annotations

from dnd_simulator.core.models import Answer, FactionRelation, Query, QueryType
from dnd_simulator.rules.reputation import make_relation_fn


def test_make_relation_fn_reads_faction_relation_query() -> None:
    captured: list[tuple[str, str]] = []

    def fake_query_fn(layer: str, query: Query) -> Answer:
        assert query.question is QueryType.FACTION_RELATION
        a = str(query.params["a"])
        b = str(query.params["b"])
        captured.append((a, b))
        rel = FactionRelation.HOSTILE if a == "orcs" and b == "humans" else FactionRelation.NEUTRAL
        return Answer(value=rel)

    rel_fn = make_relation_fn(fake_query_fn)
    assert rel_fn("orcs", "humans") is FactionRelation.HOSTILE
    assert rel_fn("elves", "humans") is FactionRelation.NEUTRAL
    assert captured == [("orcs", "humans"), ("elves", "humans")]
