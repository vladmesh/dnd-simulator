"""Tests for _awareness_to_dict action info — cost_type is always present."""

from __future__ import annotations

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, ResourcePoolInfo
from dnd_simulator.core.character import Ability, AbilityScores, Attack, Character, DamageComponent, DamageType
from dnd_simulator.core.class_features import RogueFeatures
from dnd_simulator.service.session import _awareness_to_dict, build_player_status

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)


def _scores(**overrides: int) -> AbilityScores:
    scores = dict(AbilityScores().scores)
    for name, val in overrides.items():
        scores[Ability[name.upper()]] = val
    return AbilityScores(scores=scores)


def _peaceful(**kw: object) -> PeacefulAwareness:
    defaults: dict[str, object] = dict(
        hour=10,
        day=1,
        month=6,
        year=1490,
        weather={},
        location_name="Town Square",
        region_name="Valley",
        settlements=None,
        territory_owner=None,
        nation_info=None,
    )
    defaults.update(kw)
    return PeacefulAwareness(**defaults)  # type: ignore[arg-type]


def _combat(**kw: object) -> CombatAwareness:
    defaults: dict[str, object] = dict(
        self_hp=20,
        self_max_hp=20,
        self_ac=15,
        self_speed=30,
        self_weapon="longsword",
        self_weapon_damage="1d8",
    )
    defaults.update(kw)
    return CombatAwareness(**defaults)  # type: ignore[arg-type]


class TestActionInfoCostType:
    """Every action in awareness dict must include cost_type."""

    def test_basic_creature_actions_have_cost_type(self) -> None:
        creature = Character(
            id="p1",
            name="Hero",
            location_id="loc1",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
        )
        awareness = _peaceful(
            available_actions=[ActionType.SAY, ActionType.WAIT, ActionType.IDLE],
        )
        result = _awareness_to_dict(awareness, creature)
        for action_info in result["available_actions"]:
            assert "cost_type" in action_info, f"Missing cost_type on {action_info['name']}"
        by_name = {a["name"]: a for a in result["available_actions"]}
        assert by_name["say"]["cost_type"] == "free"
        assert by_name["wait"]["cost_type"] == "free"
        assert by_name["idle"]["cost_type"] == "free"

    def test_combat_actions_have_cost_type(self) -> None:
        creature = Character(
            id="p1",
            name="Hero",
            location_id="loc1",
            ability_scores=_scores(STR=16),
            attacks=(_SWORD,),
        )
        awareness = _combat(
            available_actions=[ActionType.ATTACK, ActionType.DODGE, ActionType.MOVE, ActionType.DASH],
        )
        result = _awareness_to_dict(awareness, creature)
        by_name = {a["name"]: a for a in result["available_actions"]}
        assert by_name["attack"]["cost_type"] == "action"
        assert by_name["dodge"]["cost_type"] == "action"
        assert by_name["move"]["cost_type"] == "movement"
        assert by_name["dash"]["cost_type"] == "action"

    def test_rogue_dash_has_cost_type_and_cost_options(self) -> None:
        creature = Character(
            id="p1",
            name="Rogue",
            location_id="loc1",
            ability_scores=_scores(DEX=16),
            attacks=(_SWORD,),
            class_features=[RogueFeatures(sneak_attack_dice=1)],
        )
        awareness = _combat(
            available_actions=[ActionType.ATTACK, ActionType.DASH, ActionType.DISENGAGE],
        )
        result = _awareness_to_dict(awareness, creature)
        by_name = {a["name"]: a for a in result["available_actions"]}
        dash = by_name["dash"]
        assert dash["cost_type"] == "action"
        assert "cost_options" in dash
        cost_types = [co["cost_type"] for co in dash["cost_options"]]
        assert "action" in cost_types
        assert "bonus_action" in cost_types

    def test_internal_actions_excluded(self) -> None:
        creature = Character(id="p1", name="Hero", location_id="loc1")
        awareness = _peaceful(
            available_actions=[ActionType.SAY, ActionType.END_TURN, ActionType.SKIP],
        )
        result = _awareness_to_dict(awareness, creature)
        names = [a["name"] for a in result["available_actions"]]
        assert "end_turn" not in names
        assert "skip" not in names
        assert "say" in names


class TestAwarenessResourcePoolSerialization:
    """Resource pools in awareness are serialized to JSON-compatible dicts."""

    def test_combat_awareness_resource_pools_serialized(self) -> None:
        """CombatAwareness with resource pools → dict has self_resource_pools list."""
        awareness = _combat(
            self_resource_pools=(
                ResourcePoolInfo(id="spell_slot_1", max_uses=2, current_uses=1),
                ResourcePoolInfo(id="lay_on_hands", max_uses=10, current_uses=10),
            ),
        )
        result = _awareness_to_dict(awareness)
        pools = result["self_resource_pools"]
        assert isinstance(pools, list)
        assert len(pools) == 2
        by_id = {p["id"]: p for p in pools}
        assert by_id["spell_slot_1"]["max_uses"] == 2
        assert by_id["spell_slot_1"]["current_uses"] == 1
        assert by_id["lay_on_hands"]["max_uses"] == 10

    def test_empty_resource_pools_serialized_as_empty_list(self) -> None:
        """CombatAwareness with no resource pools → self_resource_pools is empty list."""
        awareness = _combat()
        result = _awareness_to_dict(awareness)
        assert result["self_resource_pools"] == []


class TestPlayerStatusResourcePools:
    """build_player_status includes resource pools from the player character."""

    def test_player_status_has_resource_pools(self) -> None:
        """PlayerCharacter with spell slots → status has resource_pools."""
        from dnd_simulator.core.player import PlayerCharacter
        from dnd_simulator.core.resource import ResourcePool, RestType

        player = PlayerCharacter(
            id="p1",
            name="Paladin",
            location_id="arena",
            ability_scores=_scores(STR=16, CHA=14),
            resource_pools=[
                ResourcePool(id="spell_slot_1", max_uses=2, current_uses=2, reset_on=RestType.LONG_REST),
                ResourcePool(id="lay_on_hands", max_uses=10, current_uses=7, reset_on=RestType.LONG_REST),
            ],
        )
        result = build_player_status(player)
        pools = result.resource_pools
        assert len(pools) == 2
        by_id = {p.id: p for p in pools}
        assert by_id["spell_slot_1"].current_uses == 2
        assert by_id["lay_on_hands"].current_uses == 7

    def test_player_status_empty_pools_when_no_resources(self) -> None:
        """PlayerCharacter with no resource pools → resource_pools is empty list."""
        from dnd_simulator.core.player import PlayerCharacter

        player = PlayerCharacter(
            id="p1",
            name="Fighter",
            location_id="arena",
            ability_scores=_scores(STR=16),
        )
        result = build_player_status(player)
        assert result.resource_pools == []
