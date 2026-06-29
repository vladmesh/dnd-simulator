"""Action-failure error strings are localized.

Sprint 020, Phase 4, Task 3 — i18n sweep of `ActionResult.error` strings across
rules/handlers/. These rejection reasons surface to the player; they must render in
Russian at DND_LANGUAGE=ru, not stay English. Covers literal gates and the
parametrized `.format(...)` path, plus the em-dash removal in the item-type error.
"""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Character, CharClass, Creature, Race
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.models import ActionResult, Event
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.i18n import set_language
from dnd_simulator.rules.handlers.equipment import handle_equip
from dnd_simulator.rules.handlers.items import handle_lay_on_hands, handle_use_item
from dnd_simulator.rules.handlers.trade import handle_buy
from dnd_simulator.rules.validation import ActionContext


def _has_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


def _ctx(entities: dict[str, Creature] | None = None) -> ActionContext:
    lookup = (lambda eid: entities.get(eid)) if entities else None
    return ActionContext(
        is_combat=False,
        turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=30),
        get_entity=lookup,
    )


def _noop_emit(event: Event) -> ActionResult:
    return ActionResult()


def _fighter() -> Character:
    return Character(
        id="fighter",
        name="Fighter",
        location_id="arena",
        max_hp=20,
        current_hp=10,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        resource_pools=[ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)],
    )


class TestHandlerErrorsLocalizeRussian:
    def teardown_method(self) -> None:
        set_language("en")

    def test_lay_on_hands_gate_russian(self) -> None:
        """Non-Paladin Lay on Hands rejection is Russian, not the English literal (bare-literal path)."""
        set_language("ru")
        fighter = _fighter()
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 5})
        result = handle_lay_on_hands(fighter, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False
        assert "Only Paladins can use Lay on Hands" not in (result.error or "")
        assert _has_cyrillic(result.error or "")

    def test_equip_item_not_in_inventory_russian(self) -> None:
        """Equip with an id not in inventory speaks Russian and keeps the interpolated id (.format path)."""
        set_language("ru")
        fighter = _fighter()  # empty inventory
        action = Action(name=ActionType.EQUIP, params={"weapon_id": "ghost_sword"})
        result = handle_equip(fighter, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False
        assert "not in inventory" not in (result.error or "")
        assert "ghost_sword" in (result.error or "")  # placeholder interpolated, not dropped
        assert _has_cyrillic(result.error or "")

    def test_buy_merchant_not_found_russian(self) -> None:
        """Buy from an unresolvable merchant speaks Russian, keeps the merchant id (.format path)."""
        set_language("ru")
        fighter = _fighter()
        action = Action(name=ActionType.BUY, params={"merchant_id": "phantom", "item_id": "x"})
        result = handle_buy(fighter, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False
        assert "not found" not in (result.error or "")
        assert "phantom" in (result.error or "")
        assert _has_cyrillic(result.error or "")


class TestItemTypeErrorNoEmDash:
    """The item-type rejection must use a comma/period, not an em-dash (writing-style rule)."""

    def teardown_method(self) -> None:
        set_language("en")

    def test_no_em_dash(self) -> None:
        fighter = _fighter()
        armor = Item(id="plate", name="Plate", item_type=ItemType.ARMOR)
        fighter.inventory.append(armor)
        action = Action(name=ActionType.USE_ITEM, params={"item_id": "plate"})
        result = handle_use_item(fighter, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False
        assert "—" not in (result.error or "")
        # the item type is still reported so the player knows why
        assert "armor" in (result.error or "")
