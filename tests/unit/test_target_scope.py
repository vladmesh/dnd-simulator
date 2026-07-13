"""Tests for TargetMode/TargetScope enums and scope validation."""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.action_defs import TargetMode, TargetScope, get_action_def
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.rules.validation import (
    ActionContext,
    check_target_scope,
    check_target_valid,
)


def _creature(
    cid: str = "actor",
    *,
    location: str = "loc",
    faction: str = "guards",
) -> Creature:
    c = Creature(id=cid, name=cid.title(), location_id=location)
    c.faction_id = faction
    return c


def _combat_with_sides(
    sides: dict[int, set[str]],
) -> CombatState:
    """Build a minimal CombatState with pre-assigned sides."""
    cs = CombatState(location_id="loc")
    cs.sides = sides
    cs.entity_to_side = {eid: side for side, eids in sides.items() for eid in eids}
    return cs


# ---------------------------------------------------------------------------
# ActionDef — targeted property still works
# ---------------------------------------------------------------------------


class TestTargetedProperty:
    def test_attack_is_targeted(self) -> None:
        assert get_action_def(ActionType.ATTACK).targeted is True

    def test_opportunity_attack_is_targeted(self) -> None:
        assert get_action_def(ActionType.OPPORTUNITY_ATTACK).targeted is True

    def test_lay_on_hands_is_targeted(self) -> None:
        assert get_action_def(ActionType.LAY_ON_HANDS).targeted is True

    def test_dodge_not_targeted(self) -> None:
        assert get_action_def(ActionType.DODGE).targeted is False

    def test_idle_not_targeted(self) -> None:
        assert get_action_def(ActionType.IDLE).targeted is False

    def test_second_wind_not_targeted(self) -> None:
        assert get_action_def(ActionType.SECOND_WIND).targeted is False


# ---------------------------------------------------------------------------
# ActionDef — target_mode / target_scope values
# ---------------------------------------------------------------------------


class TestTargetModeMapping:
    def test_attack_single_hostile(self) -> None:
        ad = get_action_def(ActionType.ATTACK)
        assert ad.target_mode == TargetMode.SINGLE
        assert ad.target_scope == TargetScope.HOSTILE

    def test_lay_on_hands_single_ally(self) -> None:
        ad = get_action_def(ActionType.LAY_ON_HANDS)
        assert ad.target_mode == TargetMode.SINGLE
        assert ad.target_scope == TargetScope.ALLY

    def test_dodge_self(self) -> None:
        assert get_action_def(ActionType.DODGE).target_mode == TargetMode.SELF

    def test_dash_self(self) -> None:
        assert get_action_def(ActionType.DASH).target_mode == TargetMode.SELF

    def test_second_wind_self(self) -> None:
        assert get_action_def(ActionType.SECOND_WIND).target_mode == TargetMode.SELF

    def test_idle_none(self) -> None:
        assert get_action_def(ActionType.IDLE).target_mode == TargetMode.NONE

    def test_equip_none(self) -> None:
        assert get_action_def(ActionType.EQUIP).target_mode == TargetMode.NONE


# ---------------------------------------------------------------------------
# check_target_valid — uses target_mode instead of targeted bool
# ---------------------------------------------------------------------------


class TestCheckTargetValid:
    def test_probe_no_target_passes(self) -> None:
        """Probing (no target_id) always passes for targeted actions."""
        actor = _creature()
        action = Action(name=ActionType.ATTACK)
        ctx = ActionContext(is_combat=True, current_turn_entity_id="actor")
        assert check_target_valid(actor, action, ctx) is None

    def test_non_targeted_action_passes(self) -> None:
        """Non-targeted action skips target validation even with a target_id param."""
        actor = _creature()
        action = Action(name=ActionType.DODGE, params={"target_id": "someone"})
        ctx = ActionContext(is_combat=True, current_turn_entity_id="actor")
        assert check_target_valid(actor, action, ctx) is None


# ---------------------------------------------------------------------------
# check_target_scope — hostile / ally enforcement
# ---------------------------------------------------------------------------


class TestCheckTargetScope:
    """Scope validation: HOSTILE-scoped actions reject allies, ALLY-scoped reject hostiles."""

    def test_attack_hostile_target_passes(self) -> None:
        """Attack (HOSTILE scope) on enemy → OK."""
        actor = _creature("paladin")
        target = _creature("goblin", faction="goblins")
        combat = _combat_with_sides({0: {"paladin"}, 1: {"goblin"}})

        action = Action(name=ActionType.ATTACK, params={"target_id": "goblin"})
        ctx = ActionContext(
            is_combat=True,
            current_turn_entity_id="paladin",
            combat_state=combat,
            get_entity=lambda eid: {"paladin": actor, "goblin": target}[eid],
        )
        assert check_target_scope(actor, action, ctx) is None

    def test_attack_friendly_target_rejected(self) -> None:
        """Attack (HOSTILE scope) on ally → WRONG_TARGET_SCOPE."""
        actor = _creature("paladin")
        ally = _creature("cleric")  # same faction
        combat = _combat_with_sides({0: {"paladin", "cleric"}, 1: {"goblin"}})

        action = Action(name=ActionType.ATTACK, params={"target_id": "cleric"})
        ctx = ActionContext(
            is_combat=True,
            current_turn_entity_id="paladin",
            combat_state=combat,
            get_entity=lambda eid: {"paladin": actor, "cleric": ally}[eid],
        )
        error = check_target_scope(actor, action, ctx)
        assert error is not None
        assert error.code == "WRONG_TARGET_SCOPE"

    def test_lay_on_hands_ally_target_passes(self) -> None:
        """Lay on Hands (ALLY scope) on ally → OK."""
        actor = _creature("paladin")
        ally = _creature("cleric")
        combat = _combat_with_sides({0: {"paladin", "cleric"}, 1: {"goblin"}})

        action = Action(name=ActionType.LAY_ON_HANDS, params={"target_id": "cleric", "amount": 5})
        ctx = ActionContext(
            is_combat=True,
            current_turn_entity_id="paladin",
            combat_state=combat,
            get_entity=lambda eid: {"paladin": actor, "cleric": ally}[eid],
        )
        assert check_target_scope(actor, action, ctx) is None

    def test_lay_on_hands_self_passes(self) -> None:
        """Lay on Hands (ALLY scope) on self → OK."""
        actor = _creature("paladin")
        combat = _combat_with_sides({0: {"paladin"}, 1: {"goblin"}})

        action = Action(name=ActionType.LAY_ON_HANDS, params={"target_id": "paladin", "amount": 5})
        ctx = ActionContext(
            is_combat=True,
            current_turn_entity_id="paladin",
            combat_state=combat,
            get_entity=lambda eid: {"paladin": actor}[eid],
        )
        assert check_target_scope(actor, action, ctx) is None

    def test_lay_on_hands_hostile_target_rejected(self) -> None:
        """Lay on Hands (ALLY scope) on enemy → WRONG_TARGET_SCOPE."""
        actor = _creature("paladin")
        enemy = _creature("goblin", faction="goblins")
        combat = _combat_with_sides({0: {"paladin"}, 1: {"goblin"}})

        action = Action(name=ActionType.LAY_ON_HANDS, params={"target_id": "goblin", "amount": 5})
        ctx = ActionContext(
            is_combat=True,
            current_turn_entity_id="paladin",
            combat_state=combat,
            get_entity=lambda eid: {"paladin": actor, "goblin": enemy}[eid],
        )
        error = check_target_scope(actor, action, ctx)
        assert error is not None
        assert error.code == "WRONG_TARGET_SCOPE"

    def test_probe_no_target_passes(self) -> None:
        """No target_id in params → scope check is skipped (probe mode)."""
        actor = _creature("paladin")
        action = Action(name=ActionType.ATTACK)
        ctx = ActionContext(is_combat=True, current_turn_entity_id="paladin")
        assert check_target_scope(actor, action, ctx) is None

    def test_attack_same_faction_outside_combat_passes(self) -> None:
        """HOSTILE scope on same-faction target outside combat → allowed (auto-hostility in resolver)."""
        actor = _creature("player", faction="kingdom")
        target = _creature("npc", faction="kingdom")
        action = Action(name=ActionType.ATTACK, params={"target_id": "npc"})
        ctx = ActionContext(
            is_combat=False,
            current_turn_entity_id="player",
            combat_state=None,
            get_entity=lambda eid: {"player": actor, "npc": target}[eid],
        )
        assert check_target_scope(actor, action, ctx) is None

    def test_non_single_mode_skipped(self) -> None:
        """Actions with target_mode != SINGLE skip scope check entirely."""
        actor = _creature("paladin")
        action = Action(name=ActionType.DODGE, params={"target_id": "someone"})
        ctx = ActionContext(is_combat=True, current_turn_entity_id="paladin")
        assert check_target_scope(actor, action, ctx) is None


# ---------------------------------------------------------------------------
# Serialization — target_mode / target_scope in action_info
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_action_info_includes_target_mode_and_scope(self) -> None:
        """Serialized action_info dict includes target_mode and target_scope."""
        from dnd_simulator.core.awareness import CombatAwareness
        from dnd_simulator.service.transport_payloads import _awareness_to_dict

        awareness = CombatAwareness(
            self_hp=20,
            self_max_hp=20,
            self_ac=15,
            self_speed=30,
            self_weapon="Longsword",
            self_weapon_damage="1d8+3",
            available_actions=[ActionType.ATTACK, ActionType.DODGE, ActionType.LAY_ON_HANDS],
        )
        d = _awareness_to_dict(awareness)

        # Find attack action info
        attack_info = next(a for a in d["available_actions"] if a["name"] == "attack")
        assert attack_info["target_mode"] == "single"
        assert attack_info["target_scope"] == "hostile"

        # Find dodge action info
        dodge_info = next(a for a in d["available_actions"] if a["name"] == "dodge")
        assert dodge_info["target_mode"] == "self"
        assert dodge_info["target_scope"] == "hostile"  # default, irrelevant for self

        # Find lay_on_hands action info
        loh_info = next(a for a in d["available_actions"] if a["name"] == "lay_on_hands")
        assert loh_info["target_mode"] == "single"
        assert loh_info["target_scope"] == "ally"
