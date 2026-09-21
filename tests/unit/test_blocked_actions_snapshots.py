"""Every message carrying combat awareness has the same authoritative ``blocked_actions``.

Drives a real ``GameSession`` round: the Round's turn snapshot and the transport's
action-result snapshot (``build_action_result`` → ``build_round_state``) must agree, so an
action result can never re-enable an equip control the turn snapshot disabled.
"""

from __future__ import annotations

import threading
from typing import Any

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.items import ArmorCategory, ArmorDef, Item, ItemType, ShieldDef
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.service.session import GameSession


class _EndTurnBrain(Brain):
    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        return END_TURN


def _world(entities: list[Creature]) -> World:
    region = Region(
        id="r1",
        name="Field",
        terrain=TerrainType.PLAINS,
        latitude=45.0,
        longitude=0.0,
        elevation=100,
        water_proximity=0.0,
        connections=[],
    )
    settlements = SettlementsLayer(settlements=[], region_terrains={"r1": TerrainType.PLAINS})
    politics = PoliticsLayer(
        nations=[],
        region_terrains={"r1": TerrainType.PLAINS},
        region_adjacency={},
        region_income_fn=settlements.get_region_income,
    )
    return World(
        layers=[GeographyLayer(regions=[region]), politics, settlements, EntitiesLayer(entities=list(entities))],
        time=GameDateTime(year=1, month=1, day=1, hour=10),
        location_graph=LocationGraph([Location(id="r1", name="Field", region_id="r1")]),
    )


def _blocks(msg: dict[str, Any]) -> dict[str, str]:
    return {b["name"]: b["reason_key"] for b in msg["awareness"]["blocked_actions"]}


class _Recorder:
    """Player listener: spends the Action on the first turn, ends the second, then records only."""

    def __init__(self, session: GameSession) -> None:
        self._session = session
        self.messages: list[dict[str, Any]] = []
        self.turns = 0
        self.done = threading.Event()

    def on_turn(self, msg: dict[str, Any]) -> None:
        self.messages.append(msg)
        self.turns += 1
        if self.turns == 1:
            self._session.submit_player_action(Action(name=ActionType.DODGE))
        elif self.turns == 2:
            self._session.submit_player_action(END_TURN)
        else:
            self.done.set()

    def on_action_result(self, msg: dict[str, Any]) -> None:
        self.messages.append(msg)

    def on_round_result(self, msg: dict[str, Any]) -> None:
        self.messages.append(msg)

    def on_reaction(self, msg: dict[str, Any]) -> None:
        pass

    def on_game_over(self) -> None:
        pass


def test_action_results_carry_the_turn_snapshots_blocked_actions() -> None:
    player = PlayerCharacter(id="player", name="Player", location_id="r1")
    player.inventory.extend(
        [
            Item(
                id="chain_0",
                name="Chain Mail",
                item_type=ItemType.ARMOR,
                armor_def=ArmorDef(armor_id="chain_mail", category=ArmorCategory.HEAVY, base_ac=16, max_dex_bonus=0),
            ),
            Item(id="shield_0", name="Shield", item_type=ItemType.SHIELD, shield_def=ShieldDef("shield", ac_bonus=2)),
        ]
    )
    npc = Creature(id="npc", name="NPC", location_id="r1", brain=_EndTurnBrain())
    world = _world([player, npc])
    entities = next(layer for layer in world.layers if isinstance(layer, EntitiesLayer))
    entities._combat._combats["r1"] = CombatState(location_id="r1", turn_order=[player.id, npc.id])
    session = GameSession(session_id="blocks", world=world)
    session._evict_grace_seconds = 3600
    recorder = _Recorder(session)
    session.add_listener(recorder)
    session.start_round(player)
    try:
        assert recorder.done.wait(timeout=5), "the player's next-round turn never came"
    finally:
        session.remove_listener(recorder)

    kinds = [m["type"] for m in recorder.messages]
    first_turn = recorder.messages[0]
    dodge_result = next(m for m in recorder.messages if m["type"] == "action_result" and m["action"] == "dodge")
    second_turn = recorder.messages[kinds.index("turn", 1)]
    after_player = recorder.messages[kinds.index("turn", 1) + 1 :]

    # Turn snapshot, Action unspent: armor blocked by mode, shield available.
    assert _blocks(first_turn) == {"equip_armor": "WRONG_MODE"}
    # After the Action is spent, the action result and the next turn snapshot agree.
    assert _blocks(dodge_result) == {"equip_armor": "WRONG_MODE", "equip_shield": "INSUFFICIENT_BUDGET"}
    assert _blocks(second_turn) == _blocks(dodge_result)
    # Later action/round results (the NPC's turn, the round end) still carry the armor block.
    later_results = [m for m in after_player if m["type"] in ("action_result", "round_result")]
    assert later_results
    for msg in later_results:
        assert msg["mode"] == "combat"
        assert _blocks(msg)["equip_armor"] == "WRONG_MODE"
