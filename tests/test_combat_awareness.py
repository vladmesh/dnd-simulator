"""Tests for combat awareness, combat prompts, combat tools, and combat mode switching."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    DamageComponent,
    DamageType,
    Entity,
    Race,
)
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, GameDateTime, Query
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.client import LlmResponse, ToolCall
from dnd_simulator.llm.prompts import build_npc_combat_prompt
from dnd_simulator.llm.tools import build_npc_combat_tools
from dnd_simulator.rules.action_handlers import handle_attack, handle_dodge, handle_flee
from dnd_simulator.rules.validation import ActionContext

_STUB_WORLD = cast(World, MagicMock(spec=World))


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)

_DAGGER = Attack(
    name="кинжал",
    ability=Ability.DEX,
    damage=(DamageComponent("1d4", DamageType.PIERCING),),
)


def _scores(**overrides: int) -> AbilityScores:
    scores = dict(AbilityScores().scores)
    for name, val in overrides.items():
        scores[Ability[name.upper()]] = val
    return AbilityScores(scores=scores)


def _get_entity_fn(*entities: Entity):
    by_id = {e.id: e for e in entities}
    return lambda eid: by_id.get(eid)


# --- Combat awareness ---


class TestBuildCombatAwareness:
    def test_contains_self_stats(self) -> None:
        player = Character(id="p1", name="Hero", location_id="r1", max_hp=20, current_hp=15, attacks=(_SWORD,))
        npc = Character(id="n1", name="Guard", location_id="r1")
        layer = EntitiesLayer([player, npc])
        aw = layer.build_combat_awareness(player)
        assert aw.self_hp == 15
        assert aw.self_max_hp == 20
        assert aw.self_weapon == "longsword"
        assert aw.self_weapon_damage == "1d8"

    def test_unarmed_defaults(self) -> None:
        player = Character(id="p1", name="Hero", location_id="r1")
        layer = EntitiesLayer([player])
        aw = layer.build_combat_awareness(player)
        assert aw.self_weapon == "fists"
        assert aw.self_weapon_damage == "1"

    def test_nearby_excludes_self(self) -> None:
        player = Character(id="p1", name="Hero", location_id="r1")
        npc = Character(id="n1", name="Guard", location_id="r1", race=Race.DWARF)
        layer = EntitiesLayer([player, npc])
        aw = layer.build_combat_awareness(player)
        assert len(aw.nearby) == 1
        assert aw.nearby[0].id == "n1"

    def test_no_time_or_weather(self) -> None:
        player = Character(id="p1", name="Hero", location_id="r1")
        layer = EntitiesLayer([player])
        aw = layer.build_combat_awareness(player)
        assert not hasattr(aw, "time")
        assert not hasattr(aw, "weather")
        assert not hasattr(aw, "settlements")


# --- Combat prompt ---


class TestBuildNpcCombatPrompt:
    def test_contains_combat_marker(self) -> None:
        npc_data = {"name": "Варн", "role": "скупщик", "personality": "жадный"}
        combat_aw = {
            "self_hp": 12,
            "self_max_hp": 18,
            "self_ac": 14,
            "self_weapon": "кинжал",
            "self_weapon_damage": "1d4",
            "nearby": [{"id": "player", "description": "полуорк со шрамом"}],
        }
        prompt = build_npc_combat_prompt(npc_data, combat_aw)
        assert "in combat" in prompt.lower()
        assert "Варн" in prompt
        assert "12/18" in prompt
        assert "кинжал" in prompt

    def test_no_weather_or_time(self) -> None:
        npc_data = {"name": "Варн", "role": "скупщик", "personality": "жадный"}
        combat_aw = {
            "self_hp": 18,
            "self_max_hp": 18,
            "self_ac": 14,
            "self_weapon": "кинжал",
            "self_weapon_damage": "1d4",
            "nearby": [],
        }
        prompt = build_npc_combat_prompt(npc_data, combat_aw)
        assert "weather" not in prompt.lower().split("rules")[0]
        assert "time:" not in prompt.lower().split("rules")[0]
        assert "settlement" not in prompt.lower()

    def test_hp_status_healthy(self) -> None:
        npc_data = {"name": "Варн", "role": "скупщик", "personality": "жадный"}
        combat_aw = {
            "self_hp": 18,
            "self_max_hp": 18,
            "self_ac": 14,
            "self_weapon": "кинжал",
            "self_weapon_damage": "1d4",
            "nearby": [],
        }
        prompt = build_npc_combat_prompt(npc_data, combat_aw)
        assert "healthy" in prompt

    def test_hp_status_wounded(self) -> None:
        npc_data = {"name": "Варн", "role": "скупщик", "personality": "жадный"}
        combat_aw = {
            "self_hp": 12,
            "self_max_hp": 18,
            "self_ac": 14,
            "self_weapon": "кинжал",
            "self_weapon_damage": "1d4",
            "nearby": [],
        }
        prompt = build_npc_combat_prompt(npc_data, combat_aw)
        assert "wounded" in prompt

    def test_hp_status_critical(self) -> None:
        npc_data = {"name": "Варн", "role": "скупщик", "personality": "жадный"}
        combat_aw = {
            "self_hp": 3,
            "self_max_hp": 18,
            "self_ac": 14,
            "self_weapon": "кинжал",
            "self_weapon_damage": "1d4",
            "nearby": [],
        }
        prompt = build_npc_combat_prompt(npc_data, combat_aw)
        assert "badly wounded" in prompt

    def test_no_say_in_rules(self) -> None:
        npc_data = {"name": "Варн", "role": "скупщик", "personality": "жадный"}
        combat_aw = {
            "self_hp": 18,
            "self_max_hp": 18,
            "self_ac": 14,
            "self_weapon": "кинжал",
            "self_weapon_damage": "1d4",
            "nearby": [],
        }
        prompt = build_npc_combat_prompt(npc_data, combat_aw)
        rules_section = prompt.lower().split("rules")[1]
        assert "say," not in rules_section.split("\n")[1]


# --- Combat tools ---


class TestBuildNpcCombatTools:
    def test_has_combat_actions(self) -> None:
        tools = build_npc_combat_tools()
        names = {t["function"]["name"] for t in tools}
        assert names == {"attack", "dodge", "flee", "idle", "move", "dash"}

    def test_no_say_tool(self) -> None:
        tools = build_npc_combat_tools()
        names = {t["function"]["name"] for t in tools}
        assert "say" not in names

    def test_attack_has_description(self) -> None:
        tools = build_npc_combat_tools()
        attack_tool = next(t for t in tools if t["function"]["name"] == "attack")
        params = attack_tool["function"]["parameters"]["properties"]
        assert "description" in params
        assert "target_id" in params

    def test_dodge_has_description(self) -> None:
        tools = build_npc_combat_tools()
        dodge_tool = next(t for t in tools if t["function"]["name"] == "dodge")
        params = dodge_tool["function"]["parameters"]["properties"]
        assert "description" in params


# --- Perception of dodge/flee ---


class TestPerceiveDodgeFlee:
    def test_perceive_dodge_self(self) -> None:
        observer = Character(id="p1", name="Hero", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={"entity_id": "p1"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "defensive stance" in result
        assert "you" in result.lower()

    def test_perceive_dodge_other(self) -> None:
        observer = Character(id="p1", name="Hero", location_id="r1")
        npc = Character(id="n1", name="Guard", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, npc))
        assert "defensive stance" in result
        assert "dwarf" in result

    def test_perceive_dodge_with_description(self) -> None:
        observer = Character(id="p1", name="Hero", location_id="r1")
        npc = Character(id="n1", name="Guard", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={"entity_id": "n1", "description": "Прячется за стол"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, npc))
        assert "Прячется за стол" in result

    def test_perceive_flee_self(self) -> None:
        observer = Character(id="p1", name="Hero", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={"entity_id": "p1"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "flee" in result
        assert "you" in result.lower()

    def test_perceive_flee_other(self) -> None:
        observer = Character(id="p1", name="Hero", location_id="r1")
        npc = Character(id="n1", name="Guard", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, npc))
        assert "flee" in result


# --- Combat mode switching ---


class TestCombatModeSwitch:
    def test_attack_sets_in_combat_for_all_in_region(self) -> None:
        attacker = Character(id="p1", name="Hero", location_id="r1", max_hp=20, current_hp=20, ac=15, attacks=(_SWORD,))
        target = Character(id="n1", name="Guard", location_id="r1", max_hp=20, current_hp=20, ac=10)
        bystander = Character(id="n2", name="Merchant", location_id="r1", max_hp=10, current_hp=10)
        other_region = Character(id="n3", name="Farmer", location_id="r2", max_hp=10, current_hp=10)

        layer = EntitiesLayer([attacker, target, bystander, other_region])
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "p1", "target_id": "n1"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

        assert attacker.in_combat is True
        assert target.in_combat is True
        assert bystander.in_combat is True
        assert other_region.in_combat is False

    def test_flee_clears_in_combat(self) -> None:
        npc = Character(id="n1", name="Guard", location_id="r1", in_combat=True)
        layer = EntitiesLayer([npc])
        event = Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        assert npc.in_combat is False

    def test_flee_event_logged(self) -> None:
        observer = Character(id="p1", name="Hero", location_id="r1")
        npc = Character(id="n1", name="Guard", location_id="r1", race=Race.DWARF, in_combat=True)
        layer = EntitiesLayer([observer, npc])
        event = Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        log = layer.get_perceived_log(observer)
        assert len(log) == 1
        assert "flee" in log[0]

    def test_dodge_event_logged(self) -> None:
        observer = Character(id="p1", name="Hero", location_id="r1")
        npc = Character(id="n1", name="Guard", location_id="r1", race=Race.DWARF)
        layer = EntitiesLayer([observer, npc])
        event = Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        log = layer.get_perceived_log(observer)
        assert len(log) == 1
        assert "defensive stance" in log[0]


# --- NPC combat turn ---


class TestNpcCombatTurn:
    def test_combat_turn_uses_combat_tools(self) -> None:
        """When in_combat=True, NPC should use combat prompt and tools."""
        npc = Npc(id="n1", name="Guard", location_id="r1", role="guard", attacks=(_DAGGER,), in_combat=True)
        player = Character(id="p1", name="Hero", location_id="r1", race=Race.HUMAN)
        layer = EntitiesLayer([npc, player])

        mock_llm = MagicMock()
        atk_tc = ToolCall(id="tc_1", name="attack", arguments={"target_id": "p1", "description": "Бью кинжалом!"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=atk_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        time = GameDateTime(hour=12)
        awareness = layer.build_awareness(npc, time, _noop_query_fn)
        events = layer.get_perceived_events(npc)
        action = npc.brain.choose_action(npc, awareness, events)
        ctx = ActionContext(is_combat=True, current_turn_entity_id=npc.id)
        handle_attack(npc, action, capture_emit, ctx, _STUB_WORLD)

        # Check that combat tools were used
        call_args = mock_llm.generate_with_tools.call_args
        tools_passed = call_args[0][1]
        tool_names = {t["function"]["name"] for t in tools_passed}
        assert tool_names == {"attack", "dodge", "flee", "idle", "move", "dash"}
        assert "say" not in tool_names

    def test_combat_turn_dodge(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="r1", role="guard", in_combat=True)
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        dodge_tc = ToolCall(id="tc_1", name="dodge", arguments={"description": "Прячусь за щит"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=dodge_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        time = GameDateTime(hour=12)
        awareness = layer.build_awareness(npc, time, _noop_query_fn)
        events = layer.get_perceived_events(npc)
        action = npc.brain.choose_action(npc, awareness, events)
        ctx = ActionContext(is_combat=True, current_turn_entity_id=npc.id)
        handle_dodge(npc, action, capture_emit, ctx, _STUB_WORLD)
        assert len(emit_calls) == 1
        assert emit_calls[0].event_type == EventType.ENTITY_DODGE

    def test_combat_turn_flee(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="r1", role="guard", in_combat=True)
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        flee_tc = ToolCall(id="tc_1", name="flee", arguments={"description": "Бегу к двери!"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=flee_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        time = GameDateTime(hour=12)
        awareness = layer.build_awareness(npc, time, _noop_query_fn)
        events = layer.get_perceived_events(npc)
        action = npc.brain.choose_action(npc, awareness, events)
        ctx = ActionContext(is_combat=True, current_turn_entity_id=npc.id)
        handle_flee(npc, action, capture_emit, ctx, _STUB_WORLD)
        assert len(emit_calls) == 1
        assert emit_calls[0].event_type == EventType.ENTITY_FLEE

    def test_peaceful_turn_uses_peaceful_tools(self) -> None:
        """When in_combat=False, NPC should use the regular tools."""
        npc = Npc(id="n1", name="Guard", location_id="r1", role="guard", in_combat=False)
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        idle_tc = ToolCall(id="tc_1", name="idle", arguments={})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=idle_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        time = GameDateTime(hour=12)
        awareness = layer.build_awareness(npc, time, _noop_query_fn)
        events = layer.get_perceived_events(npc)
        npc.brain.choose_action(npc, awareness, events)
        call_args = mock_llm.generate_with_tools.call_args
        tools_passed = call_args[0][1]
        tool_names = {t["function"]["name"] for t in tools_passed}
        assert "say" in tool_names


# --- Dodge mechanics ---


class TestDodgeMechanics:
    def test_dodge_sets_is_dodging(self) -> None:
        c1 = Character(id="c1", name="Fighter", location_id="r1", max_hp=20, current_hp=20)
        layer = EntitiesLayer([c1])
        event = Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={"entity_id": "c1"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        assert c1.is_dodging is True

    def test_dodge_gives_disadvantage_on_attacks(self) -> None:
        import random

        attacker = Character(
            id="c1",
            name="Fighter",
            location_id="r1",
            max_hp=20,
            current_hp=20,
            attacks=(_SWORD,),
            ability_scores=_scores(str=14),
        )
        target = Character(id="c2", name="Dodger", location_id="r1", max_hp=100, current_hp=100, ac=10)
        layer = EntitiesLayer([attacker, target])

        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "c1", "target_id": "c2"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )

        from dnd_simulator.core.combat import Position

        combat = layer.get_combat("r1")
        assert combat is not None
        combat.battle_map.set_position("c1", Position(30, 30))
        combat.battle_map.set_position("c2", Position(35, 30))

        hits_normal = 0
        for seed in range(200):
            target.current_hp = 100
            target.is_dodging = False
            random.seed(seed)
            layer.handle_event(
                Event(
                    event_type=EventType.ENTITY_ATTACK,
                    source_layer="entities",
                    data={"attacker_id": "c1", "target_id": "c2"},
                ),
                _noop_query_fn,
                _noop_emit_fn,
            )
            if target.current_hp < 100:
                hits_normal += 1

        hits_dodging = 0
        for seed in range(200):
            target.current_hp = 100
            target.is_dodging = True
            random.seed(seed)
            layer.handle_event(
                Event(
                    event_type=EventType.ENTITY_ATTACK,
                    source_layer="entities",
                    data={"attacker_id": "c1", "target_id": "c2"},
                ),
                _noop_query_fn,
                _noop_emit_fn,
            )
            if target.current_hp < 100:
                hits_dodging += 1

        assert hits_dodging < hits_normal

    def test_dodge_clears_on_combat_end(self) -> None:
        c1 = Character(id="c1", name="Fighter", location_id="r1", max_hp=20, current_hp=20, is_dodging=True)
        c2 = Character(id="c2", name="Rogue", location_id="r1", max_hp=20, current_hp=20)
        layer = EntitiesLayer([c1, c2])
        layer._combat.start_combat("r1")
        layer._combat._end_combat("r1")
        assert c1.is_dodging is False
