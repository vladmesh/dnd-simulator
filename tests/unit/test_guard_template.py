"""Tests for guard monster template and patrol content fixes.

Sprint 013, Phase 3, Task 1.
"""

from __future__ import annotations

from pathlib import Path

from dnd_simulator.content_loader import load_catalog, load_squads, parse_monster_template
from dnd_simulator.content_loader.schemas import MonsterTemplateContent

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
CATALOG_DIR = CONTENT_DIR / "catalogs" / "monsters"
SWORD_VALE_ECOLOGY = CONTENT_DIR / "library" / "ecology" / "sword_vale"


class TestGuardTemplate:
    """Guard monster template loads from catalog with SRD stats."""

    def test_guard_catalog_entry_exists(self) -> None:
        catalog = load_catalog(CATALOG_DIR, MonsterTemplateContent)
        assert "guard" in catalog

    def test_guard_stats_match_srd(self) -> None:
        """SRD Guard: HP 11 (2d8+2), AC 16 (chain shirt, shield), CR 1/8."""
        catalog = load_catalog(CATALOG_DIR, MonsterTemplateContent)
        guard = catalog["guard"]
        assert guard.hp == 11
        assert guard.ac == 16
        assert guard.speed == 30
        assert guard.cr == 0.125
        assert guard.ability_scores.str_ == 13
        assert guard.ability_scores.dex == 12
        assert guard.ability_scores.con == 12
        assert guard.ability_scores.int_ == 10
        assert guard.ability_scores.wis == 11
        assert guard.ability_scores.cha == 10

    def test_guard_has_spear_attack(self) -> None:
        catalog = load_catalog(CATALOG_DIR, MonsterTemplateContent)
        guard = catalog["guard"]
        assert len(guard.attacks) >= 1
        spear = guard.attacks[0]
        assert spear.name == "spear"

    def test_guard_spawn_produces_correct_creature(self) -> None:
        """Spawned creature gets guard's HP, AC, and attacks."""
        catalog = load_catalog(CATALOG_DIR, MonsterTemplateContent)
        template = parse_monster_template("guard", catalog["guard"].model_dump(by_alias=True))
        creature = template.spawn("test_location", "guard_001")
        assert creature.max_hp == 11
        assert creature.current_hp == 11
        assert creature.ac == 16
        assert creature.speed == 30
        assert len(creature.attacks) >= 1
        assert creature.attacks[0].name == "spear"


class TestPatrolSquadsUseGuards:
    """Patrol squads in library content reference guard, not bandit."""

    def test_kingdom_patrol_members_are_guards(self) -> None:
        squads = load_squads(SWORD_VALE_ECOLOGY)
        patrol = squads["kingdom_patrol_1"]
        assert patrol.member_templates == ["guard", "guard", "guard"]

    def test_kingdom_patrol_faction_is_kingdom(self) -> None:
        squads = load_squads(SWORD_VALE_ECOLOGY)
        patrol = squads["kingdom_patrol_1"]
        assert patrol.faction_id == "kingdom"
