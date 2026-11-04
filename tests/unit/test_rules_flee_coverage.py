"""Flee eligibility when combat sides and faction information are unavailable."""

import pytest
from test_flee_scene_exit import _combat, _fighter

from dnd_simulator.core.combat import Position
from dnd_simulator.rules.flee import FleeBlock, flee_blocker


@pytest.mark.parametrize("actor_faction, other_faction", [("", "vale"), ("vale", ""), ("", "")])
def test_unknown_faction_neighbour_blocks_flee(actor_faction: str, other_faction: str) -> None:
    actor = _fighter("me", actor_faction)
    other = _fighter("other", other_faction)
    combat = _combat({"me": (0, 0), "other": (15, 0)})
    get_entity = {actor.id: actor, other.id: other}.get

    assert flee_blocker(actor, combat, get_entity, exits=["road"]) is FleeBlock.ENEMIES_TOO_CLOSE

    combat.battle_map.set_position(other.id, Position(20, 0))
    assert flee_blocker(actor, combat, get_entity, exits=["road"]) is None
