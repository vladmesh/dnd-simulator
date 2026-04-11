"""Tests for Divine Smite combat integration — CombatManager + RuleBrain.

Covers: smite damage on hit, slot not spent on miss, validation errors,
RuleBrain smite decision, damage log components.
"""

from __future__ import annotations

from collections import defaultdict

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity
from dnd_simulator.core.brain import RuleBrain
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Character,
    CharClass,
    Creature,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle, PaladinFeatures
from dnd_simulator.core.items import Item, ItemType, WeaponCategory, WeaponDef
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.rules.resources import spell_slot_pool_id

_LONGSWORD = WeaponDef(
    weapon_id="longsword",
    attack_name="longsword slash",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)


def _paladin(
    *,
    level: int = 2,
    slot_uses: int = 2,
    hp: int = 25,
) -> Character:
    pools: list[ResourcePool] = [
        ResourcePool("lay_on_hands", 5 * level, 5 * level, RestType.LONG_REST),
    ]
    if level >= 2:
        pools.append(
            ResourcePool(spell_slot_pool_id(1), max_uses=2, current_uses=slot_uses, reset_on=RestType.LONG_REST)
        )
    weapon = Item(id="longsword", name="Longsword", item_type=ItemType.WEAPON, weapon_def=_LONGSWORD)
    return Character(
        id="paladin",
        name="Paladin",
        location_id="arena",
        max_hp=25,
        current_hp=hp,
        ac=18,
        race=Race.HUMAN,
        char_class=CharClass.PALADIN,
        level=level,
        class_features=[PaladinFeatures()],
        resource_pools=pools,
        ability_scores=AbilityScores(
            {Ability.STR: 16, Ability.DEX: 10, Ability.CON: 14, Ability.INT: 10, Ability.WIS: 12, Ability.CHA: 14}
        ),
        equipped_weapon=weapon,
        faction_id="heroes",
    )


def _fighter(*, hp: int = 20) -> Character:
    weapon = Item(id="longsword", name="Longsword", item_type=ItemType.WEAPON, weapon_def=_LONGSWORD)
    return Character(
        id="fighter",
        name="Fighter",
        location_id="arena",
        max_hp=20,
        current_hp=hp,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        resource_pools=[ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)],
        ability_scores=AbilityScores(
            {Ability.STR: 16, Ability.DEX: 10, Ability.CON: 14, Ability.INT: 10, Ability.WIS: 12, Ability.CHA: 8}
        ),
        equipped_weapon=weapon,
        faction_id="heroes",
    )


def _target(*, hp: int = 50, ac: int = 5) -> Creature:
    """Low AC target — guarantees hit on any non-nat-1 roll."""
    return Creature(
        id="target",
        name="Dummy",
        location_id="arena",
        max_hp=hp,
        current_hp=hp,
        ac=ac,
        faction_id="monsters",
    )


def _setup_combat(attacker: Creature, target: Creature) -> tuple[CombatManager, dict[str, list[Event]]]:
    entities: dict[str, Creature] = {attacker.id: attacker, target.id: target}
    log: dict[str, list[Event]] = defaultdict(list)
    cm = CombatManager(entities, log)  # type: ignore[arg-type]
    cm.start_combat("arena")
    return cm, log


class TestSmiteOnHit:
    def test_smite_hit_adds_radiant_damage_and_spends_slot(self) -> None:
        """Paladin attacks with smite_slot_level=1, hits → radiant damage, slot spent."""
        paladin = _paladin(slot_uses=2)
        target = _target(ac=5)  # guaranteed hit
        cm, log = _setup_combat(paladin, target)

        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "paladin", "target_id": "target", "smite_slot_level": 1},
        )
        result = cm.resolve_attack(event)
        assert result.success

        # Slot was spent (2 → 1)
        pool = next(p for p in paladin.resource_pools if p.id == spell_slot_pool_id(1))
        assert pool.current_uses == 1

        # Damage log should contain divine_smite component
        attack_events = [e for e in log["arena"] if e.event_type == EventType.ENTITY_ATTACK]
        assert len(attack_events) == 1
        components = attack_events[0].data.get("damage_components", [])
        smite_components = [c for c in components if c["source"] == "divine_smite"]
        assert len(smite_components) == 1
        assert smite_components[0]["type"] == DamageType.RADIANT.value
        assert "d8" in smite_components[0]["dice"]


class TestSmiteOnMiss:
    def test_smite_miss_does_not_spend_slot(self) -> None:
        """Paladin attacks with smite, misses → slot NOT spent."""
        paladin = _paladin(slot_uses=2)
        target = _target(ac=99)  # guaranteed miss (unless nat 20)
        _cm, _log = _setup_combat(paladin, target)

        # Run many attempts — some may crit (nat 20). We need at least one miss.
        miss_found = False
        for _ in range(50):
            # Reset state for each attempt
            fresh_paladin = _paladin(slot_uses=2)
            fresh_target = _target(ac=99)
            fresh_cm, _ = _setup_combat(fresh_paladin, fresh_target)

            event = Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "paladin", "target_id": "target", "smite_slot_level": 1},
            )
            result = fresh_cm.resolve_attack(event)
            assert result.success

            pool = next(p for p in fresh_paladin.resource_pools if p.id == spell_slot_pool_id(1))
            if fresh_target.current_hp == fresh_target.max_hp:
                # Miss — slot should NOT be spent
                assert pool.current_uses == 2
                miss_found = True
                break
            else:
                # Hit (nat 20 crit) — slot should be spent
                assert pool.current_uses == 1

        assert miss_found, "No miss observed in 50 attempts against AC 99"


class TestSmiteValidation:
    def test_smite_no_slots_fails(self) -> None:
        """Paladin with no slots left → error."""
        paladin = _paladin(slot_uses=0)
        target = _target()
        cm, _log = _setup_combat(paladin, target)

        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "paladin", "target_id": "target", "smite_slot_level": 1},
        )
        result = cm.resolve_attack(event)
        assert not result.success

    def test_smite_non_paladin_fails(self) -> None:
        """Fighter with smite param → error."""
        fighter = _fighter()
        target = _target()
        cm, _log = _setup_combat(fighter, target)

        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "fighter", "target_id": "target", "smite_slot_level": 1},
        )
        result = cm.resolve_attack(event)
        assert not result.success


class TestRuleBrainSmite:
    def _combat_awareness(
        self,
        *,
        target_distance: int = 5,
        available_actions: list[ActionType] | None = None,
    ) -> CombatAwareness:
        if available_actions is None:
            available_actions = [ActionType.ATTACK, ActionType.DODGE, ActionType.END_TURN]
        return CombatAwareness(
            self_hp=25,
            self_max_hp=25,
            self_ac=18,
            self_speed=30,
            self_weapon="longsword",
            self_weapon_damage="1d8",
            nearby=[
                CombatEntity(
                    id="target",
                    description="A goblin",
                    distance_ft=target_distance,
                    direction="N",
                    is_hostile=True,
                ),
            ],
            turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=30, reaction=1),
            available_actions=available_actions,
        )

    def test_paladin_with_slots_smites(self) -> None:
        """RuleBrain adds smite_slot_level when Paladin has spell slots."""
        paladin = _paladin(slot_uses=2)
        brain = RuleBrain()
        awareness = self._combat_awareness()

        action = brain.choose_action(paladin, awareness, [])
        assert action.name == ActionType.ATTACK
        assert action.params.get("smite_slot_level") == 1

    def test_paladin_no_slots_does_not_smite(self) -> None:
        """RuleBrain omits smite when Paladin has no spell slots."""
        paladin = _paladin(slot_uses=0)
        brain = RuleBrain()
        awareness = self._combat_awareness()

        action = brain.choose_action(paladin, awareness, [])
        assert action.name == ActionType.ATTACK
        assert "smite_slot_level" not in action.params

    def test_fighter_does_not_smite(self) -> None:
        """RuleBrain never smites for non-Paladins."""
        fighter = _fighter()
        brain = RuleBrain()
        awareness = self._combat_awareness()

        action = brain.choose_action(fighter, awareness, [])
        assert action.name == ActionType.ATTACK
        assert "smite_slot_level" not in action.params
