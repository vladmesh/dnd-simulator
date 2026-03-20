"""Tests for combat awareness, combat prompts, combat tools, and combat mode switching."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.character import (
    Ability,
    Attack,
    Character,
    DamageComponent,
    DamageType,
    Entity,
    Race,
    build_combat_awareness,
)
from dnd_simulator.core.models import ActionResult, Event, EventType, GameDateTime
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.llm.client import LlmResponse, ToolCall
from dnd_simulator.llm.prompts import build_npc_combat_prompt
from dnd_simulator.llm.tools import build_npc_combat_tools

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


def _get_entity_fn(*entities: Entity):
    by_id = {e.id: e for e in entities}
    return lambda eid: by_id.get(eid)


def _mock_world(entities: list[Entity] | None = None) -> MagicMock:
    """Create a mock World with EntitiesLayer for combat awareness."""
    world = MagicMock()
    world.time = GameDateTime(year=1, month=1, day=1, hour=12)

    layer = EntitiesLayer(entities or [])
    world.layers = [layer]

    def fake_query(layer_name: str, query: object) -> MagicMock:
        answer = MagicMock()
        q = getattr(query, "question", "")
        if layer_name == "entities":
            return layer.query(query)
        elif layer_name == "geography":
            if q == "weather":
                answer.value = {"condition": "clear", "temperature": 20}
            elif q == "region_info":
                answer.value = {"name": "Test Region"}
            else:
                answer.value = {}
        elif layer_name in ("settlements", "politics"):
            answer.value = None
        else:
            answer.value = None
        return answer

    world.query_layer.side_effect = fake_query
    world.handle_event.return_value = ActionResult()
    return world


# --- Combat awareness ---


class TestBuildCombatAwareness:
    def test_contains_self_stats(self) -> None:
        player = Character(id="p1", name="Hero", region_id="r1", max_hp=20, current_hp=15, attacks=(_SWORD,))
        npc = Character(id="n1", name="Guard", region_id="r1")
        world = _mock_world([player, npc])
        aw = build_combat_awareness(world, player)
        assert aw["self_hp"] == 15
        assert aw["self_max_hp"] == 20
        assert aw["self_weapon"] == "longsword"
        assert aw["self_weapon_damage"] == "1d8"

    def test_unarmed_defaults(self) -> None:
        player = Character(id="p1", name="Hero", region_id="r1")
        world = _mock_world([player])
        aw = build_combat_awareness(world, player)
        assert aw["self_weapon"] == "кулаки"
        assert aw["self_weapon_damage"] == "1"

    def test_nearby_excludes_self(self) -> None:
        player = Character(id="p1", name="Hero", region_id="r1")
        npc = Character(id="n1", name="Guard", region_id="r1", race=Race.DWARF)
        world = _mock_world([player, npc])
        aw = build_combat_awareness(world, player)
        assert len(aw["nearby"]) == 1
        assert aw["nearby"][0]["id"] == "n1"

    def test_no_time_or_weather(self) -> None:
        player = Character(id="p1", name="Hero", region_id="r1")
        world = _mock_world([player])
        aw = build_combat_awareness(world, player)
        assert "time" not in aw
        assert "weather" not in aw
        assert "settlements" not in aw


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
        assert "в бою" in prompt.lower()
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
        assert "погода" not in prompt.lower()
        assert "время" not in prompt.lower()
        assert "поселен" not in prompt.lower()

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
        assert "здоров" in prompt

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
        assert "ранен" in prompt

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
        assert "тяжело ранен" in prompt

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
        # say should not be listed as an action
        assert "say" not in prompt.lower().split("правила")[1]


# --- Combat tools ---


class TestBuildNpcCombatTools:
    def test_has_combat_actions(self) -> None:
        tools = build_npc_combat_tools()
        names = {t["function"]["name"] for t in tools}
        assert names == {"attack", "dodge", "flee", "idle"}

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
        observer = Character(id="p1", name="Hero", region_id="r1")
        event = Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={"entity_id": "p1"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "защитную стойку" in result
        assert "ты" in result.lower()

    def test_perceive_dodge_other(self) -> None:
        observer = Character(id="p1", name="Hero", region_id="r1")
        npc = Character(id="n1", name="Guard", region_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, npc))
        assert "защитную стойку" in result
        assert "dwarf" in result

    def test_perceive_dodge_with_description(self) -> None:
        observer = Character(id="p1", name="Hero", region_id="r1")
        npc = Character(id="n1", name="Guard", region_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={"entity_id": "n1", "description": "Прячется за стол"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, npc))
        assert "Прячется за стол" in result

    def test_perceive_flee_self(self) -> None:
        observer = Character(id="p1", name="Hero", region_id="r1")
        event = Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={"entity_id": "p1"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "сбежать" in result
        assert "ты" in result.lower()

    def test_perceive_flee_other(self) -> None:
        observer = Character(id="p1", name="Hero", region_id="r1")
        npc = Character(id="n1", name="Guard", region_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, npc))
        assert "сбежать" in result


# --- Combat mode switching ---


class TestCombatModeSwitch:
    def test_attack_sets_in_combat_for_all_in_region(self) -> None:
        attacker = Character(id="p1", name="Hero", region_id="r1", max_hp=20, current_hp=20, ac=15, attacks=(_SWORD,))
        target = Character(id="n1", name="Guard", region_id="r1", max_hp=20, current_hp=20, ac=10)
        bystander = Character(id="n2", name="Merchant", region_id="r1", max_hp=10, current_hp=10)
        other_region = Character(id="n3", name="Farmer", region_id="r2", max_hp=10, current_hp=10)

        layer = EntitiesLayer([attacker, target, bystander, other_region])
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "p1", "target_id": "n1"},
        )
        layer.handle_event(event)

        assert attacker.in_combat is True
        assert target.in_combat is True
        assert bystander.in_combat is True
        assert other_region.in_combat is False

    def test_flee_clears_in_combat(self) -> None:
        npc = Character(id="n1", name="Guard", region_id="r1", in_combat=True)
        layer = EntitiesLayer([npc])
        event = Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        layer.handle_event(event)
        assert npc.in_combat is False

    def test_flee_event_logged(self) -> None:
        observer = Character(id="p1", name="Hero", region_id="r1")
        npc = Character(id="n1", name="Guard", region_id="r1", race=Race.DWARF, in_combat=True)
        layer = EntitiesLayer([observer, npc])
        event = Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        layer.handle_event(event)
        log = layer.get_perceived_log(observer)
        assert len(log) == 1
        assert "сбежать" in log[0]

    def test_dodge_event_logged(self) -> None:
        observer = Character(id="p1", name="Hero", region_id="r1")
        npc = Character(id="n1", name="Guard", region_id="r1", race=Race.DWARF)
        layer = EntitiesLayer([observer, npc])
        event = Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={"entity_id": "n1"},
        )
        layer.handle_event(event)
        log = layer.get_perceived_log(observer)
        assert len(log) == 1
        assert "защитную стойку" in log[0]


# --- NPC combat turn ---


class TestNpcCombatTurn:
    def test_combat_turn_uses_combat_tools(self) -> None:
        """When in_combat=True, NPC should use combat prompt and tools."""
        npc = Npc(id="n1", name="Guard", region_id="r1", role="guard", attacks=(_DAGGER,), in_combat=True)
        player = Character(id="p1", name="Hero", region_id="r1", race=Race.HUMAN)
        world = _mock_world([npc, player])

        mock_llm = MagicMock()
        atk_tc = ToolCall(id="tc_1", name="attack", arguments={"target_id": "p1", "description": "Бью кинжалом!"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=atk_tc, raw_message=None)
        npc.llm = mock_llm

        npc.take_turn(world)

        # Check that combat tools were used (4 tools: attack, dodge, flee, idle)
        call_args = mock_llm.generate_with_tools.call_args
        tools_passed = call_args[0][1]
        tool_names = {t["function"]["name"] for t in tools_passed}
        assert tool_names == {"attack", "dodge", "flee", "idle"}
        assert "say" not in tool_names

    def test_combat_turn_dodge(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="r1", role="guard", in_combat=True)
        world = _mock_world([npc])
        mock_llm = MagicMock()
        dodge_tc = ToolCall(id="tc_1", name="dodge", arguments={"description": "Прячусь за щит"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=dodge_tc, raw_message=None)
        npc.llm = mock_llm
        npc.take_turn(world)
        world.handle_event.assert_called_once()
        event = world.handle_event.call_args[0][0]
        assert event.event_type == EventType.ENTITY_DODGE

    def test_combat_turn_flee(self) -> None:
        npc = Npc(id="n1", name="Guard", region_id="r1", role="guard", in_combat=True)
        world = _mock_world([npc])
        mock_llm = MagicMock()
        flee_tc = ToolCall(id="tc_1", name="flee", arguments={"description": "Бегу к двери!"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=flee_tc, raw_message=None)
        npc.llm = mock_llm
        npc.take_turn(world)
        world.handle_event.assert_called_once()
        event = world.handle_event.call_args[0][0]
        assert event.event_type == EventType.ENTITY_FLEE

    def test_peaceful_turn_uses_peaceful_tools(self) -> None:
        """When in_combat=False, NPC should use the regular tools."""
        npc = Npc(id="n1", name="Guard", region_id="r1", role="guard", in_combat=False)
        world = _mock_world([npc])
        mock_llm = MagicMock()
        idle_tc = ToolCall(id="tc_1", name="idle", arguments={})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=idle_tc, raw_message=None)
        npc.llm = mock_llm
        npc.take_turn(world)
        call_args = mock_llm.generate_with_tools.call_args
        tools_passed = call_args[0][1]
        tool_names = {t["function"]["name"] for t in tools_passed}
        assert "say" in tool_names


# --- Player combat turn ---


class TestPlayerCombatTurn:
    def test_combat_prompt_shown(self) -> None:
        outputs: list[str] = []
        inputs = iter(["idle"])
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            region_id="r1",
            max_hp=20,
            current_hp=15,
            attacks=(_SWORD,),
            in_combat=True,
            output_fn=outputs.append,
            input_fn=lambda _prompt: next(inputs),
        )
        world = _mock_world([player])
        player.take_turn(world)
        # Should show combat-style prompt
        assert any("Бой" in o for o in outputs)
        assert not any("время" in o for o in outputs)

    def test_combat_dodge_command(self) -> None:
        outputs: list[str] = []
        inputs = iter(["dodge"])
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            region_id="r1",
            in_combat=True,
            output_fn=outputs.append,
            input_fn=lambda _prompt: next(inputs),
        )
        world = _mock_world([player])
        player.take_turn(world)
        world.handle_event.assert_called_once()
        event = world.handle_event.call_args[0][0]
        assert event.event_type == EventType.ENTITY_DODGE

    def test_combat_flee_command(self) -> None:
        outputs: list[str] = []
        inputs = iter(["flee"])
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            region_id="r1",
            in_combat=True,
            output_fn=outputs.append,
            input_fn=lambda _prompt: next(inputs),
        )
        world = _mock_world([player])
        player.take_turn(world)
        world.handle_event.assert_called_once()
        event = world.handle_event.call_args[0][0]
        assert event.event_type == EventType.ENTITY_FLEE

    def test_combat_say_not_available(self) -> None:
        outputs: list[str] = []
        inputs = iter(["say Привет", "idle"])
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            region_id="r1",
            in_combat=True,
            output_fn=outputs.append,
            input_fn=lambda _prompt: next(inputs),
        )
        world = _mock_world([player])
        player.take_turn(world)
        # say should show help text, not send event
        assert any("Команды:" in o for o in outputs)
        # Only handle_event should not have been called with entity_say
        # (idle doesn't call handle_event either)
        world.handle_event.assert_not_called()

    def test_combat_wait_not_available(self) -> None:
        outputs: list[str] = []
        inputs = iter(["wait", "idle"])
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            region_id="r1",
            in_combat=True,
            output_fn=outputs.append,
            input_fn=lambda _prompt: next(inputs),
        )
        world = _mock_world([player])
        player.take_turn(world)
        assert any("Команды:" in o for o in outputs)

    def test_peaceful_turn_has_say(self) -> None:
        outputs: list[str] = []
        inputs = iter(["say Привет"])
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            region_id="r1",
            in_combat=False,
            output_fn=outputs.append,
            input_fn=lambda _prompt: next(inputs),
        )
        world = _mock_world([player])
        player.take_turn(world)
        world.handle_event.assert_called_once()
        event = world.handle_event.call_args[0][0]
        assert event.event_type == EventType.ENTITY_SAY

    def test_combat_prompt_input_prefix(self) -> None:
        """Combat mode should use 'бой>' prompt prefix."""
        prompts: list[str] = []

        def capture_input(prompt: str) -> str:
            prompts.append(prompt)
            return "idle"

        player = PlayerCharacter(
            id="p1",
            name="Hero",
            region_id="r1",
            in_combat=True,
            output_fn=lambda _: None,
            input_fn=capture_input,
        )
        world = _mock_world([player])
        player.take_turn(world)
        assert any("бой>" in p for p in prompts)
