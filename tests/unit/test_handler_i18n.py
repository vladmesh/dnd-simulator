"""Handler error strings must localize under DND_LANGUAGE=ru.

Sprint 020, Phase 1, Task 4. Mirrors the TestMoveErrorI18n pattern from
test_handlers_movement.py — one failure per handler file, assert Cyrillic
and no em-dash.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Character, CharClass, Creature, Race
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.i18n import set_language
from dnd_simulator.rules.handlers.action_surge import handle_action_surge
from dnd_simulator.rules.handlers.equipment import handle_equip
from dnd_simulator.rules.handlers.items import handle_lay_on_hands, handle_use_item
from dnd_simulator.rules.handlers.loot import handle_take
from dnd_simulator.rules.handlers.trade import handle_buy
from dnd_simulator.rules.validation import ActionContext


def _has_cyrillic(text: str) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in text)


def _noop_emit(event: object) -> ActionResult:
    return ActionResult()


def _basic_ctx(*, entities: dict[str, object] | None = None) -> ActionContext:
    return ActionContext(
        is_combat=False,
        get_entity=lambda eid: (entities or {}).get(eid),
    )


def _creature_with_weapon() -> Creature:
    weapon = Item(id="dagger_0", name="Dagger", item_type=ItemType.WEAPON)
    c = Creature(
        id="fighter",
        name="Fighter",
        location_id="arena",
        max_hp=20,
        current_hp=20,
    )
    c.inventory = [weapon]
    return c


def _fighter_l1() -> Character:
    return Character(
        id="fighter1",
        name="FighterL1",
        location_id="arena",
        max_hp=20,
        current_hp=20,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=1,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        resource_pools=[ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)],
    )


def _fighter_l2_no_surge() -> Character:
    """L2 Fighter whose action_surge pool is exhausted (0 current_uses)."""
    return Character(
        id="fighter2",
        name="FighterL2",
        location_id="arena",
        max_hp=22,
        current_hp=22,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=2,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        resource_pools=[
            ResourcePool("second_wind", 1, 1, RestType.SHORT_REST),
            ResourcePool("action_surge", 1, 0, RestType.SHORT_REST),
        ],
    )


# ---------------------------------------------------------------------------
# items.py — handle_use_item (non-usable type)
# ---------------------------------------------------------------------------


class TestItemsHandlerI18n:
    def teardown_method(self) -> None:
        set_language("en")

    def _use_weapon_as_item(self) -> ActionResult:
        actor = _creature_with_weapon()
        action = Action(name=ActionType.USE_ITEM, params={"item_id": "dagger_0"})
        world = MagicMock()
        return handle_use_item(actor, action, _noop_emit, _basic_ctx(), world)

    def test_use_non_usable_item_localizes_russian(self) -> None:
        set_language("ru")
        result = self._use_weapon_as_item()
        assert not result.success
        assert "—" not in result.error
        assert _has_cyrillic(result.error), f"Expected Cyrillic, got: {result.error!r}"

    def test_use_non_usable_item_english_no_em_dash(self) -> None:
        set_language("en")
        result = self._use_weapon_as_item()
        assert not result.success
        assert "—" not in result.error


# ---------------------------------------------------------------------------
# items.py — handle_lay_on_hands (non-Paladin)
# ---------------------------------------------------------------------------


class TestLayOnHandsI18n:
    def teardown_method(self) -> None:
        set_language("en")

    def _lay_on_hands_as_fighter(self) -> ActionResult:
        actor = _fighter_l1()
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 5})
        world = MagicMock()
        return handle_lay_on_hands(actor, action, _noop_emit, _basic_ctx(), world)

    def test_lay_on_hands_non_paladin_localizes_russian(self) -> None:
        set_language("ru")
        result = self._lay_on_hands_as_fighter()
        assert not result.success
        assert "—" not in result.error
        assert _has_cyrillic(result.error), f"Expected Cyrillic, got: {result.error!r}"

    def test_lay_on_hands_non_paladin_english_no_em_dash(self) -> None:
        set_language("en")
        result = self._lay_on_hands_as_fighter()
        assert not result.success
        assert "—" not in result.error


# ---------------------------------------------------------------------------
# equipment.py — handle_equip (item not in inventory)
# ---------------------------------------------------------------------------


class TestEquipmentHandlerI18n:
    def teardown_method(self) -> None:
        set_language("en")

    def _equip_missing_item(self) -> ActionResult:
        actor = Creature(
            id="fighter",
            name="Fighter",
            location_id="arena",
            max_hp=20,
            current_hp=20,
        )
        action = Action(name=ActionType.EQUIP, params={"weapon_id": "missing_sword"})
        world = MagicMock()
        return handle_equip(actor, action, _noop_emit, _basic_ctx(), world)

    def test_equip_missing_item_localizes_russian(self) -> None:
        set_language("ru")
        result = self._equip_missing_item()
        assert not result.success
        assert "—" not in result.error
        assert _has_cyrillic(result.error), f"Expected Cyrillic, got: {result.error!r}"

    def test_equip_missing_item_english_no_em_dash(self) -> None:
        set_language("en")
        result = self._equip_missing_item()
        assert not result.success
        assert "—" not in result.error


# ---------------------------------------------------------------------------
# trade.py — handle_buy (merchant not found)
# ---------------------------------------------------------------------------


class TestTradeHandlerI18n:
    def teardown_method(self) -> None:
        set_language("en")

    def _buy_from_missing_merchant(self) -> ActionResult:
        actor = Creature(
            id="buyer",
            name="Buyer",
            location_id="market",
            max_hp=20,
            current_hp=20,
        )
        action = Action(name=ActionType.BUY, params={"merchant_id": "ghost_merchant", "item_id": "potion_0"})
        world = MagicMock()
        return handle_buy(actor, action, _noop_emit, _basic_ctx(), world)

    def test_buy_missing_merchant_localizes_russian(self) -> None:
        set_language("ru")
        result = self._buy_from_missing_merchant()
        assert not result.success
        assert "—" not in result.error
        assert _has_cyrillic(result.error), f"Expected Cyrillic, got: {result.error!r}"

    def test_buy_missing_merchant_english_no_em_dash(self) -> None:
        set_language("en")
        result = self._buy_from_missing_merchant()
        assert not result.success
        assert "—" not in result.error


# ---------------------------------------------------------------------------
# action_surge.py — handle_action_surge (pool exhausted)
# ---------------------------------------------------------------------------


class TestActionSurgeI18n:
    def teardown_method(self) -> None:
        set_language("en")

    def _surge_with_no_pool(self) -> ActionResult:
        actor = _fighter_l2_no_surge()
        budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=30)
        ctx = ActionContext(is_combat=True, turn_budget=budget)
        action = Action(name=ActionType.ACTION_SURGE, params={})
        world = MagicMock()
        return handle_action_surge(actor, action, _noop_emit, ctx, world)

    def test_surge_exhausted_localizes_russian(self) -> None:
        set_language("ru")
        result = self._surge_with_no_pool()
        assert not result.success
        assert "—" not in result.error
        assert _has_cyrillic(result.error), f"Expected Cyrillic, got: {result.error!r}"

    def test_surge_exhausted_english_no_em_dash(self) -> None:
        set_language("en")
        result = self._surge_with_no_pool()
        assert not result.success
        assert "—" not in result.error


# ---------------------------------------------------------------------------
# loot.py — handle_take (non-lootable target)
# ---------------------------------------------------------------------------


class TestLootHandlerI18n:
    def teardown_method(self) -> None:
        set_language("en")

    def _take_from_non_lootable(self) -> ActionResult:
        # A living creature is not lootable.
        target = Creature(
            id="bandit",
            name="Bandit",
            location_id="arena",
            max_hp=20,
            current_hp=20,
        )
        actor = Creature(
            id="player",
            name="Player",
            location_id="arena",
            max_hp=20,
            current_hp=20,
        )
        ctx = _basic_ctx(entities={"bandit": target})
        action = Action(name=ActionType.TAKE, params={"target_id": "bandit"})
        world = MagicMock()
        return handle_take(actor, action, _noop_emit, ctx, world)

    def test_take_non_lootable_localizes_russian(self) -> None:
        set_language("ru")
        result = self._take_from_non_lootable()
        assert not result.success
        assert "—" not in result.error
        assert _has_cyrillic(result.error), f"Expected Cyrillic, got: {result.error!r}"

    def test_take_non_lootable_english_no_em_dash(self) -> None:
        set_language("en")
        result = self._take_from_non_lootable()
        assert not result.success
        assert "—" not in result.error
