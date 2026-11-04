"""Branch coverage for per-event perception: self / target / bystander phrasings."""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import Character, Entity
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.events import (
    AttackResolvedPayload as _AttackResolved,
)
from dnd_simulator.core.events import (
    AttackRollPayload,
    BuyPayload,
    EntityActorPayload,
    EntityBlessPayload,
    EntityLayOnHandsPayload,
    EquipmentPayload,
    InspectPayload,
    OpportunityAttackPayload,
    RollComponentPayload,
    SellPayload,
    TakePayload,
    TurnSkippedPayload,
    XpGainedPayload,
)
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.i18n import set_language
from dnd_simulator.layers.entities.perception import perceive_event


@pytest.fixture(autouse=True)
def _english() -> None:
    set_language("en")


OBSERVER = Character(id="me", name="Me", location_id="r1")
ALLY = Character(id="ally", name="Ally", location_id="r1")
OTHER = Character(id="other", name="Other", location_id="r1")


def _get(*entities: Entity):
    by_id = {e.id: e for e in entities}
    return lambda eid: by_id.get(eid)


def _see(event_type: EventType, payload: object, *extra: Entity) -> str:
    event = Event(event_type=event_type, source_layer="entities", data=payload)  # type: ignore[arg-type]
    return perceive_event(event, OBSERVER, _get(OBSERVER, ALLY, OTHER, *extra))


class TestAttackRollFormatting:
    def _attack(self, *, advantage: bool, disadvantage: bool, bonus: int) -> str:
        roll = AttackRollPayload(10, (RollComponentPayload("ability", bonus),), 10 + bonus, advantage, disadvantage)
        payload = _AttackResolved(
            attacker_id="ally",
            target_id="other",
            weapon=None,
            hit=True,
            critical=False,
            ac=12,
            attack_roll=roll,
            damage=None,
            damage_components=(),
        )
        return _see(EventType.ENTITY_ATTACK, payload)

    def test_disadvantage_and_negative_modifier(self) -> None:
        text = self._attack(advantage=False, disadvantage=True, bonus=-1)
        assert "disadv d20(10)-1=9" in text

    def test_advantage_and_disadvantage_cancel(self) -> None:
        text = self._attack(advantage=True, disadvantage=True, bonus=2)
        assert "adv" not in text
        assert "d20(10)+2=12" in text

    def test_hit_without_damage_has_no_outcome(self) -> None:
        text = self._attack(advantage=False, disadvantage=False, bonus=0)
        assert text.endswith("vs AC 12]")


class TestOpportunityAttackNote:
    def test_observer_is_target(self) -> None:
        text = _see(EventType.OPPORTUNITY_ATTACK, OpportunityAttackPayload(attacker_id="ally", target_id="me"))
        assert "against you" in text

    def test_bystander(self) -> None:
        text = _see(EventType.OPPORTUNITY_ATTACK, OpportunityAttackPayload(attacker_id="ally", target_id="other"))
        assert "seizes the opening against" in text
        assert "you" not in text


class TestInspect:
    def _inspect(self, target: Entity | None, target_id: str = "t") -> str:
        event = Event(
            event_type=EventType.CUSTOM, source_layer="entities", data=InspectPayload(inspect_target=target_id)
        )
        extra = (target,) if target is not None else ()
        return perceive_event(event, OBSERVER, _get(OBSERVER, *extra))

    def test_unknown_target(self) -> None:
        assert "no one matching 'ghost'" in self._inspect(None, "ghost")

    def test_badly_wounded(self) -> None:
        target = Character(id="t", name="T", location_id="r1", max_hp=10, current_hp=4)
        assert "badly wounded" in self._inspect(target)

    def test_minor_injuries(self) -> None:
        target = Character(id="t", name="T", location_id="r1", max_hp=10, current_hp=9)
        assert "minor injuries" in self._inspect(target)

    def test_healthy_with_conditions(self) -> None:
        target = Character(
            id="t",
            name="T",
            location_id="r1",
            max_hp=10,
            current_hp=10,
            conditions={Condition.PRONE: None, Condition.BLINDED: 2},
        )
        text = self._inspect(target)
        assert "look healthy" in text
        assert "Conditions: blinded, prone." in text


class TestTurnSkippedAndBless:
    def test_turn_skipped_self(self) -> None:
        text = _see(EventType.TURN_SKIPPED, TurnSkippedPayload(entity_id="me", reason="x", conditions=("stunned",)))
        assert text == "You can't act (stunned) — turn skipped"

    def test_turn_skipped_other_without_conditions(self) -> None:
        text = _see(EventType.TURN_SKIPPED, TurnSkippedPayload(entity_id="ally", reason="x", conditions=()))
        assert "can't act (?)" in text
        assert not text.startswith("You")

    def test_bless_self(self) -> None:
        text = _see(EventType.ENTITY_BLESS, EntityBlessPayload(entity_id="me", duration_rounds=10))
        assert text.startswith("You invoke a blessing")
        assert "10 rounds" in text

    def test_bless_other(self) -> None:
        text = _see(EventType.ENTITY_BLESS, EntityBlessPayload(entity_id="ally", duration_rounds=3))
        assert "invokes a blessing" in text
        assert "3 rounds" in text


class TestActionSurge:
    def test_other(self) -> None:
        text = _see(EventType.ENTITY_ACTION_SURGE, EntityActorPayload(entity_id="ally"))
        assert "surges with energy" in text


class TestLayOnHands:
    def _loh(self, entity_id: str, target_id: str, healed: int) -> str:
        payload = EntityLayOnHandsPayload(
            entity_id=entity_id, target_id=target_id, healed=healed, pool_before=5, pool_after=5 - healed
        )
        return _see(EventType.ENTITY_LAY_ON_HANDS, payload)

    def test_zero_heal_bystander(self) -> None:
        text = self._loh("ally", "other", 0)
        assert "lays hands on" in text
        assert "they are already at full health" in text

    def test_heal_self_on_self(self) -> None:
        assert self._loh("me", "me", 3) == "You lay hands on yourself, restoring 3 HP (pool 5→2)"

    def test_heal_self_on_other(self) -> None:
        text = self._loh("me", "ally", 2)
        assert text.startswith("You lay hands on")
        assert "restoring 2 HP (pool 5→3)" in text

    def test_heal_other_on_observer(self) -> None:
        text = self._loh("ally", "me", 4)
        assert "lays hands on you, restoring 4 HP" in text

    def test_heal_other_on_bystander(self) -> None:
        text = self._loh("ally", "other", 1)
        assert "lays hands on" in text
        assert "restoring 1 HP" in text
        assert "pool" not in text


class TestEquipment:
    def test_equip_self(self) -> None:
        assert _see(EventType.ENTITY_EQUIP, EquipmentPayload(entity_id="me", item_name="Dagger")) == "You equip Dagger"

    def test_unequip_self(self) -> None:
        text = _see(EventType.ENTITY_UNEQUIP, EquipmentPayload(entity_id="me", item_name="Dagger"))
        assert text == "You put away Dagger"

    def test_unequip_other(self) -> None:
        text = _see(EventType.ENTITY_UNEQUIP, EquipmentPayload(entity_id="ally", item_name="Dagger"))
        assert "puts away Dagger" in text


class TestTrade:
    def test_buy_self(self) -> None:
        text = _see(EventType.ENTITY_BUY, BuyPayload(buyer_id="me", merchant_id="ally", item_name="Rope", price=2))
        assert text.startswith("You buy Rope from")
        assert "for 2 gold" in text

    def test_buy_other(self) -> None:
        text = _see(EventType.ENTITY_BUY, BuyPayload(buyer_id="other", merchant_id="ally", item_name="Rope", price=2))
        assert "buys Rope from" in text

    def test_sell_self(self) -> None:
        text = _see(EventType.ENTITY_SELL, SellPayload(seller_id="me", merchant_id="ally", item_name="Rope", price=1))
        assert text.startswith("You sell Rope to")

    def test_sell_other(self) -> None:
        payload = SellPayload(seller_id="other", merchant_id="ally", item_name="Rope", price=1)
        assert "sells Rope to" in _see(EventType.ENTITY_SELL, payload)


class TestTake:
    def test_self_takes_items_and_gold(self) -> None:
        payload = TakePayload(actor_id="me", target_id="other", item_names=("Dagger", "Rope"), gold=7)
        text = _see(EventType.ENTITY_TAKE, payload)
        assert text.startswith("You loot")
        assert "(Dagger, Rope; 7 gold)" in text

    def test_other_takes_nothing(self) -> None:
        text = _see(EventType.ENTITY_TAKE, TakePayload(actor_id="ally", target_id="other"))
        assert "loots" in text
        assert "(nothing)" in text


class TestXpGained:
    def test_self(self) -> None:
        payload = XpGainedPayload(
            entity_id="me", amount=50, new_total=50, source_entity_id="other", level_up_available=False
        )
        text = _see(EventType.XP_GAINED, payload)
        assert text.startswith("You gain 50 XP for defeating")
