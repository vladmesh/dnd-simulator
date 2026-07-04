"""Serialization dedup pins (phase 3 task 1).

Round-trip fidelity for GameDateTime and item (de)serialization. These pin the
save format byte-for-byte across the dedup refactor: GameDateTime.to_dict/from_dict
replacing hand-rolled dict-building, and item ser/deser consolidated in content_loader
so core/player no longer imports content_loader (cycle break).
"""

from __future__ import annotations

from dnd_simulator.core.models import GameDateTime


class TestGameDateTimeDict:
    def test_to_from_dict_roundtrip(self) -> None:
        gdt = GameDateTime(year=1490, month=6, day=12, hour=10, minute=30, second=45)
        assert GameDateTime.from_dict(gdt.to_dict()) == gdt

    def test_to_dict_keys(self) -> None:
        gdt = GameDateTime(year=1490, month=6, day=1, hour=10, minute=0, second=0)
        assert gdt.to_dict() == {
            "year": 1490,
            "month": 6,
            "day": 1,
            "hour": 10,
            "minute": 0,
            "second": 0,
        }

    def test_from_dict_missing_second_defaults_zero(self) -> None:
        """Old saves predate the 'second' field — must default to 0, not crash."""
        old = {"year": 1490, "month": 6, "day": 1, "hour": 10, "minute": 30}
        restored = GameDateTime.from_dict(old)
        assert restored.second == 0
        assert restored == GameDateTime(year=1490, month=6, day=1, hour=10, minute=30, second=0)

    def test_from_dict_empty_defaults(self) -> None:
        """Fully empty dict falls back to GameDateTime defaults."""
        assert GameDateTime.from_dict({}) == GameDateTime()


def _rt(data: dict[str, object]) -> None:
    """Assert an item dict survives deserialize -> serialize -> deserialize unchanged."""
    from dnd_simulator.content_loader.items import deserialize_item, serialize_item

    item = deserialize_item(data)
    again = deserialize_item(serialize_item(item))
    assert again == item


class TestItemRoundTrip:
    def test_magic_weapon_roundtrip(self) -> None:
        _rt(
            {
                "id": "flame_sword_0",
                "name": "Flame Sword",
                "type": "weapon",
                "weapon_id": "longsword",
                "attack_name": "Flame Sword",
                "category": "martial",
                "damage": [{"dice": "1d8", "type": "slashing"}, {"dice": "1d6", "type": "fire"}],
                "reach": 5,
                "ability": "str",
                "modifier": 1,
                "is_magic": True,
                "is_finesse": False,
                "price": 500,
            }
        )

    def test_finesse_weapon_with_conditions(self) -> None:
        _rt(
            {
                "id": "venom_dagger_0",
                "name": "Venom Dagger",
                "type": "weapon",
                "weapon_id": "dagger",
                "attack_name": "Venom Dagger",
                "category": "simple",
                "damage": [{"dice": "1d4", "type": "piercing"}],
                "reach": 5,
                "ability": "dex",
                "modifier": 0,
                "is_magic": False,
                "is_finesse": True,
                "grant_conditions": ["poisoned"],
            }
        )

    def test_armor_roundtrip(self) -> None:
        _rt(
            {
                "id": "plate_0",
                "name": "Plate Armor",
                "type": "armor",
                "armor_id": "plate",
                "category": "heavy",
                "base_ac": 18,
                "max_dex_bonus": 0,
                "price": 1500,
            }
        )

    def test_shield_roundtrip(self) -> None:
        _rt(
            {
                "id": "shield_0",
                "name": "Shield",
                "type": "shield",
                "shield_id": "shield",
                "ac_bonus": 2,
            }
        )

    def test_accessory_with_modifiers_roundtrip(self) -> None:
        """The BLOCKER fixture: ring_of_protection with grant_modifiers survives round-trip."""
        _rt(
            {
                "id": "ring_of_protection_0",
                "name": "Ring of Protection",
                "type": "accessory",
                "accessory_id": "ring_of_protection",
                "slot": "ring",
                "grant_modifiers": [
                    {"stat": "ac", "op": "add", "value": 1, "source": "ring_of_protection"},
                ],
            }
        )

    def test_potion_roundtrip(self) -> None:
        _rt(
            {
                "id": "healing_potion_0",
                "name": "Healing Potion",
                "type": "potion",
                "heal_dice": "2d4+2",
            }
        )
