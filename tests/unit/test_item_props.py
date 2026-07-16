"""Structured item props in player-facing payloads (Sprint 024, Phase 3, Task 1).

Items resolved from the real catalog must carry a JSON-safe ``props`` dict
(built from the typed defs) through every player-facing channel: inventory,
equipped slots, merchant stock, and loot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dnd_simulator.content_loader import parse_items
from dnd_simulator.content_loader.catalogs import load_catalog
from dnd_simulator.content_loader.schemas import ItemContent
from dnd_simulator.core.awareness import item_props
from dnd_simulator.core.character import AbilityScores, Alignment, CharClass, Creature, NpcRole, Race
from dnd_simulator.core.items import EquipmentSlot, Item
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.awareness_builder import AwarenessBuilder
from dnd_simulator.layers.entities.combat_manager import CombatManager
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.service.transport_payloads import build_equipped_payload, build_inventory_payload

CATALOG_DIR = Path(__file__).resolve().parents[2] / "content" / "catalogs" / "items"


@pytest.fixture(scope="module")
def catalog() -> dict[str, ItemContent]:
    return load_catalog(CATALOG_DIR, ItemContent)


def _resolve(ref: str, catalog: dict[str, ItemContent]) -> Item:
    items = parse_items([{"ref": ref}], item_catalog=catalog)
    assert len(items) == 1
    return items[0]


def _creature(inventory: list[Item] | None = None) -> Creature:
    return Creature(
        id="c",
        name="C",
        location_id="loc",
        ability_scores=AbilityScores(),
        max_hp=10,
        current_hp=10,
        ac=10,
        inventory=inventory or [],
    )


def _player(**kwargs: object) -> PlayerCharacter:
    return PlayerCharacter(
        id="player_1",
        name="Hero",
        location_id="loc",
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        alignment=Alignment.TRUE_NEUTRAL,
        ability_scores=AbilityScores(),
        max_hp=20,
        current_hp=20,
        ac=16,
        **kwargs,  # type: ignore[arg-type]
    )


class TestInventoryChannel:
    def test_plate_props_in_inventory_payload(self, catalog: dict[str, ItemContent]) -> None:
        player = _player(inventory=[_resolve("plate", catalog)])
        entry = build_inventory_payload(player)[0]
        props = entry["props"]
        assert isinstance(props, dict)
        assert props["kind"] == "armor"
        assert props["base_ac"] == 18
        assert props["max_dex_bonus"] == 0
        assert props["category"] == "heavy"

    def test_frost_dagger_flags_in_available_items(self, catalog: dict[str, ItemContent]) -> None:
        creature = _creature(inventory=[_resolve("frost_dagger", catalog)])
        info = AwarenessBuilder.build_available_items(creature)[0]
        assert info.props is not None
        assert info.props["kind"] == "weapon"
        assert info.props["is_finesse"] is True
        assert info.props["is_light"] is True
        assert info.props["ability"] == "dex"

    def test_potion_and_shield_props(self, catalog: dict[str, ItemContent]) -> None:
        player = _player(inventory=[_resolve("health_potion", catalog), _resolve("shield", catalog)])
        by_name = {entry["name"]: entry["props"] for entry in build_inventory_payload(player)}
        potion = by_name["Health Potion"]
        assert isinstance(potion, dict)
        assert potion["kind"] == "potion"
        assert potion["heal_dice"] == "2d4+2"
        shield = by_name["Shield"]
        assert isinstance(shield, dict)
        assert shield["kind"] == "shield"
        assert shield["ac_bonus"] == 2

    def test_plain_item_has_no_props(self) -> None:
        from dnd_simulator.core.items import ItemType

        plain = Item(id="rock_0", name="Rock", item_type=ItemType.WEAPON)
        player = _player(inventory=[plain])
        assert build_inventory_payload(player)[0]["props"] is None


class TestMerchantChannel:
    def test_flaming_longsword_props_via_merchant_awareness(self, catalog: dict[str, ItemContent]) -> None:
        merchant = Npc(
            id="merchant_1",
            name="Gretta",
            location_id="loc",
            ability_scores=AbilityScores(),
            max_hp=10,
            current_hp=10,
            ac=10,
            role=NpcRole.MERCHANT,
            gold=500,
            inventory=[_resolve("flaming_longsword", catalog)],
        )
        player = _creature()
        entities: dict[str, object] = {merchant.id: merchant, player.id: player}
        builder = AwarenessBuilder(entities, {}, CombatManager(entities, {}))  # type: ignore[arg-type]
        merchants = builder.build_merchants(player, hour=12)
        assert len(merchants) == 1
        props = merchants[0].items[0].props
        assert props is not None
        assert props["kind"] == "weapon"
        assert props["category"] == "martial"
        assert props["modifier"] == 1
        assert props["is_magic"] is True
        assert props["damage"] == [
            {"dice": "1d8", "type": "slashing"},
            {"dice": "1d6", "type": "fire"},
        ]


class TestEquippedChannel:
    def test_ring_of_protection_props_in_equipped_payload(self, catalog: dict[str, ItemContent]) -> None:
        ring = _resolve("ring_of_protection", catalog)
        player = _player(equipped={EquipmentSlot.RING: ring})
        entry = next(e for e in build_equipped_payload(player) if e["slot"] == "ring")
        props = entry["props"]
        assert isinstance(props, dict)
        assert props["kind"] == "accessory"
        assert props["slot"] == "ring"
        assert props["modifiers"] == [{"stat": "ac", "op": "add", "value": 1}]


class TestLootChannel:
    def test_dead_creature_loot_items_carry_props(self, catalog: dict[str, ItemContent]) -> None:
        corpse = _creature(inventory=[_resolve("longsword", catalog)])
        corpse.id = "corpse_1"
        corpse.current_hp = 0
        observer = _creature()
        entities: dict[str, object] = {corpse.id: corpse, observer.id: observer}
        builder = AwarenessBuilder(entities, {}, CombatManager(entities, {}))  # type: ignore[arg-type]
        nearby = builder.build_nearby_entities(observer, hour=12)
        loot = next(e for e in nearby if e.id == "corpse_1")
        assert loot.loot_items, "corpse inventory should surface as loot"
        props = loot.loot_items[0].props
        assert props is not None
        assert props["kind"] == "weapon"
        assert props["damage"] == [{"dice": "1d8", "type": "slashing"}]
        assert props["reach"] == 5


class TestJsonSafety:
    def test_every_catalog_entry_props_is_json_safe(self, catalog: dict[str, ItemContent]) -> None:
        """Guards against enum leakage or new non-primitive fields in props.

        Merchant/loot payloads go through dataclasses.asdict without a blanket
        _json_safe pass, so props must be pure primitives at build time.
        """
        for stem in catalog:
            item = _resolve(stem, catalog)
            props = item_props(item)
            json.dumps(props)  # raises TypeError if anything non-primitive leaks in
