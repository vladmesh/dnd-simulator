"""Tests for monster spawn engine + temporary creature lifecycle."""

from __future__ import annotations

from unittest.mock import patch

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Creature,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.models import Event, EventType, GameDateTime
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer


def _make_template(template_id: str = "goblin", hp: int = 7, ac: int = 15) -> MonsterTemplate:
    return MonsterTemplate(
        id=template_id,
        name="Goblin",
        hp=hp,
        ac=ac,
        speed=30,
        ability_scores=AbilityScores.from_dict({"str": 8, "dex": 14, "con": 10, "int": 10, "wis": 8, "cha": 8}),
        attacks=(
            Attack(
                name="scimitar",
                ability=Ability.DEX,
                damage=(DamageComponent(dice="1d6", type=DamageType.SLASHING),),
                reach=5,
            ),
        ),
        cr=0.25,
    )


def _make_player(location: str = "forest") -> PlayerCharacter:
    return PlayerCharacter(
        id="player1",
        name="Hero",
        location_id=location,
        race="human",
        char_class="fighter",
    )


def _make_layer(
    player: PlayerCharacter,
    templates: dict[str, MonsterTemplate] | None = None,
    encounters: dict[str, list[EncounterEntry]] | None = None,
) -> EntitiesLayer:
    return EntitiesLayer(
        entities=[player],
        monster_templates=templates or {},
        encounter_tables=encounters or {},
    )


class TestSpawnOnPlayerArrival:
    """When player enters a location with encounters, monsters spawn."""

    def test_spawn_on_successful_roll(self) -> None:
        """RNG success → creatures spawned at player location with template stats."""
        template = _make_template()
        encounters = {"forest": [EncounterEntry(template_id="goblin", chance=0.5, count_min=2, count_max=2)]}
        player = _make_player(location="tavern")
        layer = _make_layer(player, templates={"goblin": template}, encounters=encounters)

        # Player travels to forest
        player.location_id = "forest"

        # Roll succeeds (0.1 < 0.5 chance), count=2 (fixed)
        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.1  # below 0.5 → success
            mock_rng.randint.return_value = 2
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10))

        # Should have player + 2 goblins
        creatures = [e for e in layer.get_active_creatures() if e.id != "player1"]
        assert len(creatures) == 2
        for c in creatures:
            assert c.location_id == "forest"
            assert c.max_hp == 7
            assert c.ac == 15
            assert c.speed == 30
            assert c.temporary is True
            assert len(c.attacks) == 1
            assert c.attacks[0].name == "scimitar"

    def test_no_spawn_on_failed_roll(self) -> None:
        """RNG failure → no creatures spawned."""
        template = _make_template()
        encounters = {"forest": [EncounterEntry(template_id="goblin", chance=0.3, count_min=1, count_max=3)]}
        player = _make_player(location="tavern")
        layer = _make_layer(player, templates={"goblin": template}, encounters=encounters)

        player.location_id = "forest"

        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.9  # above 0.3 → fail
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10))

        creatures = [e for e in layer.get_active_creatures() if e.id != "player1"]
        assert len(creatures) == 0

    def test_no_spawn_at_location_without_encounters(self) -> None:
        """Location with no encounter table → nothing happens."""
        player = _make_player(location="tavern")
        layer = _make_layer(player)

        player.location_id = "forest"
        layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10))

        creatures = [e for e in layer.get_active_creatures() if e.id != "player1"]
        assert len(creatures) == 0


class TestSpawnedCreatureStats:
    """Spawned creatures get correct stats from template."""

    def test_spawned_creature_matches_template(self) -> None:
        template = _make_template(hp=11, ac=13)
        encounters = {"forest": [EncounterEntry(template_id="goblin", chance=1.0, count_min=1, count_max=1)]}
        player = _make_player(location="tavern")
        layer = _make_layer(player, templates={"goblin": template}, encounters=encounters)

        player.location_id = "forest"

        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10))

        creatures = [e for e in layer.get_active_creatures() if e.id != "player1"]
        assert len(creatures) == 1
        c = creatures[0]
        assert c.temporary is True
        assert c.max_hp == 11
        assert c.current_hp == 11
        assert c.ac == 13
        assert c.ability_scores[Ability.DEX] == 14


class TestTemporaryCreatureCleanup:
    """Temporary creatures removed on death, non-temporary preserved."""

    def test_temporary_creature_removed_on_death(self) -> None:
        """When a temporary creature dies, it's removed from the layer."""
        player = _make_player()
        layer = _make_layer(player)

        monster = Creature(
            id="goblin_1",
            name="Goblin",
            location_id="forest",
            temporary=True,
            max_hp=7,
            current_hp=0,  # dead
        )
        layer.add_entity(monster)

        death_event = Event(
            event_type=EventType.ENTITY_DIED,
            source_layer="entities",
            data={"entity_id": "goblin_1"},
        )

        def noop_query(layer: str, query: object) -> object:
            raise NotImplementedError

        def noop_emit(event: Event) -> object:
            raise NotImplementedError

        layer.handle_event(death_event, noop_query, noop_emit)  # type: ignore[arg-type]

        assert layer.get_entity("goblin_1") is None

    def test_non_temporary_creature_preserved_on_death(self) -> None:
        """Non-temporary creature stays in entities after death (existing behavior)."""
        player = _make_player()
        layer = _make_layer(player)

        npc = Creature(
            id="guard_1",
            name="Guard",
            location_id="forest",
            temporary=False,
            max_hp=20,
            current_hp=0,
        )
        layer.add_entity(npc)

        death_event = Event(
            event_type=EventType.ENTITY_DIED,
            source_layer="entities",
            data={"entity_id": "guard_1"},
        )

        def noop_query(layer: str, query: object) -> object:
            raise NotImplementedError

        def noop_emit(event: Event) -> object:
            raise NotImplementedError

        layer.handle_event(death_event, noop_query, noop_emit)  # type: ignore[arg-type]

        assert layer.get_entity("guard_1") is not None


class TestEncounterCooldown:
    """Cooldown prevents re-rolling encounters on repeated location entry."""

    def test_no_reroll_within_cooldown(self) -> None:
        """Same location within cooldown → no new spawn roll."""
        template = _make_template()
        encounters = {"forest": [EncounterEntry(template_id="goblin", chance=1.0, count_min=1, count_max=1)]}
        player = _make_player(location="tavern")
        layer = _make_layer(player, templates={"goblin": template}, encounters=encounters)

        player.location_id = "forest"

        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            time = GameDateTime(year=1490, month=6, day=1, hour=10)
            layer.update_activation(time)

        spawned_1 = [e for e in layer.get_active_creatures() if e.id != "player1"]
        assert len(spawned_1) == 1

        # Player leaves and comes back — same time (within cooldown)
        player.location_id = "tavern"
        layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10, minute=0, second=6))
        player.location_id = "forest"

        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10, minute=0, second=12))

        # Still only 1 spawned (no re-roll)
        spawned_2 = [e for e in layer.get_active_creatures() if e.id != "player1"]
        assert len(spawned_2) == 1

    def test_reroll_after_cooldown_expires(self) -> None:
        """After cooldown expires, entering location triggers new roll."""
        template = _make_template()
        encounters = {"forest": [EncounterEntry(template_id="goblin", chance=1.0, count_min=1, count_max=1)]}
        player = _make_player(location="tavern")
        layer = _make_layer(player, templates={"goblin": template}, encounters=encounters)

        player.location_id = "forest"

        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            time_first = GameDateTime(year=1490, month=6, day=1, hour=10)
            layer.update_activation(time_first)

        spawned_1 = [e for e in layer.get_active_creatures() if e.id != "player1"]
        assert len(spawned_1) == 1

        # Remove the spawned monster (it died), player leaves
        layer.remove_entity(spawned_1[0].id)
        player.location_id = "tavern"
        layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=11))

        # Come back after cooldown (10+ minutes later)
        player.location_id = "forest"

        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            time_after = GameDateTime(year=1490, month=6, day=1, hour=11, minute=15)
            layer.update_activation(time_after)

        spawned_2 = [e for e in layer.get_active_creatures() if e.id != "player1"]
        assert len(spawned_2) == 1


class TestGeneralizedEncounterTriggers:
    """Any active creature changing location triggers encounter rolls, not just PlayerCharacter."""

    def test_active_npc_triggers_encounters(self) -> None:
        """An active NPC moving to a location with encounters triggers spawn."""
        template = _make_template()
        encounters = {"forest": [EncounterEntry(template_id="goblin", chance=1.0, count_min=2, count_max=2)]}
        player = _make_player(location="tavern")
        # NPC guard starts at tavern, will move to forest
        guard = Creature(
            id="guard_1",
            name="Guard",
            location_id="tavern",
            max_hp=20,
            current_hp=20,
        )
        layer = EntitiesLayer(
            entities=[player, guard],
            monster_templates={"goblin": template},
            encounter_tables=encounters,
        )
        # Activate guard (player is at tavern = anchor, guard is at tavern too)
        layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10))
        assert guard.active is True

        # Guard moves to forest (dangerous location)
        guard.location_id = "forest"

        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 2
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10, minute=0, second=6))

        # Guard is now dormant (no player at forest), but encounters should have spawned
        spawned = [
            e for e in layer._entities.values() if isinstance(e, Creature) and e.temporary and e.location_id == "forest"
        ]
        assert len(spawned) == 2
        for c in spawned:
            assert c.location_id == "forest"
            assert c.max_hp == 7

    def test_dormant_creature_does_not_trigger_encounters(self) -> None:
        """A creature with active=False changing location does not trigger encounters."""
        template = _make_template()
        encounters = {"forest": [EncounterEntry(template_id="goblin", chance=1.0, count_min=1, count_max=1)]}
        player = _make_player(location="tavern")
        # Dormant creature at town — not near player anchor
        creature = Creature(
            id="wanderer",
            name="Wanderer",
            location_id="town",
            max_hp=10,
            current_hp=10,
        )
        creature.active = False
        layer = EntitiesLayer(
            entities=[player, creature],
            monster_templates={"goblin": template},
            encounter_tables=encounters,
        )

        # Wanderer moves to forest while dormant
        creature.location_id = "forest"

        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10))

        # No encounter spawned (dormant creature shouldn't trigger)
        spawned = [
            e for e in layer._entities.values() if isinstance(e, Creature) and e.temporary and e.location_id == "forest"
        ]
        assert len(spawned) == 0

    def test_cooldown_shared_between_player_and_npc(self) -> None:
        """Player triggers encounter at forest. NPC arrives within cooldown → no second roll."""
        template = _make_template()
        encounters = {"forest": [EncounterEntry(template_id="goblin", chance=1.0, count_min=1, count_max=1)]}
        player = _make_player(location="tavern")
        guard = Creature(
            id="guard_1",
            name="Guard",
            location_id="tavern",
            max_hp=20,
            current_hp=20,
        )
        layer = EntitiesLayer(
            entities=[player, guard],
            monster_templates={"goblin": template},
            encounter_tables=encounters,
        )

        # Player moves to forest → triggers encounter
        player.location_id = "forest"
        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10))

        spawned_count_1 = sum(1 for e in layer._entities.values() if isinstance(e, Creature) and e.temporary)
        assert spawned_count_1 == 1

        # Guard moves to forest within cooldown
        guard.location_id = "forest"
        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10, minute=1))

        # Still only 1 spawned (cooldown blocks second roll)
        spawned_count_2 = sum(1 for e in layer._entities.values() if isinstance(e, Creature) and e.temporary)
        assert spawned_count_2 == 1

    def test_temporary_spawn_does_not_self_trigger(self) -> None:
        """Spawned temporary creatures don't trigger encounter rolls at their own location."""
        template = _make_template()
        # Two locations with encounters
        encounters = {
            "forest": [EncounterEntry(template_id="goblin", chance=1.0, count_min=1, count_max=1)],
            "swamp": [EncounterEntry(template_id="goblin", chance=1.0, count_min=1, count_max=1)],
        }
        player = _make_player(location="tavern")
        layer = EntitiesLayer(
            entities=[player],
            monster_templates={"goblin": template},
            encounter_tables=encounters,
        )

        # Player enters forest → spawns 1 goblin
        player.location_id = "forest"
        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10))

        spawned = [e for e in layer._entities.values() if isinstance(e, Creature) and e.temporary]
        assert len(spawned) == 1
        goblin = spawned[0]

        # Move goblin to swamp (simulating movement). It's temporary — should NOT trigger encounters.
        goblin.location_id = "swamp"
        goblin.active = True

        with patch("dnd_simulator.layers.entities.activation_manager.random") as mock_rng:
            mock_rng.random.return_value = 0.0
            mock_rng.randint.return_value = 1
            layer.update_activation(GameDateTime(year=1490, month=6, day=1, hour=10, minute=0, second=6))

        # No new spawns at swamp — temporary creatures don't trigger encounters
        swamp_spawns = [
            e
            for e in layer._entities.values()
            if isinstance(e, Creature) and e.temporary and e.location_id == "swamp" and e.id != goblin.id
        ]
        assert len(swamp_spawns) == 0
