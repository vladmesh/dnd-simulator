"""Tests for RuleBrain utility-scoring combat AI."""

from __future__ import annotations

from dnd_simulator.core.awareness import CombatAwareness, CombatEntity, NearbyEntity, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import RuleBrain
from dnd_simulator.core.character import (
    Ability,
    Attack,
    DamageComponent,
    DamageType,
    NpcRole,
)
from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.core.models import EventType
from dnd_simulator.layers.entities.models import Npc, NpcMemory
from dnd_simulator.rules.movement import direction_label, grid_distance

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
    reach=5,
)


def _build_combat_awareness(
    npc: Npc,
    enemies: list[Npc],
    battle_map: BattleMap,
) -> CombatAwareness:
    """Build CombatAwareness from entities and a battle map."""
    my_pos = battle_map.get_position(npc.id)
    nearby: list[CombatEntity] = []
    for e in enemies:
        if e.id == npc.id:
            continue
        other_pos = battle_map.get_position(e.id)
        dist = 0
        direction = ""
        if my_pos and other_pos:
            dist = grid_distance(my_pos, other_pos)
            dx = other_pos.x - my_pos.x
            dy = other_pos.y - my_pos.y
            direction = direction_label(dx, dy)
        nearby.append(
            CombatEntity(
                id=e.id,
                description=e.name,
                is_wounded=e.current_hp < e.max_hp // 2,
                is_hostile=True,
                distance_ft=dist,
                direction=direction,
                x=other_pos.x if other_pos else 0,
                y=other_pos.y if other_pos else 0,
            )
        )
    weapon_name = npc.attacks[0].name if npc.attacks else "fists"
    weapon_damage = str(npc.attacks[0].damage[0].dice) if npc.attacks else "1"

    from dnd_simulator.core.turn_budget import TurnBudget

    budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=npc.speed, reaction=1)

    return CombatAwareness(
        self_hp=npc.current_hp,
        self_max_hp=npc.max_hp,
        self_ac=npc.ac,
        self_speed=npc.speed,
        self_weapon=weapon_name,
        self_weapon_damage=weapon_damage,
        self_x=my_pos.x if my_pos else 0,
        self_y=my_pos.y if my_pos else 0,
        nearby=nearby,
        turn_budget=budget,
    )


def _peaceful_awareness(hour: int = 12) -> PeacefulAwareness:
    return PeacefulAwareness(
        hour=hour,
        day=1,
        month=1,
        year=1,
        weather={"condition": "clear", "temperature": 15},
        location_name="market",
        region_name="Test",
        settlements=None,
        territory_owner=None,
        nation_info=None,
    )


class TestRuleBrainPeaceful:
    def test_peaceful_returns_end_turn(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="r1", role=NpcRole.GUARD, attacks=(_SWORD,))
        npc.in_combat = False
        brain = RuleBrain()
        action = brain.choose_action(npc, _peaceful_awareness(), [])
        assert action.name == "end_turn"

    def test_responds_to_speech_with_canned_line(self) -> None:
        merchant = Npc(id="m1", name="Merchant", location_id="market", role=NpcRole.MERCHANT)
        merchant.in_combat = False

        # Simulate a speech event
        speech_event = PerceivedEvent(
            description='Hero says: "Hello!"',
            event_type=EventType.ENTITY_SAY,
            actor_id="player",
        )

        brain = RuleBrain()
        action = brain.choose_action(merchant, _peaceful_awareness(hour=12), [speech_event])
        assert action.name == "say"
        # hour=12 with no schedule → IDLE activity
        assert action.params["text"] == "Shop's closed. Try tomorrow."

    def test_mood_overrides_role_dialogue(self) -> None:
        merchant = Npc(
            id="m1",
            name="Merchant",
            location_id="market",
            role=NpcRole.MERCHANT,
            memory=NpcMemory(tags=["angry"]),
        )
        merchant.in_combat = False

        speech_event = PerceivedEvent(
            description='Hero says: "Hello!"',
            event_type=EventType.ENTITY_SAY,
            actor_id="player",
        )

        brain = RuleBrain()
        action = brain.choose_action(merchant, _peaceful_awareness(hour=12), [speech_event])
        assert action.name == "say"
        assert action.params["text"] == "Leave me alone!"

    def test_no_speech_returns_end_turn(self) -> None:
        merchant = Npc(id="m1", name="Merchant", location_id="market", role=NpcRole.MERCHANT)
        merchant.in_combat = False
        brain = RuleBrain()
        action = brain.choose_action(merchant, _peaceful_awareness(), [])
        assert action.name == "end_turn"


class TestRuleBrainCombat:
    def test_attack_when_in_reach(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))  # 5 ft away — in reach
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "attack"
        assert action.params["target_id"] == "e1"

    def test_move_toward_when_close_but_not_in_reach(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20, speed=30)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 30))  # 20 ft away — within speed+reach=35
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "move"
        assert action.params["direction"] == "north"  # e1 is directly north
        assert action.params["ft"] == 5

    def test_dash_when_no_movement_left(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20, speed=30)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=120, height=120)
        bm.set_position("n1", Position(0, 0))
        bm.set_position("e1", Position(60, 60))  # ~60 ft away — beyond speed+reach
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        # Exhaust movement so brain chooses dash
        assert awareness.turn_budget is not None
        awareness.turn_budget.movement_remaining = 0
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "dash"
        assert action.params == {}

    def test_disengage_when_critically_wounded_enemy_in_reach(self) -> None:
        """With OA system, critically wounded NPC disengages instead of fleeing into OA."""
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=100, current_hp=10)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "disengage"

    def test_disengage_when_badly_hurt_and_in_reach(self) -> None:
        """With OA system, badly hurt NPC disengages instead of dodging in place."""
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=100, current_hp=20)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))  # 5 ft — in reach
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "disengage"

    def test_idle_when_no_enemies(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        awareness = CombatAwareness(
            self_hp=20,
            self_max_hp=20,
            self_ac=10,
            self_speed=30,
            self_weapon="longsword",
            self_weapon_damage="1d8",
        )
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "idle"

    def test_attacks_nearest_of_multiple_enemies(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        far = Npc(id="far", name="Far", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        close = Npc(id="close", name="Close", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("far", Position(10, 40))
        bm.set_position("close", Position(10, 15))
        awareness = _build_combat_awareness(npc, [npc, far, close], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "attack"
        assert action.params["target_id"] == "close"


class TestRuleBrainTags:
    def test_hated_target_preferred_over_closer(self) -> None:
        npc = Npc(
            id="n1",
            name="Guard",
            location_id="arena",
            attacks=(_SWORD,),
            max_hp=20,
            current_hp=20,
            memory=NpcMemory(tags=["hates:far"]),
        )
        far = Npc(id="far", name="Far", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        close = Npc(id="close", name="Close", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("far", Position(10, 15))  # 5 ft — both in reach
        bm.set_position("close", Position(15, 10))  # 5 ft — both in reach
        awareness = _build_combat_awareness(npc, [npc, far, close], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        # Hated target should be preferred when both are in reach
        assert action.name == "attack"
        assert action.params.get("target_id") == "far"

    def test_scared_npc_disengages_when_enemy_in_reach(self) -> None:
        """Scared NPC at 20% HP with enemy in reach → disengage (not flee into OA)."""
        npc = Npc(
            id="n1",
            name="Guard",
            location_id="arena",
            attacks=(_SWORD,),
            max_hp=100,
            current_hp=20,
            memory=NpcMemory(tags=["scared"]),
        )
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "disengage"

    def test_no_tags_unchanged_behavior(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "attack"
        assert action.params["target_id"] == "e1"


class TestRuleBrainFactionHostility:
    """RuleBrain faction-aware behavior: auto-attack hostiles, prefer faction enemies."""

    def test_hostile_faction_triggers_attack_in_peaceful_mode(self) -> None:
        """Orc guard meets kingdom soldier in peaceful mode → attacks."""
        orc = Npc(
            id="orc1",
            name="Orc Guard",
            location_id="road",
            role=NpcRole.GUARD,
            attacks=(_SWORD,),
            max_hp=20,
            current_hp=20,
            faction_id="orcs",
        )
        orc.in_combat = False
        brain = RuleBrain()
        awareness = _peaceful_awareness()
        # Nearby entity from hostile faction
        awareness = PeacefulAwareness(
            hour=12,
            day=1,
            month=1,
            year=1,
            weather={"condition": "clear", "temperature": 15},
            location_name="road",
            region_name="Test",
            settlements=None,
            territory_owner=None,
            nation_info=None,
            nearby=[NearbyEntity(id="soldier1", description="Kingdom Soldier", is_hostile=True)],
        )
        action = brain.choose_action(orc, awareness, [])
        assert action.name == "attack"
        assert action.params["target_id"] == "soldier1"

    def test_same_faction_no_attack_in_peaceful_mode(self) -> None:
        """Two kingdom guards meet → no attack."""
        guard = Npc(
            id="g1",
            name="Guard",
            location_id="road",
            role=NpcRole.GUARD,
            attacks=(_SWORD,),
            max_hp=20,
            current_hp=20,
            faction_id="kingdom",
        )
        guard.in_combat = False
        brain = RuleBrain()
        awareness = PeacefulAwareness(
            hour=12,
            day=1,
            month=1,
            year=1,
            weather={"condition": "clear", "temperature": 15},
            location_name="road",
            region_name="Test",
            settlements=None,
            territory_owner=None,
            nation_info=None,
            nearby=[NearbyEntity(id="g2", description="Guard", is_hostile=False)],
        )
        action = brain.choose_action(guard, awareness, [])
        assert action.name == "end_turn"

    def test_neutral_factions_no_attack(self) -> None:
        """Neutral factions don't trigger combat."""
        npc = Npc(
            id="n1",
            name="Traveler",
            location_id="road",
            role=NpcRole.GUARD,
            attacks=(_SWORD,),
            max_hp=20,
            current_hp=20,
            faction_id="merchants",
        )
        npc.in_combat = False
        brain = RuleBrain()
        awareness = PeacefulAwareness(
            hour=12,
            day=1,
            month=1,
            year=1,
            weather={"condition": "clear", "temperature": 15},
            location_name="road",
            region_name="Test",
            settlements=None,
            territory_owner=None,
            nation_info=None,
            nearby=[NearbyEntity(id="n2", description="Farmer", is_hostile=False)],
        )
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "end_turn"

    def test_hostile_faction_preferred_in_combat_scoring(self) -> None:
        """In combat, hostile-faction targets score higher than neutral ones."""
        npc = Npc(
            id="n1",
            name="Guard",
            location_id="arena",
            attacks=(_SWORD,),
            max_hp=20,
            current_hp=20,
            faction_id="kingdom",
        )
        # Two enemies at same distance — one hostile faction, one not
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("neutral", Position(10, 15))  # 5 ft
        bm.set_position("hostile", Position(15, 10))  # 5 ft
        neutral_enemy = Npc(
            id="neutral", name="Neutral", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20
        )
        hostile_enemy = Npc(
            id="hostile", name="Hostile", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20
        )
        awareness = _build_combat_awareness(npc, [npc, neutral_enemy, hostile_enemy], bm)
        # Mark hostile entity via is_hostile on CombatEntity
        from dataclasses import replace

        patched_nearby = [
            replace(e, is_hostile=True) if e.id == "hostile" else replace(e, is_hostile=False) for e in awareness.nearby
        ]
        awareness = replace(awareness, nearby=patched_nearby)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "attack"
        assert action.params["target_id"] == "hostile"

    def test_no_faction_creature_is_neutral(self) -> None:
        """Creature with empty faction_id doesn't trigger hostility."""
        npc = Npc(
            id="n1",
            name="Wanderer",
            location_id="road",
            role=NpcRole.GUARD,
            attacks=(_SWORD,),
            max_hp=20,
            current_hp=20,
            # faction_id defaults to ""
        )
        npc.in_combat = False
        brain = RuleBrain()
        awareness = PeacefulAwareness(
            hour=12,
            day=1,
            month=1,
            year=1,
            weather={"condition": "clear", "temperature": 15},
            location_name="road",
            region_name="Test",
            settlements=None,
            territory_owner=None,
            nation_info=None,
            nearby=[NearbyEntity(id="n2", description="Another Wanderer", is_hostile=False)],
        )
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "end_turn"


class TestRuleBrainTacticalDisengage:
    """RuleBrain should Disengage before retreating when enemies are in melee reach."""

    def test_disengage_when_low_hp_and_enemy_adjacent(self) -> None:
        """NPC at 20% HP with enemy at 5ft → DISENGAGE (not FLEE)."""
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=100, current_hp=20)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))  # 5 ft
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "disengage"

    def test_move_away_after_disengage(self) -> None:
        """NPC at 20% HP, is_disengaging=True, enemy at 5ft → MOVE away."""
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=100, current_hp=20)
        npc.is_disengaging = True
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 15))
        bm.set_position("e1", Position(10, 20))  # enemy is north
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "move"
        # Should move away from enemy (south, since enemy is north)
        assert action.params["direction"] == "south"

    def test_flee_when_low_hp_no_enemies_in_reach(self) -> None:
        """NPC at 10% HP, enemy at 30ft → FLEE directly (no Disengage needed)."""
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=100, current_hp=10)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 40))  # 30 ft away
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "flee"

    def test_attack_when_high_hp(self) -> None:
        """NPC at 80% HP, enemy at 5ft → ATTACK (no Disengage)."""
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=100, current_hp=80)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))  # 5 ft
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "attack"
        assert action.params["target_id"] == "e1"

    def test_scared_npc_disengages_at_higher_threshold(self) -> None:
        """SCARED NPC at 30% HP, enemy at 5ft → DISENGAGE (scared flee threshold is 25%)."""
        npc = Npc(
            id="n1",
            name="Guard",
            location_id="arena",
            attacks=(_SWORD,),
            max_hp=100,
            current_hp=30,
            memory=NpcMemory(tags=["scared"]),
        )
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))  # 5 ft
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "disengage"

    def test_choose_reaction_still_returns_oa(self) -> None:
        """RuleBrain.choose_reaction returns opportunity_attack for LEAVING_REACH trigger."""
        from dnd_simulator.core.action import ActionType
        from dnd_simulator.core.brain import ReactionOption
        from dnd_simulator.core.reactions import ReactionTrigger, TriggerType

        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        trigger = ReactionTrigger(
            trigger_type=TriggerType.LEAVING_REACH,
            source_creature_id="e1",
            data={"mover_id": "e1"},
        )
        options = [
            ReactionOption(
                action_type=ActionType.OPPORTUNITY_ATTACK,
                description="Attack the fleeing enemy",
                params={"target_id": "e1"},
            ),
        ]
        brain = RuleBrain()
        action = brain.choose_reaction(npc, trigger, options)
        assert action.name == "opportunity_attack"
