"""Branch coverage for service/commands_creatures.py: GM patch, give-item, remove and inner-self validation paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.core.character import Character, Creature
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.container import Container
from dnd_simulator.core.inner_self import InnerSelf
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _creature(creature_id: str) -> Creature:
    return Creature(
        id=creature_id,
        name=creature_id,
        location_id="nowhere",
        max_hp=10,
        current_hp=10,
        ac=10,
        speed=30,
        faction_id="raiders",
    )


def _session(tmp_path: Path) -> tuple[GameService, str, EntitiesLayer]:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    session = service.start_game()
    layer = service._get_entities_layer(service._get_session(session.session_id))
    return service, session.session_id, layer


@pytest.fixture
def setup(tmp_path: Path) -> tuple[GameService, str, EntitiesLayer]:
    return _session(tmp_path)


class TestPatchCreature:
    def test_patches_plain_creature_stats(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, layer = setup
        creature = _creature("ogre")
        layer.add_entity(creature)

        service.patch_creature(
            sid,
            "ogre",
            {"max_hp": 40, "ac": 15, "location_id": "elsewhere", "xp_value": 450, "conditions": ["prone"]},
        )

        assert creature.max_hp == 40
        assert creature.ac == 15
        assert creature.location_id == "elsewhere"
        assert creature.xp_value == 450
        assert creature.conditions == {Condition.PRONE: None}

    def test_conditions_mapping_keeps_durations(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, layer = setup
        creature = _creature("ogre")
        layer.add_entity(creature)

        service.patch_creature(sid, "ogre", {"conditions": {"prone": 2, "blinded": None}})

        assert creature.conditions == {Condition.PRONE: 2, Condition.BLINDED: None}

    def test_resource_pool_replaced_by_id(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, layer = setup
        creature = _creature("ogre")
        creature.resource_pools = [ResourcePool(id="rage", max_uses=2, current_uses=2, reset_on=RestType.LONG_REST)]
        layer.add_entity(creature)

        service.patch_creature(
            sid,
            "ogre",
            {
                "resource_pools": [
                    {"id": "rage", "max_uses": 3, "current_uses": 1, "reset_on": "long_rest"},
                    {"id": "roar", "max_uses": 1, "current_uses": 1, "reset_on": "short_rest"},
                ]
            },
        )

        pools = {pool.id: pool for pool in creature.resource_pools}
        assert len(creature.resource_pools) == 2
        assert (pools["rage"].max_uses, pools["rage"].current_uses) == (3, 1)
        assert pools["roar"].reset_on is RestType.SHORT_REST

    def test_character_level_and_experience(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, layer = setup
        player = Character(id="squire", name="Squire", location_id="nowhere", max_hp=10, current_hp=10)
        layer.add_entity(player)

        service.patch_creature(sid, player.id, {"level": 1, "experience": 300})

        assert player.level == 1
        assert player.experience == 300
        assert player.level_up_available is True

    def test_container_is_not_a_creature(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, layer = setup
        layer.add_entity(Container(id="chest", name="Chest", location_id="nowhere"))

        with pytest.raises(ValueError, match="is not a creature"):
            service.patch_creature(sid, "chest", {"ac": 12})


class TestRemoveAndGiveItem:
    def test_remove_unknown_creature_raises(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, _ = setup
        with pytest.raises(ValueError, match="not found"):
            service.remove_creature(sid, "ghost")

    def test_give_item_to_unknown_creature_raises(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, _ = setup
        with pytest.raises(ValueError, match="not found"):
            service.give_item(sid, "ghost", {"ref": "longsword"})

    def test_give_weapon_auto_equips_when_unarmed(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, layer = setup
        creature = _creature("ogre")
        layer.add_entity(creature)
        assert creature.equipped_weapon is None

        result = service.give_item(sid, "ogre", {"ref": "longsword", "equipped": True})

        assert creature.equipped_weapon is not None
        assert creature.equipped_weapon.id == result["item_id"]
        assert all(item.id != result["item_id"] for item in creature.inventory)


class TestActivationTrigger:
    def test_unknown_creature_raises(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, _ = setup
        with pytest.raises(ValueError, match="not found"):
            service.set_activation_trigger_armed(sid, "ghost", "t1", True)


class TestInnerSelfCoreValidation:
    def _bearer(self, layer: EntitiesLayer) -> None:
        creature = _creature("sage")
        creature.inner_self = InnerSelf()
        layer.add_entity(creature)

    def test_non_list_fields_rejected(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, layer = setup
        self._bearer(layer)
        with pytest.raises(ValueError, match="must be lists"):
            service.replace_creature_inner_self_core(sid, "sage", {"relations": {}, "goals": [], "mood": "calm"})

    def test_non_object_relationship_rejected(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, layer = setup
        self._bearer(layer)
        with pytest.raises(ValueError, match="relationship must be an object"):
            service.replace_creature_inner_self_core(sid, "sage", {"relations": ["x"], "goals": [], "mood": "calm"})

    def test_non_object_goal_rejected(self, setup: tuple[GameService, str, EntitiesLayer]) -> None:
        service, sid, layer = setup
        self._bearer(layer)
        with pytest.raises(ValueError, match="goal must be an object"):
            service.replace_creature_inner_self_core(sid, "sage", {"relations": [], "goals": ["x"], "mood": "calm"})
