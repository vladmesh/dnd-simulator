"""Combat action costs: equipment slots, TAKE in combat, and the peaceful-turn-end flag.

Product-level: drives the real ActionDispatcher (validation chain → handler → budget)
and the real CombatManager / awareness builder. Only the World is a stub — handlers
resolve targets through ctx.get_entity.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.action_defs import ACTION_DEFS, CombatMode, CostType, get_action_def
from dnd_simulator.core.character import Creature, DamageComponent, DamageType
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.container import Container
from dnd_simulator.core.items import (
    AccessoryDef,
    ArmorCategory,
    ArmorDef,
    EquipmentSlot,
    Item,
    ItemType,
    ShieldDef,
    WeaponCategory,
    WeaponDef,
)
from dnd_simulator.core.models import ActionResult, Event
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.i18n import language_context
from dnd_simulator.layers.entities.awareness_builder import AwarenessBuilder
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.layers.entities.combat_serialization import deserialize_combats, serialize_combats
from dnd_simulator.rules.action_provider import EquipmentActionProvider, blocked_equipment_actions
from dnd_simulator.rules.actions import ends_peaceful_turn
from dnd_simulator.rules.loot import LootBlock
from dnd_simulator.rules.validation import ActionContext
from dnd_simulator.service.action_dispatcher import create_dispatcher
from dnd_simulator.service.contextual_providers import LootActionProvider

if TYPE_CHECKING:
    from dnd_simulator.core.character import Entity

CAVE = "cave"
_WORLD = cast(World, MagicMock(spec=World))


# ── Fixtures ─────────────────────────────────────────────────────────


def _player() -> PlayerCharacter:
    return PlayerCharacter(id="player_1", name="Hero", location_id=CAVE)


def _corpse(cid: str = "goblin_corpse", *, gold: int = 7) -> Creature:
    c = Creature(id=cid, name="Goblin", location_id=CAVE, max_hp=7, current_hp=0)
    c.inventory = [Item(id=f"{cid}_dagger", name="Dagger", item_type=ItemType.WEAPON)]
    c.gold = gold
    return c


def _chain_mail() -> Item:
    return Item(
        id="chain_mail_0",
        name="Chain Mail",
        item_type=ItemType.ARMOR,
        armor_def=ArmorDef(armor_id="chain_mail", category=ArmorCategory.HEAVY, base_ac=16, max_dex_bonus=0),
    )


def _shield() -> Item:
    return Item(id="shield_0", name="Shield", item_type=ItemType.SHIELD, shield_def=ShieldDef("shield", ac_bonus=2))


def _ring() -> Item:
    return Item(
        id="ring_0",
        name="Ring",
        item_type=ItemType.ACCESSORY,
        accessory_def=AccessoryDef(accessory_id="ring", slot=EquipmentSlot.RING),
    )


def _sword() -> Item:
    return Item(
        id="sword_0",
        name="Longsword",
        item_type=ItemType.WEAPON,
        weapon_def=WeaponDef(
            weapon_id="longsword",
            attack_name="Longsword",
            category=WeaponCategory.MARTIAL,
            damage=(DamageComponent("1d8", DamageType.SLASHING),),
        ),
    )


def _combat(positions: dict[str, Position] | None = None, corpses: dict[str, Position] | None = None) -> CombatState:
    bm = BattleMap(width=60, height=60)
    for eid, pos in (positions or {}).items():
        bm.set_position(eid, pos)
    bm.corpses.update(corpses or {})
    return CombatState(location_id=CAVE, turn_order=["player_1", "orc"], battle_map=bm)


def _ctx(
    entities: dict[str, Entity], *, combat: CombatState | None = None, budget: TurnBudget | None = None
) -> ActionContext:
    return ActionContext(
        is_combat=combat is not None,
        current_turn_entity_id="player_1",
        turn_budget=budget,
        combat_state=combat,
        get_entity=lambda eid: entities.get(eid),
    )


def _dispatch(actor: Creature, action: Action, ctx: ActionContext) -> ActionResult:
    def emit(_event: Event) -> ActionResult:
        return ActionResult()

    return create_dispatcher(_WORLD).dispatch(actor, action, ctx, emit)


# ── Equipment slots ──────────────────────────────────────────────────


class TestEquipmentInCombat:
    @pytest.mark.parametrize(
        ("item_factory", "action_type", "param"),
        [
            (_chain_mail, ActionType.EQUIP_ARMOR, "armor_id"),
            (_ring, ActionType.EQUIP_RING, "ring_id"),
        ],
    )
    def test_armor_and_accessory_equip_rejected_in_combat(
        self, item_factory: object, action_type: ActionType, param: str
    ) -> None:
        player = _player()
        item = item_factory()  # type: ignore[operator]
        player.inventory.append(item)
        budget = TurnBudget()
        ctx = _ctx({"player_1": player}, combat=_combat({"player_1": Position(10, 10)}), budget=budget)

        result = _dispatch(player, Action(name=action_type, params={param: item.id}), ctx)

        assert not result.success
        assert "not available in combat" in (result.error or "")
        assert item in player.inventory
        assert budget == TurnBudget()

    @pytest.mark.parametrize(
        ("lang", "expected"),
        [
            ("en", "This is not available in combat: Equip armor from your inventory."),
            ("ru", "Это недоступно в бою: Надеть броню из инвентаря."),
        ],
    )
    def test_wrong_mode_rejection_names_the_action_not_its_id(self, lang: str, expected: str) -> None:
        player = _player()
        item = _chain_mail()
        player.inventory.append(item)
        ctx = _ctx({"player_1": player}, combat=_combat({"player_1": Position(10, 10)}), budget=TurnBudget())

        with language_context(lang):
            result = _dispatch(player, Action(name=ActionType.EQUIP_ARMOR, params={"armor_id": item.id}), ctx)

        assert result.error == expected
        assert "equip_armor" not in result.error

    def test_wrong_mode_rejection_outside_combat_names_the_action(self) -> None:
        player = _player()
        ctx = _ctx({"player_1": player})

        with language_context("ru"):
            result = _dispatch(player, Action(name=ActionType.DISENGAGE), ctx)

        assert not result.success
        assert (result.error or "").startswith("Это недоступно вне боя: ")
        assert "disengage" not in (result.error or "")

    @pytest.mark.parametrize(
        ("item_factory", "action_type", "param", "field"),
        [
            (_chain_mail, ActionType.EQUIP_ARMOR, "armor_id", "equipped_armor"),
            (_ring, ActionType.EQUIP_RING, "ring_id", "equipped_ring"),
        ],
    )
    def test_armor_and_accessory_equip_allowed_out_of_combat(
        self, item_factory: object, action_type: ActionType, param: str, field: str
    ) -> None:
        player = _player()
        item = item_factory()  # type: ignore[operator]
        player.inventory.append(item)

        result = _dispatch(player, Action(name=action_type, params={param: item.id}), _ctx({"player_1": player}))

        assert result.success
        assert getattr(player, field) is item

    def test_every_armor_and_accessory_slot_is_peaceful_only(self) -> None:
        for at in (
            ActionType.EQUIP_ARMOR,
            ActionType.UNEQUIP_ARMOR,
            ActionType.EQUIP_HEAD,
            ActionType.UNEQUIP_HEAD,
            ActionType.EQUIP_FEET,
            ActionType.UNEQUIP_FEET,
            ActionType.EQUIP_RING,
            ActionType.UNEQUIP_RING,
        ):
            assert get_action_def(at).combat_mode is CombatMode.PEACEFUL_ONLY, at

    def test_shield_equip_in_combat_charges_an_action(self) -> None:
        player = _player()
        shield = _shield()
        player.inventory.append(shield)
        budget = TurnBudget()
        ctx = _ctx({"player_1": player}, combat=_combat({"player_1": Position(10, 10)}), budget=budget)

        result = _dispatch(player, Action(name=ActionType.EQUIP_SHIELD, params={"shield_id": shield.id}), ctx)

        assert result.success
        assert player.equipped_shield is shield
        assert budget.actions == 0
        assert budget.bonus_actions == 1

    def test_shield_equip_rejected_when_action_spent(self) -> None:
        player = _player()
        shield = _shield()
        player.inventory.append(shield)
        budget = TurnBudget(actions=0)
        ctx = _ctx({"player_1": player}, combat=_combat({"player_1": Position(10, 10)}), budget=budget)

        result = _dispatch(player, Action(name=ActionType.EQUIP_SHIELD, params={"shield_id": shield.id}), ctx)

        assert not result.success
        assert player.equipped_shield is None
        assert shield in player.inventory

    def test_shield_unequip_in_combat_charges_an_action(self) -> None:
        player = _player()
        player.equipped_shield = _shield()
        budget = TurnBudget()
        ctx = _ctx({"player_1": player}, combat=_combat({"player_1": Position(10, 10)}), budget=budget)

        result = _dispatch(player, Action(name=ActionType.UNEQUIP_SHIELD), ctx)

        assert result.success
        assert player.equipped_shield is None
        assert budget.actions == 0

    def test_weapon_equip_in_combat_is_free(self) -> None:
        player = _player()
        sword = _sword()
        player.inventory.append(sword)
        budget = TurnBudget()
        ctx = _ctx({"player_1": player}, combat=_combat({"player_1": Position(10, 10)}), budget=budget)

        result = _dispatch(player, Action(name=ActionType.EQUIP, params={"weapon_id": sword.id}), ctx)

        assert result.success
        assert player.equipped_weapon is sword
        assert budget == TurnBudget()

    def test_weapon_equip_in_combat_free_even_with_action_spent(self) -> None:
        player = _player()
        sword = _sword()
        player.inventory.append(sword)
        ctx = _ctx({"player_1": player}, combat=_combat({"player_1": Position(10, 10)}), budget=TurnBudget(actions=0))

        result = _dispatch(player, Action(name=ActionType.EQUIP, params={"weapon_id": sword.id}), ctx)

        assert result.success

    def test_rule_brain_still_equips_a_weapon_in_combat(self) -> None:
        """RuleBrain's equip path: EQUIP stays offered in combat and dispatches for free."""
        from dnd_simulator.rules.action_provider import EquipmentActionProvider

        player = _player()
        player.inventory.extend([_sword(), _chain_mail(), _shield()])
        ctx = _ctx({"player_1": player}, combat=_combat({"player_1": Position(10, 10)}), budget=TurnBudget())

        offered = EquipmentActionProvider().get_action_types(player, ctx)

        assert ActionType.EQUIP in offered
        assert ActionType.EQUIP_SHIELD in offered
        assert ActionType.EQUIP_ARMOR not in offered


# ── TAKE in combat ───────────────────────────────────────────────────


class TestBlockedEquipmentActions:
    def test_combat_withholds_armor_by_mode_and_shield_by_budget_with_reason_codes(self) -> None:
        player = _player()
        player.inventory.extend([_chain_mail(), _shield(), _sword(), _ring()])
        ctx = _ctx({"player_1": player}, combat=_combat({"player_1": Position(10, 10)}), budget=TurnBudget(actions=0))

        blocked = {action: error.code for action, error in blocked_equipment_actions(player, ctx)}
        available = EquipmentActionProvider().get_action_types(player, ctx)

        assert blocked[ActionType.EQUIP_ARMOR] == "WRONG_MODE"
        assert blocked[ActionType.EQUIP_SHIELD] == "INSUFFICIENT_BUDGET"
        assert blocked[ActionType.EQUIP_RING] == "WRONG_MODE"
        assert ActionType.EQUIP not in blocked
        assert available == [ActionType.EQUIP]

    def test_nothing_is_blocked_out_of_combat(self) -> None:
        player = _player()
        player.inventory.extend([_chain_mail(), _shield(), _sword(), _ring()])

        assert blocked_equipment_actions(player, _ctx({"player_1": player})) == []


class TestTakeInCombat:
    def _setup(
        self, corpse_pos: Position, *, budget: TurnBudget | None = None
    ) -> tuple[PlayerCharacter, Creature, ActionContext, TurnBudget]:
        player = _player()
        corpse = _corpse()
        entities: dict[str, Entity] = {"player_1": player, "goblin_corpse": corpse}
        combat = _combat({"player_1": Position(10, 10)}, corpses={"goblin_corpse": corpse_pos})
        b = budget if budget is not None else TurnBudget()
        return player, corpse, _ctx(entities, combat=combat, budget=b), b

    def test_take_is_available_in_any_mode_and_costs_an_action(self) -> None:
        d = get_action_def(ActionType.TAKE)
        assert d.combat_mode is CombatMode.ANY
        assert d.cost_type is CostType.ACTION

    @pytest.mark.parametrize("pos", [Position(15, 10), Position(15, 15), Position(5, 5), Position(10, 10)])
    def test_take_adjacent_corpse_succeeds_and_charges_the_action(self, pos: Position) -> None:
        player, corpse, ctx, budget = self._setup(pos)

        result = _dispatch(player, Action(name=ActionType.TAKE, params={"target_id": corpse.id}), ctx)

        assert result.success, result.error
        assert player.gold == 7
        assert [i.name for i in player.inventory] == ["Dagger"]
        assert corpse.inventory == []
        assert budget.actions == 0
        assert budget.bonus_actions == 1
        assert budget.movement_remaining == 30

    @pytest.mark.parametrize("pos", [Position(20, 10), Position(20, 20), Position(10, 25)])
    def test_take_non_adjacent_rejected_without_charge(self, pos: Position) -> None:
        player, corpse, ctx, budget = self._setup(pos)

        result = _dispatch(player, Action(name=ActionType.TAKE, params={"target_id": corpse.id}), ctx)

        assert not result.success
        assert "adjacent" in (result.error or "")
        assert budget == TurnBudget()
        assert corpse.gold == 7
        assert player.inventory == []

    def test_second_take_without_action_rejected(self) -> None:
        player = _player()
        first, second = _corpse("corpse_a"), _corpse("corpse_b", gold=3)
        entities: dict[str, Entity] = {"player_1": player, "corpse_a": first, "corpse_b": second}
        combat = _combat(
            {"player_1": Position(10, 10)}, corpses={"corpse_a": Position(15, 10), "corpse_b": Position(5, 10)}
        )
        budget = TurnBudget()
        ctx = _ctx(entities, combat=combat, budget=budget)

        assert _dispatch(player, Action(name=ActionType.TAKE, params={"target_id": "corpse_a"}), ctx).success
        result = _dispatch(player, Action(name=ActionType.TAKE, params={"target_id": "corpse_b"}), ctx)

        assert not result.success
        assert second.gold == 3
        assert player.gold == 7

    def test_lootable_without_a_grid_cell_is_not_reachable_in_combat(self) -> None:
        player = _player()
        chest = Container(id="chest", name="Chest", location_id=CAVE, gold=20, is_open=True)
        entities: dict[str, Entity] = {"player_1": player, "chest": chest}
        budget = TurnBudget()
        ctx = _ctx(entities, combat=_combat({"player_1": Position(10, 10)}), budget=budget)

        result = _dispatch(player, Action(name=ActionType.TAKE, params={"target_id": "chest"}), ctx)

        assert not result.success
        assert "battle map" in (result.error or "")
        assert chest.gold == 20
        assert budget == TurnBudget()

    def test_take_out_of_combat_unchanged(self) -> None:
        """No grid, no reach limit, no budget; TAKE still does not end the peaceful turn."""
        player = _player()
        corpse = _corpse()
        ctx = _ctx({"player_1": player, "goblin_corpse": corpse})

        result = _dispatch(player, Action(name=ActionType.TAKE, params={"target_id": corpse.id}), ctx)

        assert result.success
        assert player.gold == 7
        assert not ends_peaceful_turn(Action(name=ActionType.TAKE, params={"target_id": corpse.id}))

    def test_provider_offers_take_only_with_a_holder_in_reach(self) -> None:
        player = _player()
        corpse = _corpse()
        entities: dict[str, Entity] = {"player_1": player, "goblin_corpse": corpse}
        provider = LootActionProvider(lambda loc: [corpse])

        near = _ctx(entities, combat=_combat({"player_1": Position(10, 10)}, {"goblin_corpse": Position(15, 15)}))
        far = _ctx(entities, combat=_combat({"player_1": Position(10, 10)}, {"goblin_corpse": Position(30, 30)}))
        spent = replace_budget(near, TurnBudget(actions=0))

        assert provider.get_action_types(player, near) == [ActionType.TAKE]
        assert provider.get_action_types(player, far) == []
        assert provider.get_action_types(player, spent) == []


def replace_budget(ctx: ActionContext, budget: TurnBudget) -> ActionContext:
    from dataclasses import replace

    return replace(ctx, turn_budget=budget)


# ── Corpse cell on the battle map ────────────────────────────────────


class TestCorpseCell:
    def _manager(self) -> tuple[CombatManager, dict[str, Entity]]:
        player = _player()
        orc = Creature(id="orc", name="Orc", location_id=CAVE, max_hp=15, current_hp=15)
        goblin = Creature(id="goblin", name="Goblin", location_id=CAVE, max_hp=7, current_hp=7)
        entities: dict[str, Entity] = {"player_1": player, "orc": orc, "goblin": goblin}
        mgr = CombatManager(entities, defaultdict(list))
        bm = BattleMap(width=60, height=60)
        bm.set_position("player_1", Position(10, 10))
        bm.set_position("orc", Position(30, 30))
        bm.set_position("goblin", Position(15, 10))
        mgr._combats[CAVE] = CombatState(
            location_id=CAVE,
            turn_order=["player_1", "orc", "goblin"],
            battle_map=bm,
            sides={0: {"player_1"}, 1: {"orc", "goblin"}},
            entity_to_side={"player_1": 0, "orc": 1, "goblin": 1},
        )
        return mgr, entities

    def test_dead_creature_keeps_its_last_cell_as_a_corpse_cell(self) -> None:
        mgr, entities = self._manager()
        goblin = cast(Creature, entities["goblin"])
        goblin.current_hp = 0

        mgr.remove_from_combat(CAVE, "goblin")

        combat = mgr.get_combat(CAVE)
        assert combat is not None
        assert combat.battle_map.get_position("goblin") is None  # no longer occupies a cell
        assert combat.battle_map.corpses == {"goblin": Position(15, 10)}
        assert combat.battle_map.loot_position("goblin") == Position(15, 10)

    def test_living_creature_leaving_combat_leaves_no_corpse(self) -> None:
        mgr, _entities = self._manager()

        mgr.remove_from_combat(CAVE, "goblin")

        combat = mgr.get_combat(CAVE)
        assert combat is not None
        assert combat.battle_map.corpses == {}

    def test_corpse_cells_survive_save_and_load(self) -> None:
        combat = _combat({"player_1": Position(10, 10)}, corpses={"goblin": Position(15, 10)})

        restored = deserialize_combats(serialize_combats({CAVE: combat}))

        assert restored[CAVE].battle_map.corpses == {"goblin": Position(15, 10)}
        assert restored[CAVE].battle_map.positions == {"player_1": Position(10, 10)}

    def test_saves_without_corpse_cells_still_load(self) -> None:
        data = serialize_combats({CAVE: _combat({"player_1": Position(10, 10)})})
        battle_map = cast(dict[str, dict[str, object]], data[CAVE])["battle_map"]
        assert isinstance(battle_map, dict)
        del battle_map["corpses"]

        assert deserialize_combats(data)[CAVE].battle_map.corpses == {}


# ── Combat awareness lootables ───────────────────────────────────────


class TestCombatLootAwareness:
    def test_lootables_carry_reach_and_reason(self) -> None:
        player = _player()
        near, far = _corpse("near"), _corpse("far")
        chest = Container(id="chest", name="Chest", location_id=CAVE, is_open=True)
        orc = Creature(id="orc", name="Orc", location_id=CAVE, max_hp=15, current_hp=15)
        entities: dict[str, Entity] = {"player_1": player, "near": near, "far": far, "chest": chest, "orc": orc}
        combat = _combat(
            {"player_1": Position(10, 10), "orc": Position(40, 40)},
            corpses={"near": Position(15, 15), "far": Position(30, 10)},
        )
        mgr = MagicMock()
        mgr.get_combat.return_value = combat
        builder = AwarenessBuilder(entities, defaultdict(list), mgr)

        lootables = {lt.id: lt for lt in builder.build_combat_awareness(player).lootables}

        assert set(lootables) == {"near", "far", "chest"}
        assert lootables["near"].in_reach and lootables["near"].reason_key is None
        assert lootables["near"].distance_ft == 5
        assert lootables["near"].loot_gold == 7
        assert [i.name for i in lootables["near"].loot_items] == ["Dagger"]
        assert not lootables["far"].in_reach
        assert lootables["far"].reason_key == LootBlock.TOO_FAR.value
        assert lootables["far"].distance_ft == 20
        assert lootables["far"].reason
        assert not lootables["chest"].in_reach
        assert lootables["chest"].reason_key == LootBlock.NOT_ON_MAP.value
        assert lootables["chest"].distance_ft is None


# ── ends_peaceful_turn registry rule ─────────────────────────────────

# TAKE is the one combat_mode=ANY action that does not end a peaceful turn: looting
# several holders back to back outside combat is the existing behaviour (like BUY/SELL).
_PEACEFUL_TURN_CONTINUES = frozenset({ActionType.TAKE})


class TestEndsPeacefulTurnRegistry:
    def test_every_any_mode_action_ends_the_peaceful_turn_except_take(self) -> None:
        """Rule: a non-internal combat_mode=ANY action is a real turn in peaceful mode and ends it."""
        mismatched = {
            at: d.ends_peaceful_turn
            for at, d in ACTION_DEFS.items()
            if d.combat_mode is CombatMode.ANY
            and not d.internal
            and d.ends_peaceful_turn != (at not in _PEACEFUL_TURN_CONTINUES)
        }
        assert mismatched == {}

    def test_rule_covers_the_actions_named_by_the_issue(self) -> None:
        for at in (ActionType.BLESS, ActionType.SECOND_WIND, ActionType.LAY_ON_HANDS, ActionType.USE_ITEM):
            assert get_action_def(at).combat_mode is CombatMode.ANY
            assert get_action_def(at).ends_peaceful_turn, at
        assert not get_action_def(ActionType.TAKE).ends_peaceful_turn
