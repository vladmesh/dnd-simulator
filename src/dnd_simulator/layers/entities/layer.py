"""EntitiesLayer — all tracked creatures: player, NPCs, named monsters."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from dnd_simulator.core.character import Attack, Character, Creature, Entity
from dnd_simulator.core.layer import Layer
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
from dnd_simulator.layers.entities.models import Npc, NpcActivity
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.rules.combat import resolve_attack

if TYPE_CHECKING:
    from dnd_simulator.core.models import TimeDelta
    from dnd_simulator.core.world import WorldState

# Event types that get recorded in the region log
_LOGGED_EVENTS = {EventType.ENTITY_SAY, EventType.ENTITY_ATTACK, EventType.ENTITY_DIED}


class EntitiesLayer(Layer):
    """All tracked entities: player, NPCs, named creatures."""

    def __init__(self, entities: list[Entity] | None = None) -> None:
        self._entities: dict[str, Entity] = {}
        self._region_log: dict[str, list[Event]] = defaultdict(list)
        if entities:
            for e in entities:
                self._entities[e.id] = e

    @property
    def name(self) -> str:
        return "entities"

    @property
    def tick_interval(self) -> int:
        return 0  # tick every advance_time call

    # -- Direct access (not through query) --

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID. Returns direct reference."""
        return self._entities.get(entity_id)

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the layer."""
        self._entities[entity.id] = entity

    def remove_entity(self, entity_id: str) -> None:
        """Remove an entity from the layer."""
        self._entities.pop(entity_id, None)

    def active_creatures_in_region(self, region_id: str, exclude_id: str = "") -> list[Creature]:
        """Get active creatures in a region (for turn polling)."""
        return [
            e
            for e in self._entities.values()
            if isinstance(e, Creature) and e.active and e.region_id == region_id and e.id != exclude_id
        ]

    def get_active_creatures(self) -> list[Creature]:
        """Get all active creatures in the world (for the main game loop)."""
        return [e for e in self._entities.values() if isinstance(e, Creature) and e.active]

    # -- Layer interface --

    def tick(self, delta: TimeDelta, world_state: WorldState) -> list[Event]:
        """Update all active entities."""
        hour = world_state.time.hour
        for entity in self._entities.values():
            if entity.active:
                entity.on_tick(hour)
        return []

    def handle_event(self, event: Event) -> ActionResult:
        """React to world events. Resolve attacks, log relevant events."""
        if event.event_type == EventType.ENTITY_ATTACK:
            return self._resolve_attack(event)

        if event.event_type in _LOGGED_EVENTS:
            region_id = self._event_region(event)
            if region_id:
                self._region_log[region_id].append(event)

        return ActionResult()

    def _resolve_attack(self, event: Event) -> ActionResult:
        """Validate and resolve an attack: check constraints, roll dice, apply damage, log."""
        attacker_id = str(event.data.get("attacker_id", ""))
        target_id = str(event.data.get("target_id", ""))
        weapon_name = str(event.data.get("weapon", ""))

        # --- Validation ---
        attacker = self._entities.get(attacker_id)
        if not isinstance(attacker, Creature):
            return ActionResult(success=False, error=f"Атакующий '{attacker_id}' не найден.")

        target = self._entities.get(target_id)
        if not isinstance(target, Creature):
            return ActionResult(success=False, error=f"Цель '{target_id}' не найдена.")

        if not attacker.is_alive:
            return ActionResult(success=False, error="Ты мёртв и не можешь атаковать.")

        if not target.is_alive:
            return ActionResult(success=False, error=f"Цель '{target_id}' уже мертва.")

        if attacker.region_id != target.region_id:
            return ActionResult(success=False, error=f"Цель '{target_id}' не в этом регионе.")

        # Find the weapon
        attack: Attack | None = None
        for a in attacker.attacks:
            if a.name == weapon_name:
                attack = a
                break
        if attack is None:
            return ActionResult(success=False, error=f"Оружие '{weapon_name}' не найдено.")

        # --- Resolution ---
        modifier = attacker.ability_scores.modifier(attack.ability)
        result = resolve_attack(modifier=modifier, ac=target.ac, attack=attack)

        # Build enriched event for the log (with damage info)
        log_data: dict[str, Any] = {
            "attacker_id": attacker_id,
            "target_id": target_id,
            "weapon": weapon_name,
            "hit": result.hit,
            "critical": result.critical,
            "roll": result.attack_check.roll,
            "total": result.attack_check.total,
        }

        result_events: list[Event] = []

        if result.hit:
            actual_damage = target.take_damage(result.total_damage)
            log_data["damage"] = actual_damage
            log_data["damage_types"] = [d.type.value for d in result.damage]

            if not target.is_alive:
                target.active = False
                death_event = Event(
                    event_type=EventType.ENTITY_DIED,
                    source_layer="entities",
                    data={"entity_id": target_id},
                )
                result_events.append(death_event)
                self._region_log[target.region_id].append(death_event)

        # Log the attack in the attacker's region
        attack_log_event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data=log_data,
        )
        self._region_log[attacker.region_id].append(attack_log_event)

        return ActionResult(success=True, events=result_events)

    def get_perceived_log(self, observer: Character) -> list[str]:
        """Get ALL events in observer's region that the observer can see.

        Used for NPC LLM prompts — full history as context/memory.
        Filters by observer_ids: events with observer_ids set are only visible
        to listed entities.
        """
        events = self._region_log.get(observer.region_id, [])
        if not events:
            return []
        return [
            perceive_event(e, observer, self.get_entity)
            for e in events
            if e.observer_ids is None or observer.id in e.observer_ids
        ]

    def get_new_perceived_events(self, observer: Character) -> list[str]:
        """Get only events since this observer last checked that they can see.

        Updates the observer's index. Used for player display.
        """
        events = self._region_log.get(observer.region_id, [])
        last_seen = observer._last_seen_log_index
        new_events = events[last_seen:]
        observer._last_seen_log_index = len(events)
        if not new_events:
            return []
        return [
            perceive_event(e, observer, self.get_entity)
            for e in new_events
            if e.observer_ids is None or observer.id in e.observer_ids
        ]

    def _event_region(self, event: Event) -> str | None:
        """Determine which region an event happened in."""
        # Try to find region from event participants
        for key in ("entity_id", "attacker_id"):
            eid = event.data.get(key)
            if isinstance(eid, str):
                entity = self._entities.get(eid)
                if entity:
                    return entity.region_id
        return None

    def query(self, query: Query) -> Answer:
        """Answer queries about entities.

        Supported queries:
        - "entities_in_region": params={region_id} -> entities in a region
        - "entity_info": params={entity_id} -> full entity data
        - "perceived_log": params={entity_id} -> recent events from entity's POV
        """
        q = query.question
        params = query.params

        if q == "entities_in_region":
            region_id = params["region_id"]
            result = []
            for e in self._entities.values():
                if e.region_id == region_id:
                    result.append(self._entity_summary(e))
            return Answer(value=result)

        if q == "entity_info":
            e = self._entities[params["entity_id"]]
            return Answer(value=self._entity_detail(e))

        if q == "perceived_log":
            e = self._entities[params["entity_id"]]
            if isinstance(e, Character):
                return Answer(value=self.get_perceived_log(e))
            return Answer(value=[])

        if q == "new_perceived_events":
            e = self._entities[params["entity_id"]]
            if isinstance(e, Character):
                return Answer(value=self.get_new_perceived_events(e))
            return Answer(value=[])

        raise ValueError(f"Unknown entities query: {q}")

    def _entity_summary(self, entity: Entity) -> dict[str, object]:
        """Short summary for listings."""
        base: dict[str, object] = {
            "id": entity.id,
            "name": entity.name,
        }
        if isinstance(entity, Npc):
            base["role"] = entity.role
            base["activity"] = entity.activity.value
            base["location_label"] = entity.location_label
        return base

    def _entity_detail(self, entity: Entity) -> dict[str, object]:
        """Full detail for a single entity."""
        base: dict[str, object] = {
            "id": entity.id,
            "name": entity.name,
            "region_id": entity.region_id,
            "active": entity.active,
        }
        if isinstance(entity, Npc):
            base.update(
                {
                    "role": entity.role,
                    "personality": entity.personality,
                    "settlement_id": entity.settlement_id,
                    "activity": entity.activity.value,
                    "location_label": entity.location_label,
                    "conversation_summary": entity.conversation_summary,
                }
            )
        return base

    def get_state(self) -> dict[str, object]:
        """Serialize entities state."""
        entities: dict[str, Any] = {}
        for eid, e in self._entities.items():
            data: dict[str, Any] = {
                "id": e.id,
                "name": e.name,
                "region_id": e.region_id,
                "active": e.active,
            }
            if isinstance(e, Npc):
                data.update(
                    {
                        "role": e.role,
                        "personality": e.personality,
                        "settlement_id": e.settlement_id,
                        "activity": e.activity.value,
                        "location_label": e.location_label,
                        "conversation_summary": e.conversation_summary,
                    }
                )
            entities[eid] = data
        return {"entities": entities}

    def load_state(self, state: dict[str, object]) -> None:
        """Restore mutable entity state from saved data."""
        entities_data = state["entities"]
        assert isinstance(entities_data, dict)

        for eid, edata in entities_data.items():
            assert isinstance(edata, dict)
            entity = self._entities.get(str(eid))
            if entity:
                entity.active = bool(edata.get("active", True))
                if isinstance(entity, Npc):
                    entity.activity = NpcActivity(str(edata.get("activity", "idle")))
                    entity.location_label = str(edata.get("location_label", "home"))
                    entity.conversation_summary = str(edata.get("conversation_summary", ""))
