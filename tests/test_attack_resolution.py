"""Tests for attack resolution through EntitiesLayer.handle_event."""

from __future__ import annotations

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.layers.entities.layer import EntitiesLayer


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


def _attack_event(attacker_id: str = "attacker", target_id: str = "target", weapon: str = "longsword") -> Event:
    return Event(
        event_type=EventType.ENTITY_ATTACK,
        source_layer="entities",
        data={"attacker_id": attacker_id, "target_id": target_id, "weapon": weapon},
    )


class TestAttackResolution:
    def test_attack_reduces_target_hp(self) -> None:
        scores = AbilityScores()
        scores[Ability.STR] = 18  # +4 modifier, should hit AC 10 most of the time
        attacker = Character(id="attacker", name="Fighter", region_id="r1", ability_scores=scores, attacks=(_sword(),))
        target = Character(id="target", name="Goblin", region_id="r1", max_hp=20, current_hp=20, ac=5)
        layer = EntitiesLayer(entities=[attacker, target])

        # Run many attacks — at least some should hit
        hits = 0
        for _ in range(20):
            target.current_hp = 20  # reset
            layer.handle_event(_attack_event())
            if target.current_hp < 20:
                hits += 1
        assert hits > 0, "No attacks hit in 20 tries"

    def test_attack_logs_to_region(self) -> None:
        attacker = Character(id="attacker", name="Fighter", region_id="r1", attacks=(_sword(),))
        target = Character(id="target", name="Goblin", region_id="r1", max_hp=20, current_hp=20, ac=5)
        layer = EntitiesLayer(entities=[attacker, target])

        layer.handle_event(_attack_event())

        log = layer.get_perceived_log(target)
        assert len(log) >= 1
        assert "атакует тебя" in log[0]

    def test_death_generates_event(self) -> None:
        attacker = Character(id="attacker", name="Fighter", region_id="r1", attacks=(_sword(),))
        target = Character(id="target", name="Goblin", region_id="r1", max_hp=1, current_hp=1, ac=1)
        layer = EntitiesLayer(entities=[attacker, target])

        # With AC 1, should hit easily; 1 HP means any damage kills
        result_events: list[Event] = []
        for _ in range(20):
            target.current_hp = 1
            target.active = True
            result_events = layer.handle_event(_attack_event())
            if result_events:
                break

        death_events = [e for e in result_events if e.event_type == EventType.ENTITY_DIED]
        assert len(death_events) == 1
        assert death_events[0].data["entity_id"] == "target"
        assert target.active is False

    def test_unknown_weapon_no_damage(self) -> None:
        attacker = Character(id="attacker", name="Fighter", region_id="r1", attacks=(_sword(),))
        target = Character(id="target", name="Goblin", region_id="r1", max_hp=20, current_hp=20)
        layer = EntitiesLayer(entities=[attacker, target])

        event = _attack_event(weapon="unknown_weapon")
        layer.handle_event(event)
        assert target.current_hp == 20

    def test_nonexistent_target_no_crash(self) -> None:
        attacker = Character(id="attacker", name="Fighter", region_id="r1", attacks=(_sword(),))
        layer = EntitiesLayer(entities=[attacker])

        event = _attack_event(target_id="nonexistent")
        result = layer.handle_event(event)
        assert result == []
