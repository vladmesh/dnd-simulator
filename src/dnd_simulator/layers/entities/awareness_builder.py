"""Awareness building — assembles what a creature perceives by querying lower layers."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.awareness import (
    CombatAwareness,
    CombatEntity,
    NearbyEntity,
    PeacefulAwareness,
    ResourcePoolInfo,
)
from dnd_simulator.core.character import Character, Creature, Entity
from dnd_simulator.core.models import Event, FactionRelation
from dnd_simulator.core.queries import (
    query_faction_name,
    query_location_region,
    query_nation_info,
    query_region_info,
    query_region_owner,
    query_region_settlements,
    query_weather,
)
from dnd_simulator.core.world import LayerError
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.rules.combat_sides import are_allies
from dnd_simulator.rules.reputation import effective_relation, make_relation_fn

if TYPE_CHECKING:
    from dnd_simulator.core.models import GameDateTime, QueryFn
    from dnd_simulator.layers.entities.combat_manager import CombatManager

logger = structlog.get_logger(domain="entity")


class AwarenessBuilder:
    """Builds awareness data for creatures by querying geography, politics, and settlements layers.

    Operates on shared entity and combat references owned by EntitiesLayer.
    """

    def __init__(
        self,
        entities: dict[str, Entity],
        location_log: dict[str, list[Event]],
        combat: CombatManager,
    ) -> None:
        self._entities = entities
        self._location_log = location_log
        self._combat = combat

    def build_awareness(
        self, creature: Creature, time: GameDateTime, query_fn: QueryFn
    ) -> PeacefulAwareness | CombatAwareness:
        """Build awareness for a creature — dispatches by combat state."""
        if creature.in_combat:
            return self.build_combat_awareness(creature, query_fn)
        return self.build_peaceful_awareness(creature, time, query_fn)

    def build_peaceful_awareness(self, creature: Creature, time: GameDateTime, query_fn: QueryFn) -> PeacefulAwareness:
        """Build peaceful awareness using query_fn + internal data."""
        location_name = creature.location_id
        region_name = creature.location_id

        # Resolve location → region (location may or may not belong to a region)
        region_id: str | None = None
        try:
            region_id = query_location_region(query_fn, location_id=creature.location_id)
        except (KeyError, ValueError, LayerError):
            logger.warning("region_resolve_failed", location_id=creature.location_id, exc_info=True)

        # Region-dependent data: weather, settlements, politics
        weather: dict[str, object] = {"condition": "clear", "temperature": 15}
        settlements: list[dict[str, object]] | None = None
        territory_owner: str | None = None
        nation_info: dict[str, object] | None = None

        if region_id is not None:
            try:
                region_name = query_region_info(query_fn, region_id=region_id).name
            except (KeyError, ValueError, LayerError):
                logger.warning("region_info_query_failed", region_id=region_id, exc_info=True)

            try:
                weather = dataclasses.asdict(query_weather(query_fn, region_id=region_id))
            except (KeyError, ValueError, LayerError):
                logger.warning("weather_query_failed", region_id=region_id, exc_info=True)

            try:
                settlements = [dataclasses.asdict(s) for s in query_region_settlements(query_fn, region_id=region_id)]
            except (KeyError, ValueError, LayerError):
                logger.warning("settlements_query_failed", region_id=region_id, exc_info=True)

            try:
                territory_owner = query_region_owner(query_fn, region_id=region_id)
                if territory_owner is not None:
                    nation_info = dataclasses.asdict(query_nation_info(query_fn, nation_id=territory_owner))
            except (KeyError, ValueError, LayerError):
                logger.warning("politics_query_failed", region_id=region_id, exc_info=True)

        # Nearby entities (uses query_fn for faction hostility)
        nearby = self.build_nearby_entities(creature, time.hour, query_fn)

        # NPC scheduled location name
        if isinstance(creature, Npc):
            location_name = creature.current_location(time.hour)

        return PeacefulAwareness(
            hour=time.hour,
            day=time.day,
            month=time.month,
            year=time.year,
            weather=weather,
            location_name=location_name,
            region_name=region_name,
            settlements=settlements,
            territory_owner=territory_owner,
            nation_info=nation_info,
            nearby=nearby,
        )

    def build_combat_awareness(self, creature: Creature, query_fn: QueryFn | None = None) -> CombatAwareness:
        """Build combat awareness using internal data + optional faction queries."""
        from dnd_simulator.core.combat import Position
        from dnd_simulator.rules.movement import direction_label, grid_distance

        combat = self._combat.get_combat(creature.location_id)
        round_number = combat.round_number if combat else 1
        battle_map_positions: dict[str, Position] = dict(combat.battle_map.positions) if combat else {}
        my_pos = battle_map_positions.get(creature.id)

        # Build nearby list (exclude dead creatures and containers — containers are loot, not combatants)
        from dnd_simulator.core.container import Container

        nearby: list[CombatEntity] = []
        for e in self._entities.values():
            if e.id == creature.id or not e.active or e.location_id != creature.location_id:
                continue
            if isinstance(e, Container):
                continue
            if isinstance(e, Creature) and not e.is_alive:
                continue
            # Build description using perceive if observer is a Character
            desc = creature.perceive(e) if isinstance(creature, Character) and isinstance(e, Entity) else e.name
            is_wounded = isinstance(e, Creature) and e.current_hp < e.max_hp // 2
            distance_ft = 0
            direction = ""
            other_pos = battle_map_positions.get(e.id)
            if my_pos is not None and other_pos is not None:
                distance_ft = grid_distance(my_pos, other_pos)
                dx = other_pos.x - my_pos.x
                dy = other_pos.y - my_pos.y
                direction = direction_label(dx, dy)
            e_conditions = frozenset(e.conditions) if isinstance(e, Creature) else frozenset()
            # In combat with sides: use sides as single source of truth.
            # Without sides or outside combat: fall back to faction relation query.
            if combat and combat.entity_to_side and creature.id in combat.entity_to_side:
                is_hostile = not are_allies(combat, creature.id, e.id)
            else:
                is_hostile = self.check_faction_hostility(creature, e, query_fn)
            nearby.append(
                CombatEntity(
                    id=e.id,
                    description=desc,
                    is_wounded=is_wounded,
                    is_hostile=is_hostile,
                    distance_ft=distance_ft,
                    direction=direction,
                    x=other_pos.x if other_pos else 0,
                    y=other_pos.y if other_pos else 0,
                    conditions=e_conditions,
                )
            )

        from dnd_simulator.rules.modifiers import effective_ac, effective_speed
        from dnd_simulator.rules.weapons import get_weapon_attack

        weapon_attack = get_weapon_attack(creature)
        weapon_name = weapon_attack.name
        weapon_damage = str(weapon_attack.damage[0].dice) if weapon_attack.damage else "1"

        wall_descriptions: list[str] = []
        battle_map_ascii = ""
        battle_map_width = 0
        battle_map_height = 0
        battle_map_walls: list[dict[str, int]] = []
        if combat:
            wall_descriptions = combat.battle_map.describe_walls()
            battle_map_ascii = combat.battle_map.render_ascii(creature.id)
            battle_map_width = combat.battle_map.width
            battle_map_height = combat.battle_map.height
            battle_map_walls = [
                {"x1": w.x1, "y1": w.y1, "x2": w.x2, "y2": w.y2} for w in combat.battle_map._inner_walls
            ]

        resource_pools = tuple(
            ResourcePoolInfo(id=p.id, max_uses=p.max_uses, current_uses=p.current_uses) for p in creature.resource_pools
        )

        return CombatAwareness(
            self_hp=creature.current_hp,
            self_max_hp=creature.max_hp,
            self_ac=effective_ac(creature),
            self_speed=effective_speed(creature),
            self_weapon=weapon_name,
            self_weapon_damage=weapon_damage,
            self_x=my_pos.x if my_pos else 0,
            self_y=my_pos.y if my_pos else 0,
            nearby=nearby,
            round_number=round_number,
            walls=wall_descriptions,
            battle_map_ascii=battle_map_ascii,
            battle_map_width=battle_map_width,
            battle_map_height=battle_map_height,
            battle_map_walls=battle_map_walls,
            self_conditions=frozenset(creature.conditions),
            is_disengaging=creature.is_disengaging,
            self_resource_pools=resource_pools,
        )

    def build_nearby_entities(
        self, creature: Creature, hour: int, query_fn: QueryFn | None = None
    ) -> list[NearbyEntity]:
        """Build list of nearby entities for peaceful awareness."""
        from dnd_simulator.core.awareness import ItemInfo, describe_item
        from dnd_simulator.core.loot import InventoryHolder
        from dnd_simulator.rules.loot import is_lootable

        result: list[NearbyEntity] = []
        creature_location = creature.location_id
        if isinstance(creature, Npc):
            creature_location = creature.current_location(hour)
        for e in self._entities.values():
            if e.id == creature.id:
                continue
            # Determine effective location
            e_location = e.location_id
            if isinstance(e, Npc):
                e_location = e.current_location(hour)
            if e_location != creature_location:
                continue
            lootable = is_lootable(e)
            # Corpses are dormant after death — surface them as loot anyway. Other
            # inactive/dead entities stay hidden.
            if not lootable:
                if not e.active:
                    continue
                if isinstance(e, Creature) and not e.is_alive:
                    continue
            desc = creature.perceive(e) if isinstance(creature, Character) and isinstance(e, Entity) else e.name
            is_wounded = isinstance(e, Creature) and e.is_alive and e.current_hp < e.max_hp // 2
            is_dead = isinstance(e, Creature) and not e.is_alive
            is_hostile = (not lootable) and self.check_faction_hostility(creature, e, query_fn)
            relation = self._resolve_relation(creature, e, query_fn)
            loot_items: list[ItemInfo] = []
            loot_gold = 0
            if lootable and isinstance(e, InventoryHolder):
                loot_items = [
                    ItemInfo(
                        id=i.id,
                        name=i.name,
                        description=describe_item(i),
                        item_type=str(i.item_type),
                        price=i.price,
                    )
                    for i in e.inventory
                ]
                loot_gold = e.gold
            # Structured fields for inspect card — all populated from AwarenessBuilder
            name = e.name
            race = ""
            role = ""
            faction_id = e.faction_id
            faction_name = self._resolve_faction_name(faction_id, query_fn)
            npc_description = ""
            is_merchant = False
            if isinstance(e, Character):
                race = e.race.value
            if isinstance(e, Npc):
                role = e.role.value
                npc_description = e.description
                is_merchant = e.is_merchant
            result.append(
                NearbyEntity(
                    id=e.id,
                    description=desc,
                    is_wounded=is_wounded,
                    is_hostile=is_hostile,
                    is_dead=is_dead,
                    name=name,
                    race=race,
                    role=role,
                    faction_id=faction_id,
                    faction_name=faction_name,
                    relation=relation,
                    npc_description=npc_description,
                    is_merchant=is_merchant,
                    lootable=lootable,
                    loot_items=loot_items,
                    loot_gold=loot_gold,
                )
            )
        if result:
            logger.info(
                "awareness_nearby",
                creature_id=creature.id,
                location=creature_location,
                nearby=[{"id": n.id, "hostile": n.is_hostile} for n in result],
            )
        return result

    def _resolve_faction_name(self, faction_id: str, query_fn: QueryFn | None) -> str:
        """Resolve faction_id to a display name via politics query. Returns '' if unavailable."""
        if not faction_id or query_fn is None:
            return ""
        try:
            return query_faction_name(query_fn, faction_id) or ""
        except (KeyError, ValueError, LayerError):
            return ""

    def _resolve_relation(self, observer: Entity, other: Entity, query_fn: QueryFn | None) -> str:
        """Resolve the relation string between observer and other entity."""
        if not observer.faction_id or not other.faction_id:
            return FactionRelation.NEUTRAL.value
        if query_fn is None:
            return FactionRelation.NEUTRAL.value

        try:
            get_faction_relation = make_relation_fn(query_fn)

            if isinstance(observer, Creature) and isinstance(other, Creature):
                relation = effective_relation(observer, other, get_faction_relation)
            else:
                if observer.faction_id == other.faction_id:
                    return FactionRelation.FRIENDLY.value
                relation = get_faction_relation(observer.faction_id, other.faction_id)

            return relation.value
        except (KeyError, ValueError, LayerError):
            return FactionRelation.NEUTRAL.value

    def check_faction_hostility(self, observer: Entity, other: Entity, query_fn: QueryFn | None) -> bool:
        """Check if two entities are hostile based on effective relation (reputation + faction)."""
        if not observer.faction_id or not other.faction_id:
            return False
        if query_fn is None:
            return False

        try:
            get_faction_relation = make_relation_fn(query_fn)

            if isinstance(observer, Creature) and isinstance(other, Creature):
                relation = effective_relation(observer, other, get_faction_relation)
            else:
                # Plain Entity — no reputation, use faction-only logic
                if observer.faction_id == other.faction_id:
                    return False
                relation = get_faction_relation(observer.faction_id, other.faction_id)

            is_hostile = relation == FactionRelation.HOSTILE
            logger.info(
                "faction_hostility_check",
                observer=observer.id,
                other=other.id,
                observer_faction=observer.faction_id,
                other_faction=other.faction_id,
                relation=str(relation),
                hostile=is_hostile,
            )
            return is_hostile
        except (KeyError, ValueError, LayerError):
            logger.warning(
                "faction_relation_query_failed",
                a=observer.faction_id,
                b=other.faction_id,
                exc_info=True,
            )
            return False
