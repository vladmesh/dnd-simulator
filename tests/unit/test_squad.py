"""Tests for Squad model and squads.yaml loading."""

from __future__ import annotations

from pathlib import Path

from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType


class TestSquadModel:
    """Squad dataclass structure and field semantics."""

    def test_patrol_squad_has_route_and_empty_territory(self) -> None:
        squad = Squad(
            id="kingdom_patrol_1",
            name="Kingdom Patrol",
            faction_id="kingdom",
            squad_type=SquadType.PATROL,
            behavior=SquadBehavior.PATROL,
            current_location_id="highfield_town_gate",
            route=["highfield_town_gate", "silverport_highfield_road", "silverport_city_gate"],
            territory=[],
            strength=5,
            max_strength=5,
            member_templates=["bandit", "bandit", "bandit"],
            tick_interval=3600,
        )
        assert squad.route == ["highfield_town_gate", "silverport_highfield_road", "silverport_city_gate"]
        assert squad.territory == []
        assert squad.squad_type == SquadType.PATROL

    def test_roaming_squad_has_territory_and_empty_route(self) -> None:
        squad = Squad(
            id="wolf_pack_1",
            name="Wolf Pack",
            faction_id="wildlife",
            squad_type=SquadType.MONSTER_PACK,
            behavior=SquadBehavior.ROAM,
            current_location_id="greenwood_village_edge",
            route=[],
            territory=["greenwood_village_edge", "greenwood_highfield_road"],
            strength=3,
            max_strength=3,
            member_templates=["wolf", "wolf", "wolf"],
            tick_interval=1800,
        )
        assert squad.territory == ["greenwood_village_edge", "greenwood_highfield_road"]
        assert squad.route == []
        assert squad.behavior == SquadBehavior.ROAM

    def test_squad_has_faction_id(self) -> None:
        squad = Squad(
            id="bandit_gang_1",
            name="Bandit Gang",
            faction_id="bandits",
            squad_type=SquadType.BANDIT,
            behavior=SquadBehavior.RAID,
            current_location_id="highfield_bogmire_road",
            route=[],
            territory=["highfield_bogmire_road", "bogmire_dustmere_road"],
            strength=4,
            max_strength=4,
            member_templates=["bandit", "bandit"],
            tick_interval=3600,
        )
        assert squad.faction_id == "bandits"


class TestSquadYamlParsing:
    """Loading squads from YAML content files."""

    def test_parse_patrol_squad_from_yaml(self) -> None:
        from dnd_simulator.content_loader import parse_squad

        data = {
            "name": {"en": "Kingdom Patrol", "ru": "Королевский патруль"},
            "faction": "kingdom",
            "type": "patrol",
            "behavior": "patrol",
            "start_location": "highfield_town_gate",
            "route": ["highfield_town_gate", "silverport_highfield_road"],
            "strength": 5,
            "members": ["bandit", "bandit", "bandit"],
            "tick_interval": 3600,
        }
        squad = parse_squad("kingdom_patrol_1", data, lang="en")
        assert squad.id == "kingdom_patrol_1"
        assert squad.name == "Kingdom Patrol"
        assert squad.faction_id == "kingdom"
        assert squad.squad_type == SquadType.PATROL
        assert squad.behavior == SquadBehavior.PATROL
        assert squad.current_location_id == "highfield_town_gate"
        assert squad.route == ["highfield_town_gate", "silverport_highfield_road"]
        assert squad.territory == []
        assert squad.strength == 5
        assert squad.max_strength == 5
        assert squad.member_templates == ["bandit", "bandit", "bandit"]
        assert squad.tick_interval == 3600

    def test_parse_roaming_squad_from_yaml(self) -> None:
        from dnd_simulator.content_loader import parse_squad

        data = {
            "name": {"en": "Wolf Pack", "ru": "Стая волков"},
            "faction": "wildlife",
            "type": "monster_pack",
            "behavior": "roam",
            "start_location": "greenwood_village_edge",
            "territory": ["greenwood_village_edge", "greenwood_highfield_road"],
            "strength": 3,
            "members": ["wolf", "wolf", "wolf"],
            "tick_interval": 1800,
        }
        squad = parse_squad("wolf_pack_1", data, lang="en")
        assert squad.territory == ["greenwood_village_edge", "greenwood_highfield_road"]
        assert squad.route == []
        assert squad.behavior == SquadBehavior.ROAM

    def test_parse_squad_i18n_name(self) -> None:
        from dnd_simulator.content_loader import parse_squad

        data = {
            "name": {"en": "Kingdom Patrol", "ru": "Королевский патруль"},
            "faction": "kingdom",
            "type": "patrol",
            "behavior": "patrol",
            "start_location": "highfield_town_gate",
            "strength": 5,
            "members": ["bandit"],
            "tick_interval": 3600,
        }
        squad_ru = parse_squad("kp1", data, lang="ru")
        assert squad_ru.name == "Королевский патруль"

    def test_load_squads_from_world_directory(self, tmp_path: Path) -> None:
        from dnd_simulator.content_loader import load_squads

        world_dir = tmp_path / "test_world"
        world_dir.mkdir()
        squads_yaml = world_dir / "squads.yaml"
        squads_yaml.write_text(
            """
kingdom_patrol_1:
  name: {en: Kingdom Patrol, ru: Королевский патруль}
  faction: kingdom
  type: patrol
  behavior: patrol
  start_location: highfield_town_gate
  route: [highfield_town_gate, silverport_highfield_road]
  strength: 5
  members: [bandit, bandit]
  tick_interval: 3600

wolf_pack_1:
  name: {en: Wolf Pack}
  faction: wildlife
  type: monster_pack
  behavior: roam
  start_location: greenwood_village_edge
  territory: [greenwood_village_edge]
  strength: 3
  members: [wolf, wolf, wolf]
  tick_interval: 1800
"""
        )
        squads = load_squads(world_dir, lang="en")
        assert len(squads) == 2
        assert "kingdom_patrol_1" in squads
        assert "wolf_pack_1" in squads
        assert squads["kingdom_patrol_1"].squad_type == SquadType.PATROL
        assert squads["wolf_pack_1"].behavior == SquadBehavior.ROAM

    def test_load_squads_missing_file_returns_empty(self, tmp_path: Path) -> None:
        from dnd_simulator.content_loader import load_squads

        world_dir = tmp_path / "empty_world"
        world_dir.mkdir()
        squads = load_squads(world_dir)
        assert squads == {}


class TestCreatureSquadId:
    """Creature.squad_id field for tracking squad membership."""

    def test_creature_default_squad_id_is_none(self) -> None:
        from dnd_simulator.core.character import Creature

        c = Creature(id="c1", name="Test", location_id="loc1")
        assert c.squad_id is None

    def test_creature_with_squad_id(self) -> None:
        from dnd_simulator.core.character import Creature

        c = Creature(id="c1", name="Test", location_id="loc1", squad_id="kingdom_patrol_1")
        assert c.squad_id == "kingdom_patrol_1"

    def test_two_creatures_same_squad(self) -> None:
        from dnd_simulator.core.character import Creature

        c1 = Creature(id="c1", name="Guard A", location_id="loc1", squad_id="kingdom_patrol_1")
        c2 = Creature(id="c2", name="Guard B", location_id="loc1", squad_id="kingdom_patrol_1")
        assert c1.squad_id == c2.squad_id


class TestSwordValeSquads:
    """Integration: load squads from the actual Sword Vale ecology library template."""

    def test_load_sword_vale_squads(self) -> None:
        from dnd_simulator.content_loader import load_squads

        library_path = Path(__file__).resolve().parents[2] / "content" / "library" / "ecology" / "sword_vale"
        squads = load_squads(library_path)
        assert len(squads) >= 3
        # All squads must have a faction
        for squad in squads.values():
            assert squad.faction_id, f"Squad {squad.id} has no faction_id"
