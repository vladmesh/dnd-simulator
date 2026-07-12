"""Attack resolution helpers — event builders, dice rolling, move resolution.

Extracted from CombatManager to keep event serialization and action mechanics
separate from combat lifecycle management.
"""

from __future__ import annotations

import random

import structlog

from dnd_simulator.core.character import Attack, Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.events import EntityMovePayload
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.core.modifiers import AttackModifiers, RollComponent
from dnd_simulator.i18n import _
from dnd_simulator.rules.combat import AttackResult
from dnd_simulator.rules.movement import grid_distance, move_direction

logger = structlog.get_logger(domain="combat")


def build_attack_event(
    attacker_id: str,
    target_id: str,
    attack: Attack,
    result: AttackResult,
    atk_mods: AttackModifiers,
    rolled_dice: list[RollComponent],
) -> dict[str, object]:
    """Build structured attack event data from resolution result."""
    all_roll_components = [
        {"source": rc.source, "value": rc.value, "dice": rc.dice} for rc in atk_mods.roll_components if not rc.dice
    ] + [{"source": rc.source, "value": rc.value, "dice": rc.dice} for rc in rolled_dice]

    d20 = result.attack_check.d20
    d20_data: dict[str, object] = {"result": d20.die.result, "sides": d20.die.sides}
    atk_roll_data: dict[str, object] = {
        "natural": result.attack_check.roll,
        "d20": d20_data,
        "components": all_roll_components,
        "total": result.attack_check.total,
        "advantage": atk_mods.advantage,
        "disadvantage": atk_mods.disadvantage,
    }
    if d20.alt is not None:
        atk_roll_data["d20_alt"] = {"result": d20.alt.result, "sides": d20.alt.sides}

    return {
        "attacker_id": attacker_id,
        "target_id": target_id,
        "weapon": attack.name,
        "hit": result.hit,
        "critical": result.critical,
        "ac": atk_mods.target_ac,
        "attack_roll": atk_roll_data,
    }


def build_damage_components(
    result: AttackResult,
    damage_components: list[RollComponent] | tuple[RollComponent, ...],
) -> list[dict[str, object]]:
    """Build damage component list for event data."""
    components: list[dict[str, object]] = []
    for dr in result.damage:
        dice_detail: list[dict[str, object]] = []
        if dr.dice_result is not None:
            for die in dr.dice_result.dice:
                entry: dict[str, object] = {"sides": die.sides, "result": die.result}
                if die.original is not None:
                    entry["original"] = die.original
                dice_detail.append(entry)
        components.append(
            {
                "source": dr.source,
                "dice": dr.dice,
                "dice_detail": dice_detail,
                "amount": dr.amount,
                "type": dr.type.value,
            }
        )
    primary_type = result.damage[0].type.value if result.damage else "bludgeoning"
    for dbc in damage_components:
        components.append(
            {
                "source": dbc.source,
                "dice": "",
                "dice_detail": [],
                "amount": dbc.value,
                "type": primary_type,
            }
        )
    return components


def roll_attack_dice(atk_mods: AttackModifiers, *, rng: random.Random | None = None) -> tuple[list[RollComponent], int]:
    """Roll dice bonuses (Bless +1d4, etc.). Returns (rolled_components, total)."""
    rolled_dice: list[RollComponent] = []
    dice_total = 0
    if atk_mods.dice_bonuses:
        from dnd_simulator.rules.dice import roll as roll_dice_fn

        for rc in atk_mods.roll_components:
            if rc.dice:
                rolled_value = roll_dice_fn(rc.dice, rng=rng).total
                rolled_dice.append(RollComponent(source=rc.source, value=rolled_value, dice=rc.dice))
                dice_total += rolled_value
    return rolled_dice, dice_total


def resolve_combat_move(
    entity: Creature,
    event: Event,
    combat: CombatState,
    location_log: dict[str, list[Event]],
) -> ActionResult:
    """Resolve an atomic combat move: single step in a compass direction.

    Returns success=False if blocked (wall, occupied cell, off-map).
    """
    entity_id = entity.id
    bm = combat.battle_map
    cur_pos = bm.get_position(entity_id)
    if cur_pos is None:
        return ActionResult(success=False, error=_("Creature not on the battle map."))

    direction = str(event.data.get("direction", ""))
    ft = int(event.data.get("ft", 5))
    new_pos = move_direction(cur_pos, direction, ft, bm, entity_id)

    if new_pos == cur_pos:
        logger.info(
            "move_blocked",
            entity_id=entity_id,
            pos=(cur_pos.x, cur_pos.y),
            direction=direction,
            battle_map="\n" + bm.render_ascii(),
        )
        return ActionResult(success=False, error=_("Cannot move there — blocked."))

    bm.set_position(entity_id, new_pos)
    moved_ft = grid_distance(cur_pos, new_pos)

    location_log[entity.location_id].append(
        Event(
            event_type=EventType.ENTITY_MOVE,
            source_layer="entities",
            data=EntityMovePayload(
                entity_id=entity_id,
                location_id=entity.location_id,
                from_x=cur_pos.x,
                from_y=cur_pos.y,
                to_x=new_pos.x,
                to_y=new_pos.y,
                distance_ft=moved_ft,
            ),
        )
    )
    return ActionResult(success=True)
