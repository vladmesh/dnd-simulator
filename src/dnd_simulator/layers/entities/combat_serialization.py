"""Combat state serialization — save/load active combats."""

from __future__ import annotations

from dnd_simulator.core.combat import BattleMap, CombatState, Position, Wall


def serialize_combats(combats: dict[str, CombatState]) -> dict[str, object]:
    """Serialize all active combats to a dict for saving."""
    result: dict[str, object] = {}
    for loc_id, combat in combats.items():
        bm = combat.battle_map
        positions = {eid: {"x": pos.x, "y": pos.y} for eid, pos in bm.positions.items()}
        walls = [{"x1": w.x1, "y1": w.y1, "x2": w.x2, "y2": w.y2} for w in bm._inner_walls]
        result[loc_id] = {
            "location_id": combat.location_id,
            "turn_order": list(combat.turn_order),
            "round_number": combat.round_number,
            "rounds_without_attack": combat.rounds_without_attack,
            "sides": {side: sorted(members) for side, members in combat.sides.items()},
            "entity_to_side": dict(combat.entity_to_side),
            "battle_map": {
                "width": bm.width,
                "height": bm.height,
                "positions": positions,
                "walls": walls,
            },
        }
    return result


def deserialize_combats(data: dict[str, object]) -> dict[str, CombatState]:
    """Restore active combats from saved data."""
    combats: dict[str, CombatState] = {}
    for loc_id, cdata in data.items():
        assert isinstance(cdata, dict)
        bm_data = cdata["battle_map"]
        assert isinstance(bm_data, dict)

        walls = [
            Wall(x1=int(w["x1"]), y1=int(w["y1"]), x2=int(w["x2"]), y2=int(w["y2"])) for w in bm_data.get("walls", [])
        ]
        bm = BattleMap(width=int(bm_data["width"]), height=int(bm_data["height"]), walls=walls)

        positions_raw = bm_data.get("positions", {})
        assert isinstance(positions_raw, dict)
        for eid, pos_data in positions_raw.items():
            assert isinstance(pos_data, dict)
            bm.set_position(str(eid), Position(x=int(pos_data["x"]), y=int(pos_data["y"])))

        combats[str(loc_id)] = CombatState(
            location_id=str(cdata["location_id"]),
            turn_order=list(cdata["turn_order"]),
            round_number=int(cdata["round_number"]),
            rounds_without_attack=int(cdata.get("rounds_without_attack", 0)),
            battle_map=bm,
            sides={int(side): {str(member) for member in members} for side, members in cdata.get("sides", {}).items()},
            entity_to_side={str(entity_id): int(side) for entity_id, side in cdata.get("entity_to_side", {}).items()},
        )
    return combats
