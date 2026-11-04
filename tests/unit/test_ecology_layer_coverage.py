"""Coverage for unsupported ecology queries and obsolete lairs in saved state."""

import pytest

from dnd_simulator.core.lair import Lair, LairState
from dnd_simulator.core.models import Query, QueryType
from dnd_simulator.layers.ecology.layer import EcologyLayer


def _make_lair(lair_id: str) -> Lair:
    return Lair(
        id=lair_id,
        name=f"Lair {lair_id}",
        faction_id="goblins",
        location_id="cave",
        members=["goblin", "goblin"],
        core="chief",
    )


def test_query_rejects_unsupported_query_type() -> None:
    layer = EcologyLayer(seed=0)

    with pytest.raises(ValueError, match=r"^Unknown ecology query: QueryType\.WEATHER$"):
        layer.query(Query(QueryType.WEATHER))


def test_load_state_skips_removed_lair_and_restores_remaining_lairs() -> None:
    saved_lair = _make_lair("warren")
    saved_lair.state = LairState.DEPLETED
    saved_lair.alive_members = ["goblin"]
    saved_lair.core_alive = False
    saved_lair.last_respawn_time = 3600
    saved_lair.death_writebacks = {"fallen_chief"}
    saved = EcologyLayer(lairs=[_make_lair("removed"), saved_lair], seed=0).get_state()

    restored_lair = _make_lair("warren")
    new_lair = _make_lair("new")
    layer = EcologyLayer(lairs=[restored_lair, new_lair], seed=0)
    layer.load_state(saved)

    lairs = layer.query(Query(QueryType.LAIRS_AT_LOCATION, {"location_id": "cave"})).value
    assert {lair.id for lair in lairs} == {"warren", "new"}
    assert restored_lair.state is LairState.DEPLETED
    assert restored_lair.alive_members == ["goblin"]
    assert restored_lair.core_alive is False
    assert restored_lair.last_respawn_time == 3600
    assert restored_lair.death_writebacks == {"fallen_chief"}
    assert new_lair.state is LairState.ACTIVE
    assert new_lair.alive_members is None
    assert new_lair.core_alive is True
    assert new_lair.last_respawn_time == 0
    assert new_lair.death_writebacks == set()
