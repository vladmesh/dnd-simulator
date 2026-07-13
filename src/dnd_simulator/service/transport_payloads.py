"""JSON-safe payload builders shared by service commands and session callbacks."""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import TYPE_CHECKING, Any

from dnd_simulator.core.action_defs import get_action_def
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.character import Ability, Creature
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.i18n import _
from dnd_simulator.rules.actions import collect_cost_overrides
from dnd_simulator.rules.leveling import xp_to_next_level
from dnd_simulator.rules.modifiers import effective_ac
from dnd_simulator.service.dto import JourneyView, PlayerStatusData, ResourcePoolView

if TYPE_CHECKING:
    from dnd_simulator.core.creature_host import CreatureHost
    from dnd_simulator.core.location import LocationGraph
    from dnd_simulator.core.world import World
    from dnd_simulator.round import Round


def _awareness_to_dict(
    awareness: PeacefulAwareness | CombatAwareness,
    creature: Creature | None = None,
) -> dict[str, Any]:
    data = dataclasses.asdict(awareness)
    data["reachable"] = sorted([x, y] for x, y in awareness.reachable)
    if isinstance(awareness, CombatAwareness):
        data["self_conditions"] = sorted(condition.value for condition in awareness.self_conditions)
        for index, nearby_entry in enumerate(awareness.nearby):
            data["nearby"][index]["conditions"] = sorted(condition.value for condition in nearby_entry.conditions)
        data["self_resource_pools"] = [
            {"id": pool.id, "max_uses": pool.max_uses, "current_uses": pool.current_uses}
            for pool in awareness.self_resource_pools
        ]

    overrides = collect_cost_overrides(creature) if creature else []
    actions: list[dict[str, Any]] = []
    for action in awareness.available_actions:
        definition = get_action_def(action)
        if definition.internal:
            continue
        action_data: dict[str, Any] = {
            "name": str(action),
            "description": _(definition.description),
            "cost_type": definition.cost_type.value,
            "params": [
                {"name": parameter.name, "type": parameter.param_type, "required": parameter.required}
                for parameter in definition.params
            ],
            "target_mode": definition.target_mode.value,
            "target_scope": definition.target_scope.value,
        }
        action_overrides = [override for override in overrides if override.action_type == action]
        if action_overrides:
            action_data["cost_options"] = [
                {"cost_type": definition.cost_type.value, "source": "default"},
                *[{"cost_type": override.cost_type.value, "source": override.source} for override in action_overrides],
            ]
        actions.append(action_data)
    data["available_actions"] = actions
    return data


def _json_safe(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_safe(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    return value


def _events_to_list(events: list[PerceivedEvent]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for event in events:
        data = _json_safe(dataclasses.asdict(event))
        assert isinstance(data, dict)
        data["event_type"] = event.event_type.value
        result.append(data)
    return result


def _budget_to_dict(budget: TurnBudget) -> dict[str, Any]:
    return dataclasses.asdict(budget)


def _reaction_to_dict(trigger: ReactionTrigger, options: list[ReactionOption]) -> dict[str, Any]:
    return {
        "type": "reaction_prompt",
        "trigger": {
            "trigger_type": trigger.trigger_type.value,
            "source_creature_id": trigger.source_creature_id,
            "data": dict(trigger.data),
        },
        "options": [
            {
                "action_type": option.action_type.value,
                "description": option.description,
                "params": dict(option.params),
            }
            for option in options
        ],
    }


def build_equipped_payload(player: PlayerCharacter) -> list[dict[str, str]]:
    from dnd_simulator.layers.entities.awareness_builder import AwarenessBuilder

    return [
        {"slot": entry.slot.value, "item_id": entry.item_id, "name": entry.name, "description": entry.description}
        for entry in AwarenessBuilder.build_equipped(player)
    ]


def build_inventory_payload(player: PlayerCharacter) -> list[dict[str, object]]:
    from dnd_simulator.core.awareness import describe_item

    inventory: list[dict[str, object]] = []
    for item in player.inventory:
        entry: dict[str, object] = {
            "id": item.id,
            "name": item.name,
            "type": item.item_type.value,
            "description": describe_item(item),
            "price": item.price,
        }
        if item.accessory_def is not None:
            entry["slot"] = item.accessory_def.slot.value
        inventory.append(entry)
    return inventory


def build_player_status(player: PlayerCharacter, location_graph: LocationGraph | None = None) -> PlayerStatusData:
    from dnd_simulator.core.intent import TravelIntent

    scores = player.ability_scores
    journey = None
    if isinstance(player.current_intent, TravelIntent) and location_graph is not None:
        intent = player.current_intent

        def location_name(location_id: str) -> str:
            return location_graph.get(location_id).name if location_graph.has(location_id) else location_id

        journey = JourneyView(
            destination_id=intent.destination_id,
            destination_name=location_name(intent.destination_id),
            current_location_name=location_name(player.location_id),
            next_location_name=location_name(intent.remaining_route[0]),
            remaining_route=tuple(location_name(location_id) for location_id in intent.remaining_route),
            next_arrival_seconds=intent.next_arrival_seconds,
        )
    return PlayerStatusData(
        player_id=player.id,
        name=player.name,
        race=player.race.value,
        char_class=player.char_class.value,
        level=player.level,
        experience=player.experience,
        level_up_available=player.level_up_available,
        xp_to_next_level=xp_to_next_level(player.experience),
        alignment=player.alignment.value,
        hp=player.current_hp,
        max_hp=player.max_hp,
        ac=effective_ac(player),
        gold=player.gold,
        location_id=player.location_id,
        appearance=player.appearance,
        ability_scores={
            "str": scores[Ability.STR],
            "dex": scores[Ability.DEX],
            "con": scores[Ability.CON],
            "int": scores[Ability.INT],
            "wis": scores[Ability.WIS],
            "cha": scores[Ability.CHA],
        },
        journey=journey,
        resource_pools=[
            ResourcePoolView(id=pool.id, max_uses=pool.max_uses, current_uses=pool.current_uses)
            for pool in player.resource_pools
        ],
        equipped=build_equipped_payload(player),
        inventory=build_inventory_payload(player),
    )


def _location_data(world: World, location_id: str) -> dict[str, Any]:
    graph = world.location_graph
    if not graph.has(location_id):
        return {"current_location": location_id, "paths": []}
    location = graph.get(location_id)
    paths = []
    for edge in location.edges:
        target = graph.get(edge.target_id) if graph.has(edge.target_id) else None
        paths.append(
            {
                "target_id": edge.target_id,
                "target_name": target.name if target else edge.target_id,
                "distance_m": edge.distance_m,
            }
        )
    return {
        "current_location": location.name,
        "current_location_id": location.id,
        "description": location.description,
        "region_id": location.region_id,
        "paths": paths,
    }


def build_round_state(
    msg_type: str, player: PlayerCharacter, game_round: Round, creature_host: CreatureHost, world: World
) -> dict[str, Any]:
    perceived = game_round.get_perceived_events(player)
    awareness = creature_host.build_awareness(player, world.time, world.make_query_fn("entities"))
    return {
        "type": msg_type,
        "mode": "combat" if isinstance(awareness, CombatAwareness) else "peaceful",
        "awareness": _awareness_to_dict(awareness, creature=player),
        "events": _events_to_list(perceived),
        "player": dataclasses.asdict(build_player_status(player, world.location_graph)),
        "location": _location_data(world, player.location_id),
    }


def build_turn_state(
    player: PlayerCharacter,
    awareness: PeacefulAwareness | CombatAwareness,
    events: list[PerceivedEvent],
    world: World,
) -> dict[str, Any]:
    """Build the player-turn message from the round's awareness snapshot."""
    message: dict[str, Any] = {
        "type": "turn",
        "mode": "combat" if isinstance(awareness, CombatAwareness) else "peaceful",
        "awareness": _awareness_to_dict(awareness, creature=player),
        "events": _events_to_list(events),
        "player": dataclasses.asdict(build_player_status(player, world.location_graph)),
        "location": _location_data(world, player.location_id),
    }
    if awareness.turn_budget is not None:
        message["budget"] = _budget_to_dict(awareness.turn_budget)
    return message
