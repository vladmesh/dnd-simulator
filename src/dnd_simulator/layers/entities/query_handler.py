"""QueryHandler — query dispatch and entity detail building for EntitiesLayer."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar

from dnd_simulator.core.character import Character, Creature, Entity
from dnd_simulator.core.models import Answer, EntityKind, Query, QueryType
from dnd_simulator.layers.entities.models import Npc, activity_flavor
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.rules.modifiers import effective_ac

if TYPE_CHECKING:
    from dnd_simulator.core.items import Item
    from dnd_simulator.core.models import Event
    from dnd_simulator.layers.entities.combat_manager import CombatManager

_QueryHandler = Callable[["QueryHandler", dict[str, object]], Answer]


class QueryHandler:
    """Handles all query dispatch and entity detail building for the entities layer."""

    def __init__(
        self,
        entities: dict[str, Entity],
        location_log: dict[str, list[Event]],
        combat: CombatManager,
        materialized_squads: dict[str, tuple[list[str], int, int]],
    ) -> None:
        self._entities = entities
        self._location_log = location_log
        self._combat = combat
        self._materialized_squads = materialized_squads

    def query(self, query: Query) -> Answer:
        """Answer queries about entities."""
        handler = self._dispatch.get(query.question)
        if handler is None:
            raise ValueError(f"Unknown entities query: {query.question}")
        return handler(self, query.params)

    # -- Query handlers --

    def _query_players(self, params: dict[str, object]) -> Answer:
        from dnd_simulator.core.player import PlayerCharacter

        return Answer(value=[e for e in self._entities.values() if isinstance(e, PlayerCharacter)])

    def _query_player(self, params: dict[str, object]) -> Answer:
        from dnd_simulator.core.player import PlayerCharacter

        pid = params.get("id")
        if pid:
            e = self._entities.get(str(pid))
            return Answer(value=e if isinstance(e, PlayerCharacter) else None)
        for e in self._entities.values():
            if isinstance(e, PlayerCharacter):
                return Answer(value=e)
        return Answer(value=None)

    def _query_entities_at_location(self, params: dict[str, object]) -> Answer:
        location_id = str(params["location_id"])
        hour = int(str(params.get("hour", 12)))
        result = []
        for e in self._entities.values():
            if not e.active:
                continue
            if isinstance(e, Npc):
                if e.current_location(hour) == location_id:
                    result.append(self._entity_summary(e, hour))
            elif e.location_id == location_id:
                result.append(self._entity_summary(e))
        return Answer(value=result)

    def _query_entity_info(self, params: dict[str, object]) -> Answer:
        e = self._entities[str(params["entity_id"])]
        return Answer(value=self._entity_detail(e))

    def _query_all_entities(self, params: dict[str, object]) -> Answer:
        return Answer(value=[self._entity_detail(e) for e in self._entities.values() if e.active])

    def _query_all_creatures(self, params: dict[str, object]) -> Answer:
        from dnd_simulator.core.player import PlayerCharacter

        raw_filter = params.get("entity_type")
        filter_kind = EntityKind(str(raw_filter)) if raw_filter else None
        filter_location = params.get("location_id")
        filter_active = params.get("active")
        result = []
        for e in self._entities.values():
            if not isinstance(e, Creature):
                continue
            if filter_active is not None and e.active != filter_active:
                continue
            if filter_location and e.location_id != filter_location:
                continue
            if filter_kind is EntityKind.PLAYER and not isinstance(e, PlayerCharacter):
                continue
            if filter_kind is EntityKind.NPC and not isinstance(e, Npc):
                continue
            if filter_kind is EntityKind.MONSTER and isinstance(e, (PlayerCharacter, Npc)):
                continue
            result.append(self._entity_detail(e))
        return Answer(value=result)

    def _query_all_npcs(self, params: dict[str, object]) -> Answer:
        return Answer(value=[self._npc_detail(e) for e in self._entities.values() if e.active and isinstance(e, Npc)])

    def _query_npc_info(self, params: dict[str, object]) -> Answer:
        npc_id = str(params["npc_id"])
        npc = self._entities.get(npc_id)
        if npc is None or not isinstance(npc, Npc):
            raise ValueError(f"NPC '{npc_id}' not found")
        return Answer(value=self._npc_detail(npc))

    def _query_perceived_log(self, params: dict[str, object]) -> Answer:
        e = self._entities[str(params["entity_id"])]
        if isinstance(e, Character):
            return Answer(value=self.get_perceived_log(e))
        return Answer(value=[])

    def _query_new_perceived_events(self, params: dict[str, object]) -> Answer:
        e = self._entities[str(params["entity_id"])]
        if isinstance(e, Character):
            return Answer(value=self.get_new_perceived_events(e))
        return Answer(value=[])

    def _query_new_raw_events(self, params: dict[str, object]) -> Answer:
        e = self._entities[str(params["entity_id"])]
        if isinstance(e, Character):
            return Answer(value=self.get_new_raw_events(e))
        return Answer(value=[])

    def _query_combat_info(self, params: dict[str, object]) -> Answer:
        location_id = str(params["location_id"])
        combat = self._combat.get_combat(location_id)
        if combat:
            return Answer(
                value={
                    "round_number": combat.round_number,
                    "turn_order": combat.turn_order,
                    "positions": dict(combat.battle_map.positions),
                    "wall_descriptions": combat.battle_map.describe_walls(),
                }
            )
        return Answer(value=None)

    def _query_perceive_entity(self, params: dict[str, object]) -> Answer:
        observer = self._entities.get(str(params["observer_id"]))
        target = self._entities.get(str(params["target_id"]))
        if observer and target and isinstance(observer, Character) and isinstance(target, Entity):
            return Answer(value=observer.perceive(target))
        return Answer(value=str(params["target_id"]))

    _dispatch: ClassVar[dict[QueryType, _QueryHandler]] = {
        QueryType.PLAYERS: _query_players,
        QueryType.PLAYER: _query_player,
        QueryType.ENTITIES_AT_LOCATION: _query_entities_at_location,
        QueryType.ENTITY_INFO: _query_entity_info,
        QueryType.ALL_ENTITIES: _query_all_entities,
        QueryType.ALL_CREATURES: _query_all_creatures,
        QueryType.ALL_NPCS: _query_all_npcs,
        QueryType.NPC_INFO: _query_npc_info,
        QueryType.PERCEIVED_LOG: _query_perceived_log,
        QueryType.NEW_PERCEIVED_EVENTS: _query_new_perceived_events,
        QueryType.NEW_RAW_EVENTS: _query_new_raw_events,
        QueryType.COMBAT_INFO: _query_combat_info,
        QueryType.PERCEIVE_ENTITY: _query_perceive_entity,
    }

    # -- Perception log --

    def get_perceived_log(self, observer: Character) -> list[str]:
        """Get ALL events at observer's location that the observer can see."""
        events = self._location_log.get(observer.location_id, [])
        if not events:
            return []
        return [
            perceive_event(e, observer, self._get_entity)
            for e in events
            if e.observer_ids is None or observer.id in e.observer_ids
        ]

    def get_new_perceived_events(self, observer: Character) -> list[str]:
        """Get only events since this observer last checked that they can see."""
        events = self._location_log.get(observer.location_id, [])
        last_seen = observer._last_seen_log_index
        new_events = events[last_seen:]
        observer._last_seen_log_index = len(events)
        if not new_events:
            return []
        return [
            perceive_event(e, observer, self._get_entity)
            for e in new_events
            if e.observer_ids is None or observer.id in e.observer_ids
        ]

    def get_new_raw_events(self, observer: Character) -> list[Event]:
        """Peek at raw Event objects since observer's last seen index."""
        events = self._location_log.get(observer.location_id, [])
        new_events = events[observer._last_seen_log_index :]
        if not new_events:
            return []
        return [e for e in new_events if e.observer_ids is None or observer.id in e.observer_ids]

    # -- Detail builders --

    def _entity_summary(self, entity: Entity, hour: int = 12) -> dict[str, object]:
        """Short summary for listings."""
        base: dict[str, object] = {
            "id": entity.id,
            "name": entity.name,
        }
        if isinstance(entity, Creature):
            base["is_wounded"] = entity.current_hp < entity.max_hp // 2
        if isinstance(entity, Npc):
            npc_activity = entity.scheduled_activity(hour)
            base["role"] = entity.role.value
            base["activity"] = npc_activity.value
            base["activity_flavor"] = activity_flavor(entity.role, npc_activity)
            base["location_label"] = entity.current_location(hour)
        return base

    @staticmethod
    def _serialize_equipped_weapon(weapon: Item | None) -> dict[str, object] | None:
        if weapon is None or weapon.weapon_def is None:
            return None
        wd = weapon.weapon_def
        damage_str = ", ".join(f"{d.dice} {d.type.value}" for d in wd.damage)
        return {
            "weapon_id": wd.weapon_id,
            "attack_name": wd.attack_name,
            "damage": damage_str,
        }

    def _entity_detail(self, entity: Entity) -> dict[str, object]:
        """Full detail for a single entity."""
        from dnd_simulator.core.player import PlayerCharacter

        base: dict[str, object] = {
            "id": entity.id,
            "name": entity.name,
            "location_id": entity.location_id,
            "active": entity.active,
        }
        if isinstance(entity, Creature):
            base.update(
                {
                    "hp": entity.current_hp,
                    "max_hp": entity.max_hp,
                    "ac": effective_ac(entity),
                    "conditions": sorted(c.value for c in entity.conditions),
                    "inventory": [
                        {"id": item.id, "name": item.name, "item_type": item.item_type.value}
                        for item in entity.inventory
                    ],
                    "equipped_weapon": self._serialize_equipped_weapon(entity.equipped_weapon),
                    "resource_pools": [
                        {
                            "id": rp.id,
                            "max_uses": rp.max_uses,
                            "current_uses": rp.current_uses,
                            "reset_on": rp.reset_on.value,
                        }
                        for rp in entity.resource_pools
                    ],
                    "gm_activation_override": entity.gm_activation_override.value,
                    "activation_triggers": [
                        {
                            "id": trigger.definition.id,
                            "armed": trigger.armed,
                            "active": trigger.active,
                        }
                        for trigger in entity.triggers
                    ],
                }
            )
        if isinstance(entity, Character):
            base.update(
                {
                    "race": entity.race.value,
                    "char_class": entity.char_class.value,
                    "level": entity.level,
                    "gold": entity.gold,
                }
            )
        if isinstance(entity, PlayerCharacter):
            base["entity_type"] = EntityKind.PLAYER.value
        elif isinstance(entity, Npc):
            base.update(
                {
                    "entity_type": EntityKind.NPC.value,
                    "role": entity.role.value,
                    "personality": entity.personality,
                    "settlement_id": entity.settlement_id,
                    "ai_type": entity.ai_type,
                    "memory": entity.memory.to_dict(),
                }
            )
        elif isinstance(entity, Creature):
            base["entity_type"] = EntityKind.MONSTER.value
        return base

    def _npc_detail(self, npc: Npc) -> dict[str, object]:
        """Full NPC detail including creature stats."""
        return {
            "id": npc.id,
            "name": npc.name,
            "location_id": npc.location_id,
            "role": npc.role.value,
            "personality": npc.personality,
            "hp": npc.current_hp,
            "max_hp": npc.max_hp,
            "ac": effective_ac(npc),
            "ai_type": npc.ai_type,
            "active": npc.active,
        }

    def _get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID — used as callback for perceive_event."""
        return self._entities.get(entity_id)
