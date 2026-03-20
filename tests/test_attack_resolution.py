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
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.layers.entities.layer import EntitiesLayer


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


def _attack_event(attacker_id: str = "attacker", target_id: str = "target") -> Event:
    return Event(
        event_type=EventType.ENTITY_ATTACK,
        source_layer="entities",
        data={"attacker_id": attacker_id, "target_id": target_id},
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
            result = layer.handle_event(_attack_event())
            assert result.success
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
        result: ActionResult = ActionResult()
        for _ in range(20):
            target.current_hp = 1
            target.active = True
            result = layer.handle_event(_attack_event())
            assert result.success
            if result.events:
                break

        death_events = [e for e in result.events if e.event_type == EventType.ENTITY_DIED]
        assert len(death_events) == 1
        assert death_events[0].data["entity_id"] == "target"
        assert target.active is False

    def test_unarmed_strike_when_no_weapons(self) -> None:
        """Creatures with no attacks fall back to unarmed strike (1 bludgeoning)."""
        scores = AbilityScores()
        scores[Ability.STR] = 18  # +4 modifier, should hit AC 5 easily
        attacker = Character(id="attacker", name="Monk", region_id="r1", attacks=(), ability_scores=scores)
        target = Character(id="target", name="Goblin", region_id="r1", max_hp=20, current_hp=20, ac=5)
        layer = EntitiesLayer(entities=[attacker, target])

        hits = 0
        for _ in range(20):
            target.current_hp = 20
            result = layer.handle_event(_attack_event())
            assert result.success  # unarmed strike always valid
            if target.current_hp < 20:
                hits += 1
        assert hits > 0, "No unarmed strikes hit in 20 tries"

    def test_nonexistent_target_returns_error(self) -> None:
        attacker = Character(id="attacker", name="Fighter", region_id="r1", attacks=(_sword(),))
        layer = EntitiesLayer(entities=[attacker])

        result = layer.handle_event(_attack_event(target_id="nonexistent"))
        assert not result.success
        assert "nonexistent" in result.error

    def test_cross_region_attack_returns_error(self) -> None:
        attacker = Character(id="attacker", name="Fighter", region_id="r1", attacks=(_sword(),))
        target = Character(id="target", name="Goblin", region_id="r2", max_hp=20, current_hp=20)
        layer = EntitiesLayer(entities=[attacker, target])

        result = layer.handle_event(_attack_event())
        assert not result.success
        assert "не в этом регионе" in result.error
        assert target.current_hp == 20

    def test_attack_dead_target_returns_error(self) -> None:
        attacker = Character(id="attacker", name="Fighter", region_id="r1", attacks=(_sword(),))
        target = Character(id="target", name="Goblin", region_id="r1", max_hp=20, current_hp=0)
        layer = EntitiesLayer(entities=[attacker, target])

        result = layer.handle_event(_attack_event())
        assert not result.success
        assert "мертва" in result.error
