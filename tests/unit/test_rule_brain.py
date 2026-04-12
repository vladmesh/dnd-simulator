"""Tests for RuleBrain utility-scoring combat AI."""

from __future__ import annotations

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity, NearbyEntity, PeacefulAwareness, PerceivedEvent
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
from dnd_simulator.rules.rule_brain import RuleBrain

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


class TestRuleBrainDecisionRules:
    """Tests for decomposed decision helpers and threshold constants."""

    def test_threshold_constants_exist(self) -> None:
        """Named threshold constants should be importable from brain module."""
        from dnd_simulator.rules.rule_brain import (
            DODGE_HP_THRESHOLD,
            FLEE_HP_THRESHOLD,
            POTION_HP_THRESHOLD,
            SCARED_DODGE_HP_THRESHOLD,
            SCARED_FLEE_HP_THRESHOLD,
        )

        assert FLEE_HP_THRESHOLD < DODGE_HP_THRESHOLD
        assert POTION_HP_THRESHOLD > FLEE_HP_THRESHOLD
        assert SCARED_FLEE_HP_THRESHOLD > FLEE_HP_THRESHOLD
        assert SCARED_DODGE_HP_THRESHOLD > DODGE_HP_THRESHOLD

    def test_ranged_creature_shoots_at_range(self) -> None:
        """Creature with ranged weapon and enemy at range attacks without moving closer."""
        longbow = Attack(
            name="longbow",
            ability=Ability.DEX,
            damage=(DamageComponent("1d8", DamageType.PIERCING),),
            reach=150,
        )
        archer = Npc(
            id="a1",
            name="Archer",
            location_id="arena",
            attacks=(longbow,),
            max_hp=20,
            current_hp=20,
            speed=30,
        )
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=200, height=200)
        bm.set_position("a1", Position(10, 10))
        bm.set_position("e1", Position(10, 80))  # 70 ft away — within longbow range
        awareness = _build_combat_awareness(archer, [archer, enemy], bm)
        brain = RuleBrain()
        action = brain.choose_action(archer, awareness, [])
        assert action.name == "attack"
        assert action.params["target_id"] == "e1"

    def test_creature_with_potion_uses_it_when_wounded(self) -> None:
        """Creature below potion threshold with healing potion uses it before attacking."""
        from dnd_simulator.core.action import ActionType
        from dnd_simulator.core.awareness import ItemInfo

        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=100, current_hp=30)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        # Add a potion to available items and USE_ITEM to available actions
        from dataclasses import replace

        awareness = replace(
            awareness,
            available_items=[ItemInfo(id="pot1", name="Healing Potion", description="heals 2d4+2 HP")],
            available_actions=[ActionType.USE_ITEM, ActionType.ATTACK],
        )
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "use_item"
        assert action.params["item_id"] == "pot1"

    def test_no_hostile_targets_ends_turn(self) -> None:
        """Creature in combat with only friendlies nearby ends turn."""
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("ally", Position(10, 15))
        ally = Npc(id="ally", name="Ally", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        awareness = _build_combat_awareness(npc, [npc, ally], bm)
        # Override is_hostile to False for the ally
        from dataclasses import replace

        patched = [replace(e, is_hostile=False) for e in awareness.nearby]
        awareness = replace(awareness, nearby=patched)
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == "end_turn"

    def test_choose_combat_action_is_dispatch_loop(self) -> None:
        """_choose_combat_action should be a short dispatch loop, not a monolith."""
        import inspect

        source = inspect.getsource(RuleBrain._choose_combat_action)
        lines = [line for line in source.splitlines() if line.strip() and not line.strip().startswith("#")]
        assert len(lines) <= 30, f"_choose_combat_action has {len(lines)} non-blank non-comment lines, expected <= 30"

    def test_melee_creature_moves_then_dashes_when_far(self) -> None:
        """Creature with melee weapon, enemy far away: moves first, then dashes when movement exhausted."""
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20, speed=30)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=200, height=200)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 80))  # 70 ft — way beyond speed
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        brain = RuleBrain()

        # First call: should move toward
        action1 = brain.choose_action(npc, awareness, [])
        assert action1.name == "move"

        # Simulate movement exhausted
        assert awareness.turn_budget is not None
        awareness.turn_budget.movement_remaining = 0
        action2 = brain.choose_action(npc, awareness, [])
        assert action2.name == "dash"


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
        from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger, TriggerType

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


class TestRuleBrainMovementBudget:
    """RuleBrain must not request MOVE when movement budget is insufficient."""

    def test_no_move_when_movement_under_step_cost(self) -> None:
        """NPC with movement_remaining < 5 (step cost) should not return MOVE.

        After diagonal movement, budget can end up at 1-4 ft. The brain should
        not request a 5ft MOVE that the dispatcher would reject.
        """
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20, speed=30)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=200, height=200)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 80))  # far away
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        assert awareness.turn_budget is not None
        awareness.turn_budget.movement_remaining = 3  # less than 5ft step cost
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        # Should dash (has actions) or end turn — NOT move
        assert action.name != ActionType.MOVE

    def test_no_attack_when_no_actions_remaining(self) -> None:
        """NPC with 0 actions left should not return ATTACK even if target is in reach.

        After the early exit is relaxed to allow post-attack movement,
        _try_attack must check the action budget itself.
        """
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20, speed=30)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=60, height=60)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 15))  # 5ft — in reach
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        assert awareness.turn_budget is not None
        awareness.turn_budget.actions = 0
        awareness.turn_budget.movement_remaining = 15  # still has movement
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        # Should NOT attack (no actions) — should end turn or move
        assert action.name != ActionType.ATTACK

    def test_post_attack_movement_allowed(self) -> None:
        """NPC with 0 actions but remaining movement should still be able to move.

        D&D 5e allows split movement: move → attack → move remainder.
        The brain should not end the turn just because actions are exhausted.
        """
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20, speed=30)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=200, height=200)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 80))  # far — out of reach
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        assert awareness.turn_budget is not None
        awareness.turn_budget.actions = 0
        awareness.turn_budget.bonus_actions = 0
        awareness.turn_budget.movement_remaining = 15  # still has movement
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        # Should move toward target — not end turn
        assert action.name == ActionType.MOVE

    def test_end_turn_when_all_budget_exhausted(self) -> None:
        """NPC with no actions, no bonus, no movement → END_TURN."""
        npc = Npc(id="n1", name="Guard", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20, speed=30)
        enemy = Npc(id="e1", name="Bandit", location_id="arena", attacks=(_SWORD,), max_hp=20, current_hp=20)
        bm = BattleMap(width=200, height=200)
        bm.set_position("n1", Position(10, 10))
        bm.set_position("e1", Position(10, 80))
        awareness = _build_combat_awareness(npc, [npc, enemy], bm)
        assert awareness.turn_budget is not None
        awareness.turn_budget.actions = 0
        awareness.turn_budget.bonus_actions = 0
        awareness.turn_budget.movement_remaining = 0
        brain = RuleBrain()
        action = brain.choose_action(npc, awareness, [])
        assert action.name == ActionType.END_TURN
