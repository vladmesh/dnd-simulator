"""Leaving a fight's scene — the one place a flee takes effect.

A location with an active ``CombatState`` is a scene. Leaving the fight means
leaving the scene: nobody may stay at that location, active, outside the fight
("a ghost on the scene"). ``exit_scene`` is the only code that applies a flee,
for the player and for every NPC, and it always ends with the fleer off the
scene:

- everyone first leaves the combat (turn order, map, sides; the combat ends if
  no opposing sides remain);
- an anonymous creature (a template spawn: squad member, lair member, random
  encounter) leaves the world; a squad/lair member is kept by its roster as a
  survivor, so its strength counts it alive;
- a named creature (the player, a named NPC) starts an ordinary one-edge
  journey to the chosen neighbour and goes dormant. Arrival, travel time and
  the arrival encounter roll are the regular travel machinery. A named NPC
  stays where it fled to, with its wounds.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.intent import TravelIntent

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.events import EntityFleePayload
    from dnd_simulator.layers.entities.combat_manager import CombatManager

logger = structlog.get_logger(domain="entity")


def exit_scene(
    creature: Creature,
    payload: EntityFleePayload,
    combat: CombatManager,
    withdraw_anonymous: Callable[[Creature], None],
    dormify: Callable[[Creature], None],
) -> None:
    """Take *creature* out of its fight and off the scene (see module docstring)."""
    from dnd_simulator.layers.entities.models import Npc

    origin = creature.location_id
    creature.in_combat = False
    creature.is_dodging = False
    combat.remove_from_combat(origin, creature.id)

    if creature.temporary:
        withdraw_anonymous(creature)
        logger.info("scene_exit_withdrawn", entity_id=creature.id, location_id=origin)
        return

    destination = payload.destination_id
    creature.current_intent = TravelIntent(
        started_at_seconds=payload.departed_at_seconds,
        destination_id=destination,
        remaining_route=(destination,),
        next_arrival_seconds=payload.arrival_at_seconds,
    )
    if isinstance(creature, Npc):
        # A named NPC stays where it fled to; its schedule must not pull it back
        # onto the scene it just left. While the journey is pending the override
        # is not read (``Npc.current_location``): it takes effect on arrival.
        creature.location_override = destination
    dormify(creature)
    logger.info(
        "scene_exit_journey",
        entity_id=creature.id,
        from_location=origin,
        destination_id=destination,
        arrival_at=payload.arrival_at_seconds,
    )
