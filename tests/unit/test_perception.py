"""Tests for event perception and region log."""

from __future__ import annotations

import pytest

import dnd_simulator.layers.entities.perception as perception_mod
from dnd_simulator.core.character import Ability, Attack, Character, DamageComponent, DamageType, Entity, Race
from dnd_simulator.core.events import (
    AttackRequestedPayload,
    AttackResolvedPayload,
    AttackRollPayload,
    CombatEndedPayload,
    DamageComponentPayload,
    EncounterSpawnedPayload,
    EntityActorPayload,
    EntityDiedPayload,
    EntityLayOnHandsPayload,
    EntitySayPayload,
    EntitySecondWindPayload,
    EntityUseItemPayload,
    EquipmentPayload,
    InspectPayload,
    ReputationChangedPayload,
    RollComponentPayload,
    RoundStartPayload,
    SquadDematerializedPayload,
    TakePayload,
    WeatherChangedPayload,
)
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
from dnd_simulator.i18n import set_language
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.perception import perceive_event


def _has_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _get_entity_fn(*entities: Entity):
    """Build a simple get_entity function from a list of entities."""
    by_id = {e.id: e for e in entities}
    return lambda eid: by_id.get(eid)


def _attack_payload(**overrides: object) -> AttackResolvedPayload:
    fields: dict[str, object] = {
        "attacker_id": "player",
        "target_id": "npc",
        "weapon": "Longsword",
        "hit": True,
        "critical": False,
        "ac": 13,
        "attack_roll": AttackRollPayload(14, (RollComponentPayload("ability", 3),), 17, False, False),
        "damage": 8,
        "damage_components": (
            DamageComponentPayload("weapon", "1d8", (), 5, "slashing"),
            DamageComponentPayload("ability", "", (), 3, "slashing"),
        ),
    }
    fields.update(overrides)
    return AttackResolvedPayload(**fields)  # type: ignore[arg-type]


class TestPerceiveEvent:
    def test_say_from_other(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        speaker = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data=EntitySayPayload(entity_id="smith", text="Добро пожаловать!"),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, speaker))
        assert "says" in result
        assert "Добро пожаловать!" in result
        assert "dwarf" in result

    def test_say_from_self(self) -> None:
        observer = Character(id="smith", name="Smith", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data=EntitySayPayload(
                **{"entity_id": "smith", "text": "Привет!"},
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "You say" in result

    def test_attack_observer_is_target(self) -> None:
        observer = Character(id="smith", name="Smith", location_id="r1")
        attacker = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data=_attack_payload(
                target_id="smith",
                weapon="longsword",
                damage=5,
                damage_components=(DamageComponentPayload("weapon", "1d8", (), 5, "slashing"),),
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, attacker))
        assert "attacks you" in result
        assert "longsword" in result
        assert "5 damage" in result

    def test_attack_observer_is_attacker(self) -> None:
        observer = Character(id="player", name="Hero", location_id="r1")
        target = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data=_attack_payload(
                target_id="smith",
                weapon="longsword",
                hit=False,
                ac=15,
                attack_roll=AttackRollPayload(8, (RollComponentPayload("ability", 3),), 11, False, False),
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, target))
        assert "You attack" in result
        assert "miss" in result

    def test_attack_observer_is_bystander(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        attacker = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        target = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data=_attack_payload(
                target_id="smith",
                weapon="",
                ac=10,
                attack_roll=AttackRollPayload(15, (), 15, False, False),
                damage=3,
                damage_components=(DamageComponentPayload("weapon", "1d4", (), 3, "bludgeoning"),),
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, attacker, target))
        assert "elf" in result
        assert "dwarf" in result
        assert "attacks" in result

    def test_death_other(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        victim = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_DIED,
            source_layer="entities",
            data=EntityDiedPayload(**{"entity_id": "smith"}),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, victim))
        assert "dies" in result
        assert "dwarf" in result

    def test_death_self(self) -> None:
        observer = Character(id="smith", name="Smith", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_DIED,
            source_layer="entities",
            data=EntityDiedPayload(**{"entity_id": "smith"}),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "You die" in result

    def test_unknown_event(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        event = Event(
            event_type=EventType.WEATHER_CHANGED,
            source_layer="geography",
            data=WeatherChangedPayload("r1", "clear", "rain", 10.0),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "Something happened" in result

    def test_combat_ended_has_localized_perception(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        event = Event(
            event_type=EventType.COMBAT_ENDED,
            source_layer="entities",
            data=CombatEndedPayload("r1"),
        )

        set_language("en")
        assert perceive_event(event, observer, _get_entity_fn(observer)) == "Combat ended."

        set_language("ru")
        assert perceive_event(event, observer, _get_entity_fn(observer)) == "Бой окончен."
        set_language("en")

    def test_unknown_entity_id(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data=EntitySayPayload(
                **{"entity_id": "unknown_npc", "text": "Бу!"},
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "someone" in result
        assert "Бу!" in result


class TestRegionLog:
    def test_handle_event_logs_say(self) -> None:
        smith = Character(id="smith", name="Smith", location_id="r1")
        layer = EntitiesLayer(entities=[smith])
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data=EntitySayPayload(
                **{"entity_id": "smith", "text": "Привет!"},
            ),
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        log = layer.get_perceived_log(smith)
        assert len(log) == 1
        assert "Привет!" in log[0]

    def test_log_only_for_same_region(self) -> None:
        smith = Character(id="smith", name="Smith", location_id="r1")
        guard = Character(id="guard", name="Guard", location_id="r2")
        layer = EntitiesLayer(entities=[smith, guard])
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data=EntitySayPayload(
                **{"entity_id": "smith", "text": "Привет!"},
            ),
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        assert len(layer.get_perceived_log(smith)) == 1
        assert len(layer.get_perceived_log(guard)) == 0

    def test_new_perceived_events_tracks_index(self) -> None:
        smith = Character(id="smith", name="Smith", location_id="r1")
        player = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        layer = EntitiesLayer(entities=[smith, player])

        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data=EntitySayPayload(
                    **{"entity_id": "player", "text": "Первое!"},
                ),
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        new1 = layer.get_new_perceived_events(smith)
        assert len(new1) == 1

        # Second call without new events — empty
        new2 = layer.get_new_perceived_events(smith)
        assert len(new2) == 0

        # Add another event
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data=EntitySayPayload(
                    **{"entity_id": "player", "text": "Второе!"},
                ),
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        new3 = layer.get_new_perceived_events(smith)
        assert len(new3) == 1
        assert "Второе!" in new3[0]

        # Full log still has everything
        full = layer.get_perceived_log(smith)
        assert len(full) == 2

    def test_non_logged_events_ignored(self) -> None:
        smith = Character(id="smith", name="Smith", location_id="r1")
        layer = EntitiesLayer(entities=[smith])
        event = Event(
            event_type=EventType.WEATHER_CHANGED,
            source_layer="geography",
            data=WeatherChangedPayload("r1", "clear", "rain", 10.0),
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        assert len(layer.get_perceived_log(smith)) == 0

    def test_multiple_events_in_order(self) -> None:
        from dnd_simulator.core.combat import Position

        smith = Character(id="smith", name="Smith", location_id="r1", max_hp=100, current_hp=100)
        sword = Attack(
            name="longsword",
            ability=Ability.STR,
            damage=(DamageComponent("1d8", DamageType.SLASHING),),
        )
        player = Character(id="player", name="Hero", location_id="r1", race=Race.ELF, attacks=(sword,))
        layer = EntitiesLayer(entities=[smith, player])

        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data=EntitySayPayload(
                    **{"entity_id": "player", "text": "Готовься!"},
                ),
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        # First attack starts combat — place in melee range, then attack again
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK_REQUESTED,
                source_layer="entities",
                data=AttackRequestedPayload(**{"attacker_id": "player", "target_id": "smith"}),
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        combat = layer.get_combat("r1")
        assert combat is not None
        combat.battle_map.set_position("player", Position(30, 30))
        combat.battle_map.set_position("smith", Position(35, 30))
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK_REQUESTED,
                source_layer="entities",
                data=AttackRequestedPayload(**{"attacker_id": "player", "target_id": "smith"}),
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )

        log = layer.get_perceived_log(smith)
        assert "Готовься!" in log[0]
        assert "Combat started" in log[1]
        assert any("attacks you" in line for line in log)


# ---------------------------------------------------------------------------
# i18n coverage: verify that dynamic values go through _()
# ---------------------------------------------------------------------------


def _mark_translator(original: object):
    """Return a translator that prefixes every string with [T]."""

    def marker(s: str) -> str:
        return f"[T]{s}"

    return marker


class TestCombatLogI18n:
    """Verify that damage types, source labels, weapon/item names, and 'AC'
    are passed through the gettext _() function in perception output."""

    def _attack_event(self, **overrides: object) -> Event:
        return Event(event_type=EventType.ENTITY_ATTACK, source_layer="entities", data=_attack_payload(**overrides))

    def test_damage_type_translated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Damage type 'slashing' in damage detail must go through _()."""
        monkeypatch.setattr(perception_mod, "_", _mark_translator(perception_mod._))
        observer = Character(id="player", name="Hero", location_id="r1")
        target = Character(id="npc", name="Goblin", location_id="r1", race=Race.HUMAN)
        result = perceive_event(self._attack_event(), observer, _get_entity_fn(observer, target))
        assert "[T]slashing" in result

    def test_damage_source_label_translated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-weapon source labels like 'sneak_attack' must go through _()."""
        monkeypatch.setattr(perception_mod, "_", _mark_translator(perception_mod._))
        observer = Character(id="player", name="Hero", location_id="r1")
        target = Character(id="npc", name="Goblin", location_id="r1", race=Race.HUMAN)
        event = self._attack_event(
            damage=12,
            damage_components=(
                DamageComponentPayload("weapon", "1d8", (), 5, "slashing"),
                DamageComponentPayload("sneak_attack", "1d6", (), 4, "slashing"),
                DamageComponentPayload("ability", "", (), 3, "slashing"),
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, target))
        # sneak_attack source label must be translated
        assert "[T]sneak_attack" in result
        # ability source label must be translated
        assert "[T]ability" in result

    def test_ac_label_translated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The 'AC' label in roll description must go through _()."""
        monkeypatch.setattr(perception_mod, "_", _mark_translator(perception_mod._))
        observer = Character(id="player", name="Hero", location_id="r1")
        target = Character(id="npc", name="Goblin", location_id="r1", race=Race.HUMAN)
        result = perceive_event(self._attack_event(), observer, _get_entity_fn(observer, target))
        assert "[T]AC" in result

    def test_weapon_name_translated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Weapon name in attack description must go through _()."""
        monkeypatch.setattr(perception_mod, "_", _mark_translator(perception_mod._))
        observer = Character(id="player", name="Hero", location_id="r1")
        target = Character(id="npc", name="Goblin", location_id="r1", race=Race.HUMAN)
        result = perceive_event(self._attack_event(), observer, _get_entity_fn(observer, target))
        assert "[T]Longsword" in result

    def test_item_name_translated_on_use(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Item name in use_item description must go through _()."""
        monkeypatch.setattr(perception_mod, "_", _mark_translator(perception_mod._))
        observer = Character(id="npc", name="Goblin", location_id="r1")
        user = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        event = Event(
            event_type=EventType.ENTITY_USE_ITEM,
            source_layer="entities",
            data=EntityUseItemPayload(**{"entity_id": "player", "item_name": "Health Potion", "healed": 8}),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, user))
        assert "[T]Health Potion" in result

    def test_opportunity_attack_annotated(self) -> None:
        """OA attack event shows '(opportunity attack)' annotation."""
        observer = Character(id="guard", name="Guard", location_id="r1")
        attacker = Character(id="orc", name="Orc", location_id="r1", race=Race.HUMAN)
        target = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data=_attack_payload(
                attacker_id="orc",
                target_id="player",
                weapon="Greataxe",
                ac=15,
                attack_roll=AttackRollPayload(16, (RollComponentPayload("ability", 3),), 19, False, False),
                damage=10,
                damage_components=(DamageComponentPayload("weapon", "1d12", (), 10, "slashing"),),
                is_opportunity_attack=True,
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, attacker, target))
        assert "opportunity attack" in result.lower()
        assert "d20(16)" in result
        assert "AC 15" in result

    def test_regular_attack_no_oa_annotation(self) -> None:
        """Regular attack without is_opportunity_attack flag has no OA annotation."""
        observer = Character(id="guard", name="Guard", location_id="r1")
        attacker = Character(id="orc", name="Orc", location_id="r1", race=Race.HUMAN)
        target = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data=_attack_payload(
                attacker_id="orc",
                target_id="player",
                weapon="Greataxe",
                ac=15,
                attack_roll=AttackRollPayload(16, (RollComponentPayload("ability", 3),), 19, False, False),
                damage=10,
                damage_components=(DamageComponentPayload("weapon", "1d12", (), 10, "slashing"),),
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, attacker, target))
        assert "opportunity attack" not in result.lower()

    def test_disengage_other(self) -> None:
        """Disengage event shows readable text for observer."""
        observer = Character(id="guard", name="Guard", location_id="r1")
        actor = Character(id="rogue", name="Rogue", location_id="r1", race=Race.ELF)
        event = Event(
            event_type=EventType.ENTITY_DISENGAGE,
            source_layer="entities",
            data=EntityActorPayload(**{"entity_id": "rogue"}),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, actor))
        assert "disengage" in result.lower()
        assert "elf" in result.lower()

    def test_disengage_self(self) -> None:
        """Disengage event shows 'You' for self-observer."""
        observer = Character(id="rogue", name="Rogue", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_DISENGAGE,
            source_layer="entities",
            data=EntityActorPayload(**{"entity_id": "rogue"}),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "you" in result.lower()
        assert "disengage" in result.lower()

    def test_weapon_name_translated_on_equip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Weapon name in equip description must go through _()."""
        monkeypatch.setattr(perception_mod, "_", _mark_translator(perception_mod._))
        observer = Character(id="npc", name="Goblin", location_id="r1")
        equipper = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        event = Event(
            event_type=EventType.ENTITY_EQUIP,
            source_layer="entities",
            data=EquipmentPayload(**{"entity_id": "player", "item_name": "Dagger"}),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, equipper))
        assert "[T]Dagger" in result


class TestPerceiveSecondWind:
    """Second Wind perception: full-health case must not read as 'regaining 0 HP'."""

    @staticmethod
    def _event(entity_id: str, healed: int) -> Event:
        return Event(
            event_type=EventType.ENTITY_SECOND_WIND,
            source_layer="entities",
            data=EntitySecondWindPayload(entity_id=entity_id, healed=healed),
        )

    def test_zero_heal_self_reports_full_health(self) -> None:
        observer = Character(id="fighter", name="Fighter", location_id="r1")
        result = perceive_event(self._event("fighter", 0), observer, _get_entity_fn(observer))
        assert "0" not in result
        assert "you" in result.lower()
        assert "full health" in result.lower()

    def test_zero_heal_other_reports_full_health(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        actor = Character(id="fighter", name="Fighter", location_id="r1", race=Race.ELF)
        result = perceive_event(self._event("fighter", 0), observer, _get_entity_fn(observer, actor))
        assert "0" not in result
        assert "elf" in result.lower()
        assert "full health" in result.lower()

    def test_positive_heal_self_reports_amount(self) -> None:
        observer = Character(id="fighter", name="Fighter", location_id="r1")
        result = perceive_event(self._event("fighter", 7), observer, _get_entity_fn(observer))
        assert "7" in result
        assert "you" in result.lower()

    def test_positive_heal_other_reports_amount(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        actor = Character(id="fighter", name="Fighter", location_id="r1", race=Race.ELF)
        result = perceive_event(self._event("fighter", 7), observer, _get_entity_fn(observer, actor))
        assert "7" in result
        assert "elf" in result.lower()


class TestPerceptionDispatchAndFailFast:
    """Dispatch dict routing and fail-fast on missing event data."""

    def test_dispatch_routes_to_correct_handler(self) -> None:
        """Dispatch dict routes each EventType to the right handler function."""
        observer = Character(id="guard", name="Guard", location_id="r1")
        actor = Character(id="rogue", name="Rogue", location_id="r1", race=Race.ELF)
        # Verify a sample of event types route correctly
        disengage = Event(
            event_type=EventType.ENTITY_DISENGAGE,
            source_layer="entities",
            data=EntityActorPayload(**{"entity_id": "rogue"}),
        )
        result = perceive_event(disengage, observer, _get_entity_fn(observer, actor))
        assert "disengage" in result.lower()

    def test_unrecognized_event_type_fallback(self) -> None:
        """Event types not in dispatch produce the fallback message."""
        observer = Character(id="guard", name="Guard", location_id="r1")
        event = Event(
            event_type=EventType.WEATHER_CHANGED,
            source_layer="geography",
            data=WeatherChangedPayload("r1", "clear", "rain", 10.0),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "Something happened" in result
        assert "weather_changed" in result

    def test_missing_required_data_raises_key_error(self) -> None:
        """ENTITY_SAY without text is rejected at construction."""
        with pytest.raises(TypeError, match="text"):
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data=EntitySayPayload(**{"entity_id": "guard"}),
            )

    def test_missing_entity_id_fails_at_event_boundary(self) -> None:
        with pytest.raises(TypeError, match="entity_id"):
            Event(event_type=EventType.ENTITY_DIED, source_layer="entities", data=EntityDiedPayload(**{}))

    def test_missing_round_number_fails_at_event_boundary(self) -> None:
        with pytest.raises(TypeError, match="round_number"):
            Event(event_type=EventType.ROUND_START, source_layer="entities", data=RoundStartPayload(**{}))

    def test_missing_squad_payload_fields_rejected_at_event_boundary(self) -> None:
        """Typed events fail at construction instead of later in perception."""
        with pytest.raises(TypeError, match="SquadDematerializedPayload"):
            Event(
                event_type=EventType.SQUAD_DEMATERIALIZED,
                source_layer="ecology",
                data=SquadDematerializedPayload(**{}),
            )

    def test_missing_weapon_in_attack_raises_key_error(self) -> None:
        """ENTITY_ATTACK without 'weapon' is rejected at construction."""
        with pytest.raises(TypeError, match="weapon"):
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data=AttackResolvedPayload(
                    **{
                        "attacker_id": "guard",
                        "target_id": "npc",
                        "hit": False,
                        "critical": False,
                        "ac": 13,
                        "attack_roll": AttackRollPayload(8, (), 8, False, False),
                    }
                ),
            )

    def test_missing_critical_in_attack_raises_key_error(self) -> None:
        """ENTITY_ATTACK without 'critical' is rejected at construction."""
        with pytest.raises(TypeError, match="critical"):
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data=AttackResolvedPayload(
                    **{
                        "attacker_id": "guard",
                        "target_id": "npc",
                        "weapon": "longsword",
                        "hit": True,
                        "ac": 13,
                        "attack_roll": AttackRollPayload(18, (), 18, False, False),
                        "damage": 5,
                        "damage_components": (DamageComponentPayload("weapon", "1d8", (), 5, "slashing"),),
                        # "critical" deliberately missing
                    }
                ),
            )


class TestPerceiveReputationChanged:
    """REPUTATION_CHANGED event produces readable descriptions."""

    def test_reputation_change_self_observer(self) -> None:
        """Observer whose reputation changed sees 'Your reputation with X decreased (80 → 60).'"""
        observer = Character(id="player", name="Hero", location_id="r1")
        faction_entity = Character(id="bandit", name="Bandit", location_id="r1", faction_id="bandits")
        event = Event(
            event_type=EventType.REPUTATION_CHANGED,
            source_layer="entities",
            data=ReputationChangedPayload(
                **{
                    "entity_id": "player",
                    "faction_id": "bandits",
                    "faction_name": "Bandits",
                    "old_rep": 80,
                    "new_rep": 60,
                    "delta": -20,
                    "reason": "kill",
                }
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, faction_entity))
        assert "reputation" in result.lower()
        assert "Bandits" in result
        assert "80" in result
        assert "60" in result

    def test_reputation_change_other_observer(self) -> None:
        """Non-involved observer sees a different, less detailed message."""
        observer = Character(id="guard", name="Guard", location_id="r1")
        actor = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        event = Event(
            event_type=EventType.REPUTATION_CHANGED,
            source_layer="entities",
            data=ReputationChangedPayload(
                **{
                    "entity_id": "player",
                    "faction_id": "bandits",
                    "faction_name": "Bandits",
                    "old_rep": 80,
                    "new_rep": 60,
                    "delta": -20,
                    "reason": "kill",
                }
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, actor))
        assert "reputation" in result.lower()
        assert "Bandits" in result
        # Should reference the actor, not "you"
        assert "elf" in result.lower()


class TestAttackLineLocalizes:
    """Attack-line msgids carry {oa}; the .po must match so RU renders (catalog drift fix)."""

    def teardown_method(self) -> None:
        set_language("en")

    def _attack_event(self) -> Event:
        return Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data=_attack_payload(
                target_id="smith",
                hit=False,
                ac=15,
                attack_roll=AttackRollPayload(8, (RollComponentPayload("ability", 3),), 11, False, False),
            ),
        )

    def test_attack_line_renders_russian(self) -> None:
        """Observer-is-attacker line renders RU, not the English fallback, with no raw placeholders."""
        set_language("ru")
        observer = Character(id="player", name="Hero", location_id="r1")
        target = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
        result = perceive_event(self._attack_event(), observer, _get_entity_fn(observer, target))
        assert "You attack" not in result
        assert "{oa}" not in result
        assert "{weapon}" not in result
        assert _has_cyrillic(result)


class TestEncounterSpawnedPerceiver:
    """ENCOUNTER_SPAWNED should produce vague flavor, never the fallback or monster names."""

    def teardown_method(self) -> None:
        set_language("en")

    def _event(self) -> Event:
        return Event(
            event_type=EventType.ENCOUNTER_SPAWNED,
            source_layer="entities",
            data=EncounterSpawnedPayload(**{"location_id": "loc1", "spawned_names": ("Goblin", "Goblin")}),
        )

    def test_not_fallback_and_no_name_leak(self) -> None:
        observer = Character(id="player", name="Hero", location_id="loc1")
        result = perceive_event(self._event(), observer, _get_entity_fn(observer))
        assert "Something happened" not in result
        assert "Goblin" not in result

    def test_russian_flavor(self) -> None:
        set_language("ru")
        observer = Character(id="player", name="Hero", location_id="loc1")
        result = perceive_event(self._event(), observer, _get_entity_fn(observer))
        assert "Goblin" not in result
        assert "encounter_spawned" not in result  # not the raw-type fallback
        assert _has_cyrillic(result)


class TestCombatLogLocalizesRussian:
    def teardown_method(self) -> None:
        set_language("en")

    def test_loot_line_russian(self) -> None:
        set_language("ru")
        observer = Character(id="player", name="Hero", location_id="r1")
        corpse = Character(id="bandit", name="Bandit", location_id="r1", race=Race.HUMAN)
        event = Event(
            event_type=EventType.ENTITY_TAKE,
            source_layer="entities",
            data=TakePayload(**{"actor_id": "player", "target_id": "bandit", "item_names": [], "gold": 12}),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, corpse))
        assert "You loot" not in result
        assert "gold" not in result
        assert _has_cyrillic(result)

    def test_lay_on_hands_line_russian(self) -> None:
        set_language("ru")
        observer = Character(id="paladin", name="Pal", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_LAY_ON_HANDS,
            source_layer="entities",
            data=EntityLayOnHandsPayload(
                **{
                    "entity_id": "paladin",
                    "target_id": "paladin",
                    "healed": 5,
                    "pool_before": 10,
                    "pool_after": 5,
                }
            ),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "lay hands" not in result
        assert "→" in result
        assert _has_cyrillic(result)

    def test_action_surge_line_russian(self) -> None:
        set_language("ru")
        observer = Character(id="fighter", name="Ftr", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_ACTION_SURGE,
            source_layer="entities",
            data=EntityActorPayload(**{"entity_id": "fighter"}),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "surge with energy" not in result
        assert _has_cyrillic(result)

    def test_inspect_conditions_line_russian(self) -> None:
        from dnd_simulator.core.conditions import Condition

        set_language("ru")
        observer = Character(id="player", name="Hero", location_id="r1")
        target = Character(id="orc", name="Orc", location_id="r1", race=Race.HUMAN)
        target.conditions[Condition.POISONED] = 3
        event = Event(
            event_type=EventType.CUSTOM,
            source_layer="entities",
            data=InspectPayload(**{"inspect_target": "orc"}),
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, target))
        assert "Conditions:" not in result
        assert _has_cyrillic(result)
