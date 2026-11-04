"""Branch coverage for RuleBrain combat rules: equip, potion, flee budget and relation-weighted targeting."""

from __future__ import annotations

from dataclasses import replace

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity, FleeStatus, ItemInfo, PeacefulAwareness
from dnd_simulator.core.character import Creature, DamageComponent, DamageType
from dnd_simulator.core.inner_self import InnerSelf, Relationship, RelationshipType
from dnd_simulator.core.items import Item, ItemType, WeaponCategory, WeaponDef
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.rule_brain import RuleBrain

_LONGSWORD = Item(
    id="longsword_0",
    name="Longsword",
    item_type=ItemType.WEAPON,
    weapon_def=WeaponDef(
        weapon_id="longsword",
        attack_name="Longsword Strike",
        category=WeaponCategory.MARTIAL,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    ),
)


def _enemy(eid: str, x: int, *, hostile: bool = True) -> CombatEntity:
    return CombatEntity(
        id=eid,
        description=eid,
        is_wounded=False,
        is_hostile=hostile,
        distance_ft=x * 5,
        direction="east",
        x=x,
        y=0,
    )


def _awareness(**overrides: object) -> CombatAwareness:
    base = CombatAwareness(
        self_hp=10,
        self_max_hp=10,
        self_ac=12,
        self_speed=30,
        self_weapon="fists",
        self_weapon_damage="1",
        self_x=0,
        self_y=0,
        nearby=[_enemy("foe", 5)],
        battle_map_width=10,
        battle_map_height=10,
        turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=30, reaction=1),
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _creature(**overrides: object) -> Creature:
    fields: dict[str, object] = {"id": "me", "name": "Me", "location_id": "loc"}
    fields.update(overrides)
    return Creature(**fields)  # type: ignore[arg-type]


class TestPeaceful:
    def test_inactive_creature_ends_turn(self) -> None:
        awareness = PeacefulAwareness(
            hour=12,
            day=1,
            month=1,
            year=1,
            weather={},
            location_name="market",
            region_name="Test",
            settlements=None,
            territory_owner=None,
            nation_info=None,
        )
        action = RuleBrain().choose_action(_creature(active=False), awareness, [])
        assert action.name == ActionType.END_TURN


class TestEquip:
    def test_equips_weapon_from_inventory_when_awareness_lists_none(self) -> None:
        creature = _creature(inventory=[_LONGSWORD])
        action = RuleBrain().choose_action(creature, _awareness(available_actions=[ActionType.EQUIP]), [])
        assert action.name == ActionType.EQUIP
        assert action.params == {"weapon_id": "longsword_0"}

    def test_equips_weapon_listed_in_awareness(self) -> None:
        item = ItemInfo(id="axe_0", name="Axe", description="Weapon: Axe")
        awareness = _awareness(available_actions=[ActionType.EQUIP], available_items=[item])
        action = RuleBrain().choose_action(_creature(), awareness, [])
        assert action.params == {"weapon_id": "axe_0"}

    def test_no_weapon_anywhere_does_not_equip(self) -> None:
        action = RuleBrain().choose_action(_creature(), _awareness(available_actions=[ActionType.EQUIP]), [])
        assert action.name != ActionType.EQUIP


class TestPotion:
    def test_wounded_without_healing_item_does_not_drink(self) -> None:
        rope = ItemInfo(id="rope", name="Rope", description="Rope (50 ft)")
        awareness = _awareness(self_hp=1, available_actions=[ActionType.USE_ITEM], available_items=[rope])
        action = RuleBrain().choose_action(_creature(), awareness, [])
        assert action.name != ActionType.USE_ITEM


class TestFleeBudget:
    def test_low_hp_without_action_does_not_flee(self) -> None:
        awareness = _awareness(
            self_hp=1,
            flee=FleeStatus(allowed=True),
            turn_budget=TurnBudget(actions=0, bonus_actions=1, movement_remaining=30, reaction=1),
        )
        action = RuleBrain().choose_action(_creature(), awareness, [])
        assert action.name != ActionType.FLEE

    def test_low_hp_with_action_flees(self) -> None:
        awareness = _awareness(self_hp=1, flee=FleeStatus(allowed=True))
        assert RuleBrain().choose_action(_creature(), awareness, []).name == ActionType.FLEE


class TestRelationTargeting:
    def test_feared_enemy_preferred_over_equally_placed_stranger(self) -> None:
        inner = InnerSelf(relations=(Relationship(target_id="b", type=RelationshipType.FEARS),))
        creature = _creature(inner_self=inner)
        awareness = _awareness(nearby=[_enemy("a", 1), _enemy("b", 1)])
        action = RuleBrain().choose_action(creature, awareness, [])
        assert action.name == ActionType.ATTACK
        assert action.params["target_id"] == "b"
