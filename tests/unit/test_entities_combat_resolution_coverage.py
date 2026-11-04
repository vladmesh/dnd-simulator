"""Coverage for invalid attackers and kill events with existing personal reputation."""

from __future__ import annotations

import pytest
from test_combat_resolution_branches import _attack_event, _creature, _manager

from dnd_simulator.core.container import Container
from dnd_simulator.core.events import EntityDiedPayload, ReputationChangedPayload
from dnd_simulator.core.models import EventType
from dnd_simulator.layers.entities.combat_resolution import handle_death, resolve_attack
from dnd_simulator.rules.checks import CheckResult
from dnd_simulator.rules.combat import AttackResult


@pytest.mark.parametrize("attacker_id", ["ghost", "chest"])
def test_attack_rejects_missing_or_non_creature_attacker(attacker_id: str) -> None:
    target = _creature("guard")
    chest = Container(id="chest", name="Chest", location_id="arena")
    mgr = _manager(target, chest)

    result = resolve_attack(mgr, _attack_event(attacker_id, target.id))

    assert result.success is False
    assert result.error == f"Attacker '{attacker_id}' not found."
    assert target.current_hp == 10
    assert mgr.get_combat_locations() == []
    assert not mgr._location_log


@pytest.mark.parametrize(("old_rep", "new_rep"), [(60, 40), (10, 0)])
def test_kill_reports_existing_reputation_and_clamps_drop(old_rep: int, new_rep: int) -> None:
    killer = _creature("hero", "guild")
    killer.reputation["town"] = old_rep
    victim = _creature("guard", "town", hp=0)
    victim.in_combat = True
    mgr = _manager(killer, victim)
    hit = AttackResult(
        hit=True,
        critical=False,
        attack_check=CheckResult(success=True, roll=15, total=15, dc=10, critical=False),
        damage=(),
        total_damage=10,
    )

    result = handle_death(mgr, killer, victim, victim.id, hit)

    assert result.success is True
    assert victim.in_combat is False
    assert killer.reputation == {"town": new_rep}
    assert [event.event_type for event in result.events] == [EventType.ENTITY_DIED, EventType.REPUTATION_CHANGED]
    assert result.events[0].data == EntityDiedPayload(victim.id, "arena", killer.id, victim.lair_origin)
    assert result.events[1].data == ReputationChangedPayload(
        entity_id=killer.id,
        faction_id="town",
        old_rep=old_rep,
        new_rep=new_rep,
        delta=new_rep - old_rep,
        reason="kill",
        faction_name=None,
        location_id="arena",
    )
    assert mgr._location_log["arena"] == result.events
