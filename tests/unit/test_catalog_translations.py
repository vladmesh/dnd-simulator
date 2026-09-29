"""Catalog item and attack names reach the player translated (RU) and unchanged (EN).

The names live in YAML, not Python, so they are listed by ``content_loader.catalog_messages``
instead of a hand-maintained ``_()`` list; these tests fail when a catalog entry has no Russian
translation or a player-facing surface shows a catalog name without gettext.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from babel.messages.pofile import read_po

import dnd_simulator
from dnd_simulator.content_loader import parse_items
from dnd_simulator.content_loader.catalog_messages import append_to_pot, catalog_msgids
from dnd_simulator.content_loader.catalogs import load_catalog
from dnd_simulator.content_loader.schemas import ItemContent
from dnd_simulator.core.awareness import item_info
from dnd_simulator.core.character import AbilityScores, Alignment, CharClass, Race
from dnd_simulator.core.events import EquipmentPayload
from dnd_simulator.core.items import EquipmentSlot, Item
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.i18n import _, set_language
from dnd_simulator.layers.entities import perception
from dnd_simulator.layers.entities.awareness_builder import AwarenessBuilder
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.service.transport_payloads import build_inventory_payload

CONTENT_ROOT = Path(__file__).resolve().parents[2] / "content"
RU_PO = Path(dnd_simulator.__file__).parent / "locale" / "ru" / "LC_MESSAGES" / "dnd_simulator.po"


@pytest.fixture(autouse=True)
def _english_after() -> Iterator[None]:
    yield
    set_language("en")


@pytest.fixture(scope="module")
def msgids() -> dict[str, list[str]]:
    return catalog_msgids(CONTENT_ROOT)


@pytest.fixture(scope="module")
def item_catalog() -> dict[str, ItemContent]:
    return load_catalog(CONTENT_ROOT / "catalogs" / "items", ItemContent)


def _item(ref: str, catalog: dict[str, ItemContent]) -> Item:
    return parse_items([{"ref": ref}], item_catalog=catalog)[0]


def _player(**kwargs: object) -> PlayerCharacter:
    return PlayerCharacter(
        id="player",
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


class TestCatalogMsgids:
    def test_covers_item_names_attack_names_and_monster_attacks(self, msgids: dict[str, list[str]]) -> None:
        assert "Chain Mail" in msgids
        assert "Shield" in msgids
        assert "longsword slash" in msgids
        assert msgids["scimitar"] == ["catalogs/monsters/goblin.yaml", "catalogs/monsters/goblin_boss.yaml"]

    def test_every_catalog_name_has_a_russian_translation(self, msgids: dict[str, list[str]]) -> None:
        with RU_PO.open("rb") as fh:
            translated = {str(m.id): str(m.string) for m in read_po(fh) if m.id and m.string}
        missing = sorted(msgid for msgid in msgids if msgid not in translated)
        assert missing == [], f"catalog names without a ru msgstr in {RU_PO.name}: {missing}"

    def test_compiled_catalog_translates_every_catalog_name(self, msgids: dict[str, list[str]]) -> None:
        """The .mo is compiled from the .po: ru gettext returns a translation for each name."""
        set_language("ru")
        untranslated = sorted(msgid for msgid in msgids if _(msgid) == msgid)
        assert untranslated == [], f"run `make compile-messages`; untranslated: {untranslated}"

    def test_perception_no_longer_hand_lists_catalog_names(self, msgids: dict[str, list[str]]) -> None:
        set_language("en")
        assert set(perception._TRANSLATABLE_STRINGS) & set(msgids) == set()


class TestPotExtraction:
    def test_appends_missing_catalog_msgids_once(self, tmp_path: Path, msgids: dict[str, list[str]]) -> None:
        pot = tmp_path / "messages.pot"
        header = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
        pot.write_text(header + 'msgid "Shield"\nmsgstr ""\n')

        added = append_to_pot(pot, CONTENT_ROOT)

        assert added == len(msgids) - 1
        with pot.open("rb") as fh:
            messages = {str(m.id): m for m in read_po(fh) if m.id}
        assert set(messages) == set(msgids)
        assert ("content/catalogs/items/chain_mail.yaml", None) in messages["Chain Mail"].locations
        assert append_to_pot(pot, CONTENT_ROOT) == 0


class TestPlayerFacingNames:
    def test_combat_panel_weapon_is_translated_in_russian(self, item_catalog: dict[str, ItemContent]) -> None:
        player = _player(equipped={EquipmentSlot.WEAPON: _item("longsword", item_catalog)})
        layer = EntitiesLayer([player])

        set_language("en")
        assert layer.build_combat_awareness(player).self_weapon == "longsword slash"
        set_language("ru")
        assert layer.build_combat_awareness(player).self_weapon == "удар длинным мечом"

    def test_inventory_and_equipment_names_are_translated_in_russian(
        self, item_catalog: dict[str, ItemContent]
    ) -> None:
        mail = _item("chain_mail", item_catalog)
        player = _player(
            inventory=[_item("shield", item_catalog)],
            equipped={EquipmentSlot.ARMOR: mail},
        )

        set_language("en")
        assert build_inventory_payload(player)[0]["name"] == "Shield"
        assert item_info(mail).name == "Chain Mail"
        set_language("ru")
        assert build_inventory_payload(player)[0]["name"] == "Щит"
        assert item_info(mail).name == "Кольчуга"
        assert [e.name for e in AwarenessBuilder.build_equipped(player)] == ["Кольчуга"]

    def test_put_away_log_line_names_the_item_in_russian(self) -> None:
        observer = _player()
        event = Event(
            event_type=EventType.ENTITY_UNEQUIP,
            source_layer="entities",
            data=EquipmentPayload(entity_id="player", item_name="Shield"),
        )

        set_language("en")
        assert perceive_event(event, observer, lambda _eid: observer) == "You put away Shield"
        set_language("ru")
        assert "Щит" in perceive_event(event, observer, lambda _eid: observer)
