"""Tests for EntityKind(StrEnum) — runtime entity discriminator.

Covers save/load round-trip using EntityKind values, query filter acceptance
(both enum members and raw strings via StrEnum equality), and fail-fast on
unknown entity_type in save data.
"""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    CharClass,
    Creature,
    DamageComponent,
    DamageType,
    NpcRole,
    Race,
)
from dnd_simulator.core.models import EntityKind, Query, QueryType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc


def _scores(**overrides: int) -> AbilityScores:
    scores = dict(AbilityScores().scores)
    for name, val in overrides.items():
        scores[Ability[name.upper()]] = val
    return AbilityScores(scores=scores)


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


class TestEntityKindEnum:
    def test_strenum_equal_to_string(self) -> None:
        assert EntityKind.PLAYER == "player"
        assert EntityKind.NPC == "npc"
        assert EntityKind.CREATURE == "creature"
        assert EntityKind.MONSTER == "monster"

    def test_constructor_rejects_unknown(self) -> None:
        with pytest.raises(ValueError):
            EntityKind("wizard_cat")


class TestSaveLoadUsesEntityKind:
    def test_save_emits_entity_kind_values(self) -> None:
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="tavern",
            ability_scores=_scores(STR=14),
            attacks=(_sword(),),
            race=Race.HUMAN,
            char_class=CharClass.FIGHTER,
            level=1,
            max_hp=10,
            current_hp=10,
        )
        npc = Npc(
            id="n1",
            name="Olga",
            location_id="tavern",
            role=NpcRole.TAVERN_KEEPER,
            settlement_id="village",
            max_hp=8,
            current_hp=8,
        )
        monster = Creature(
            id="m1",
            name="Wolf",
            location_id="forest",
            max_hp=11,
            current_hp=11,
            ac=13,
            speed=40,
            ability_scores=_scores(STR=12, DEX=15),
            attacks=(_sword(),),
        )
        layer = EntitiesLayer(entities=[player, npc, monster])
        state = layer.get_state()
        entities = state["entities"]
        assert isinstance(entities, dict)

        # Save emits the enum VALUE (string), callers expect string in JSON.
        assert entities["p1"]["entity_type"] == EntityKind.PLAYER
        assert entities["n1"]["entity_type"] == EntityKind.NPC
        assert entities["m1"]["entity_type"] == EntityKind.CREATURE

    def test_load_with_unknown_entity_type_raises(self) -> None:
        """Fail-fast: save data with unknown entity_type must not be silently skipped."""
        layer = EntitiesLayer(entities=[])
        bad_state: dict[str, object] = {
            "entities": {
                "x1": {
                    "id": "x1",
                    "name": "Ghost",
                    "location_id": "void",
                    "entity_type": "phantom",
                }
            }
        }
        with pytest.raises(ValueError, match="phantom"):
            layer.load_state(bad_state)


class TestQueryFilterAcceptsEntityKind:
    def _layer_with_mixed(self) -> EntitiesLayer:
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="tavern",
            ability_scores=_scores(STR=14),
            attacks=(_sword(),),
            race=Race.HUMAN,
            char_class=CharClass.FIGHTER,
            level=1,
            max_hp=10,
            current_hp=10,
        )
        npc = Npc(
            id="n1",
            name="Olga",
            location_id="tavern",
            role=NpcRole.TAVERN_KEEPER,
            settlement_id="village",
            max_hp=8,
            current_hp=8,
        )
        monster = Creature(
            id="m1",
            name="Wolf",
            location_id="tavern",
            max_hp=11,
            current_hp=11,
            ac=13,
            speed=40,
            ability_scores=_scores(STR=12, DEX=15),
            attacks=(_sword(),),
        )
        return EntitiesLayer(entities=[player, npc, monster])

    def test_filter_by_enum_player(self) -> None:
        layer = self._layer_with_mixed()
        answer = layer.query(Query(question=QueryType.ALL_CREATURES, params={"entity_type": EntityKind.PLAYER}))
        ids = {e["id"] for e in answer.value}
        assert ids == {"p1"}

    def test_filter_by_enum_npc(self) -> None:
        layer = self._layer_with_mixed()
        answer = layer.query(Query(question=QueryType.ALL_CREATURES, params={"entity_type": EntityKind.NPC}))
        ids = {e["id"] for e in answer.value}
        assert ids == {"n1"}

    def test_filter_by_enum_monster(self) -> None:
        layer = self._layer_with_mixed()
        answer = layer.query(Query(question=QueryType.ALL_CREATURES, params={"entity_type": EntityKind.MONSTER}))
        ids = {e["id"] for e in answer.value}
        assert ids == {"m1"}

    def test_filter_by_raw_string_still_works(self) -> None:
        """API/JSON callers pass strings — StrEnum equality keeps them working."""
        layer = self._layer_with_mixed()
        answer = layer.query(Query(question=QueryType.ALL_CREATURES, params={"entity_type": "player"}))
        ids = {e["id"] for e in answer.value}
        assert ids == {"p1"}
