from __future__ import annotations

import contextlib
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dnd_simulator.core.class_features import FightingStyle
    from dnd_simulator.service.dto import PlayerStatusData

import structlog

from dnd_simulator.content_loader import (
    LayerType,
    extract_region_adjacency,
    extract_region_terrains,
    load_battle_maps,
    load_catalog,
    load_factions,
    load_lairs,
    load_location_battle_maps,
    load_locations,
    load_monsters,
    load_nations,
    load_npcs,
    load_settlements,
    load_squads,
    load_world,
    load_world_meta_from_manifest,
    resolve_manifest,
)
from dnd_simulator.core.brain import BrainType
from dnd_simulator.core.character import Entity
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import GameDateTime, TimeDelta
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.rules.modifiers import effective_ac
from dnd_simulator.storage.store import SaveStore

from .brain_factory import BrainFactory
from .commands_creatures import CreatureCommands
from .commands_politics import PoliticsCommands
from .commands_save import SaveCommands
from .commands_time import TimeCommands
from .commands_world_state import WorldStateCommands
from .commands_worldbuilder import WorldBuilderCommands
from .session import GameSession

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"

logger = structlog.get_logger(domain="service")


def _flatten_region_defaults[T](
    locations: list[Location],
    by_region: dict[str, T],
    by_location: dict[str, T],
) -> dict[str, T]:
    """Collapse region-level defaults and per-location overrides into a flat per-location map.

    A region entry applies to every location in that region (default); a
    per-location entry overrides it (no merge). Battle maps and encounter tables
    both resolve region → location this way at load time, so the runtime only
    ever sees per-location data.
    """
    resolved: dict[str, T] = {}
    for loc in locations:
        if loc.region_id in by_region:
            resolved[loc.id] = by_region[loc.region_id]
        if loc.id in by_location:
            resolved[loc.id] = by_location[loc.id]
    return resolved


class GameService(
    CreatureCommands,
    PoliticsCommands,
    SaveCommands,
    TimeCommands,
    WorldBuilderCommands,
    WorldStateCommands,
):
    """Session management, world templates, hot controls. No turn execution."""

    def __init__(
        self,
        store: SaveStore,
        content_dir: Path = DEFAULT_CONTENT_DIR,
        llm: LlmClient | None = None,
    ) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._store = store
        self._content_dir = content_dir
        self._llm = llm
        self._brain_factory = BrainFactory(llm=llm)

    def start_game(self, world_name: str = "sword_vale", lang: str = "en") -> GameSession:
        """Create a new game session with a world loaded from content/worlds/<world_name>/."""
        session_id = uuid.uuid4().hex[:8]
        structlog.contextvars.bind_contextvars(session_id=session_id)

        self._validate_world_id(world_name)
        world_path = self._content_dir / "worlds" / world_name
        layer_paths = resolve_manifest(world_path, self._content_dir)
        missing = {lt.value for lt in LayerType} - set(layer_paths)
        if missing:
            raise RuntimeError(
                f"World '{world_name}' is incomplete — missing layers: {', '.join(sorted(missing))}. "
                "All 5 layers must be defined before starting a session."
            )
        meta = load_world_meta_from_manifest(world_path, lang=lang)
        regions = load_world(layer_paths["geography"], lang=lang)
        nations = load_nations(layer_paths["politics"], lang=lang)
        settlements = load_settlements(layer_paths["settlements"], lang=lang)
        locations = load_locations(layer_paths["geography"], regions, lang=lang)
        location_graph = LocationGraph(locations)
        from dnd_simulator.content_loader.schemas import ItemContent, MonsterTemplateContent

        item_catalog_dir = self._content_dir / "catalogs" / "items"
        item_catalog = load_catalog(item_catalog_dir, ItemContent) if item_catalog_dir.exists() else {}
        npcs = load_npcs(
            layer_paths["entities"],
            lang=lang,
            known_locations=set(location_graph.all_ids()),
            item_catalog=item_catalog,
        )

        catalog_dir = self._content_dir / "catalogs" / "monsters"
        monster_catalog = load_catalog(catalog_dir, MonsterTemplateContent) if catalog_dir.exists() else {}
        monster_templates, encounter_tables, region_encounter_tables = load_monsters(
            layer_paths["ecology"], lang=lang, catalog=monster_catalog, known_regions={r.id for r in regions}
        )
        faction_data = load_factions(layer_paths["politics"], lang=lang)
        squads = load_squads(layer_paths["ecology"], lang=lang)
        lairs = load_lairs(
            layer_paths["ecology"], known_templates=set(monster_templates), lang=lang, item_catalog=item_catalog
        )
        region_terrains = extract_region_terrains(regions)

        # Players are created via API (create_player), not from templates
        entities: list[Entity] = [*npcs]

        geography = GeographyLayer(regions=regions, location_graph=location_graph)
        settlements_layer = SettlementsLayer(settlements=settlements, region_terrains=region_terrains)
        politics = PoliticsLayer(
            nations=nations,
            region_terrains=region_terrains,
            region_adjacency=extract_region_adjacency(regions),
            region_income_fn=settlements_layer.get_region_income,
            faction_relations=faction_data.relations,
            faction_names=faction_data.names,
        )
        summarizer = None
        if self._llm:
            from dnd_simulator.llm.summarizer import MemorySummarizer

            summarizer = MemorySummarizer(self._llm)
        # Resolve member CRs from monster templates for abstract combat
        for squad in squads.values():
            squad.member_crs = [monster_templates[tid].cr for tid in squad.member_templates]
        ecology_layer = EcologyLayer(
            squads=list(squads.values()), location_graph=location_graph, lairs=list(lairs.values())
        )
        # Battle maps and encounter tables both resolve region → location at load
        # time: a region-level declaration is the default for every location in
        # that region, a per-location declaration overrides it. The runtime sees
        # only the flat per-location maps.
        battle_map_configs = _flatten_region_defaults(
            locations,
            load_battle_maps(layer_paths["geography"]),
            load_location_battle_maps(layer_paths["geography"]),
        )
        effective_encounters = _flatten_region_defaults(locations, region_encounter_tables, encounter_tables)

        entities_layer = EntitiesLayer(
            entities=entities,
            summarizer=summarizer,
            monster_templates=monster_templates,
            encounter_tables=effective_encounters,
            battle_map_configs=battle_map_configs,
        )

        # Assign brains via factory (content_loader only parses data, not brains)
        self._assign_brains(entities_layer)

        world = World(
            layers=[geography, politics, settlements_layer, ecology_layer, entities_layer],
            time=GameDateTime(year=1490, month=6, day=1, hour=10),
            location_graph=location_graph,
        )

        # Initial tick to set weather/temperature
        world.advance_time(TimeDelta(seconds=0))

        session = GameSession(
            session_id=session_id,
            world=world,
            lang=lang,
            world_name=world_name,
            default_player_faction=meta.get("default_player_faction", ""),
        )
        session._on_empty = self._on_session_empty
        self._sessions[session_id] = session
        return session

    def list_sessions(self) -> list[dict[str, str]]:
        """List all active sessions (in-memory + saved on disk)."""
        result: dict[str, dict[str, str]] = {}

        # In-memory sessions
        for sid, s in self._sessions.items():
            players = s.get_players()
            player_name = players[0].name if players else ""
            result[sid] = {"session_id": sid, "player_name": player_name, "world_name": s.world_name}

        # Saved sessions on disk (not yet loaded) — scan all world subdirs
        from dnd_simulator.storage.store import JsonFileStore

        if isinstance(self._store, JsonFileStore):
            for world_name in self._store.list_worlds():
                for save_name in self._store.list_saves(world=world_name):
                    if save_name.startswith("session_"):
                        sid = save_name[len("session_") :]
                        if sid not in result:
                            result[sid] = {"session_id": sid, "player_name": "(saved)", "world_name": world_name}

        return list(result.values())

    def get_session(self, session_id: str) -> GameSession:
        """Get session info."""
        return self._get_session(session_id)

    def delete_session(self, session_id: str) -> None:
        """Stop and remove a session."""
        self._get_session(session_id)
        del self._sessions[session_id]

    def _on_session_empty(self, session: GameSession) -> None:
        """Called when all listeners disconnect. Autosave and evict from memory."""
        sid = session.session_id
        logger.info("session_empty_evict", session_id=sid)
        with contextlib.suppress(Exception):
            self.autosave_session(sid)
        self._sessions.pop(sid, None)

    # -- Layer accessors --

    def _get_entities_layer(self, session: GameSession) -> EntitiesLayer:
        for layer in session.world.layers:
            if isinstance(layer, EntitiesLayer):
                return layer
        raise RuntimeError("EntitiesLayer not found")

    def _get_politics_layer(self, session: GameSession) -> PoliticsLayer:
        for layer in session.world.layers:
            if isinstance(layer, PoliticsLayer):
                return layer
        raise RuntimeError("PoliticsLayer not found")

    def _get_settlements_layer(self, session: GameSession) -> SettlementsLayer:
        for layer in session.world.layers:
            if isinstance(layer, SettlementsLayer):
                return layer
        raise RuntimeError("SettlementsLayer not found")

    def _assign_brains(self, entities_layer: EntitiesLayer) -> None:
        """Assign brains to all creatures via BrainFactory based on ai_type.

        Called after world creation and after every load to ensure brains
        match the (possibly restored) ai_type field.
        """
        from dnd_simulator.core.character import Creature
        from dnd_simulator.layers.entities.models import Npc

        for entity in entities_layer._entities.values():
            if isinstance(entity, Npc):
                entity.brain = self._brain_factory.create(entity.ai_type)
            elif isinstance(entity, Creature) and entity.brain is None:
                entity.brain = self._brain_factory.create(BrainType.RULE_BASED)

    # -- Player --

    def create_player(self, session_id: str, player_data: dict[str, Any]) -> PlayerCharacter:
        """Create a new player character in a session.

        Validates point buy, computes HP/AC/gold, loads starting equipment.
        Returns the created PlayerCharacter (with a unique id like ``player_<hex>``).
        """
        from dnd_simulator.content_loader import parse_player
        from dnd_simulator.content_loader.schemas import ItemContent
        from dnd_simulator.core.character import Ability, CharClass
        from dnd_simulator.core.class_features import FightingStyle
        from dnd_simulator.rules.character_creation import (
            STARTING_GOLD,
            calculate_max_hp,
            starting_equipment,
            validate_point_buy,
        )
        from dnd_simulator.rules.modifiers import effective_ac

        session = self._get_session(session_id)

        # --- Validate class ---
        char_class_raw = player_data.get("class", "fighter")
        try:
            char_class = CharClass(char_class_raw)
        except ValueError as e:
            raise ValueError(f"Unknown class: {char_class_raw}") from e
        supported_classes = {CharClass.FIGHTER, CharClass.ROGUE, CharClass.PALADIN}
        if char_class not in supported_classes:
            raise ValueError(f"Class '{char_class_raw}' is not supported. Choose from: fighter, rogue, paladin")

        # --- Validate ability scores ---
        raw_scores = player_data.get("ability_scores", {})
        try:
            scores = {Ability(k): int(v) for k, v in raw_scores.items()}
        except (ValueError, KeyError) as e:
            raise ValueError(f"Invalid ability scores: {e}") from e
        validate_point_buy(scores)

        # --- Validate fighting style ---
        fighting_style_raw = player_data.get("fighting_style")
        if fighting_style_raw is not None:
            if char_class not in {CharClass.FIGHTER, CharClass.PALADIN}:
                raise ValueError("Fighting style is only available for fighters and paladins")
            try:
                FightingStyle(fighting_style_raw)
            except ValueError as e:
                raise ValueError(
                    f"Invalid fighting style: '{fighting_style_raw}'. "
                    f"Choose from: {', '.join(s.value for s in FightingStyle)}"
                ) from e

        # --- Compute derived stats ---
        con_modifier = (scores[Ability.CON] - 10) // 2
        max_hp = calculate_max_hp(char_class, level=1, con_modifier=con_modifier)

        # --- Load starting equipment from item catalog ---
        item_catalog_dir = self._content_dir / "catalogs" / "items"
        item_catalog = load_catalog(item_catalog_dir, ItemContent) if item_catalog_dir.exists() else {}

        fs = FightingStyle(fighting_style_raw) if fighting_style_raw else None
        equip_refs = starting_equipment(char_class, fs)
        items_data = [{"ref": ref, "equipped": True} for ref in equip_refs]

        # --- Build player dict for parse_player ---
        class_features: dict[str, object] = {}
        if fighting_style_raw:
            class_features["fighting_style"] = fighting_style_raw

        parse_data: dict[str, Any] = {
            "name": player_data.get("name", "Adventurer"),
            "race": player_data.get("race", "human"),
            "class": char_class_raw,
            "level": 1,
            "alignment": player_data.get("alignment", "true_neutral"),
            "appearance": player_data.get("appearance", ""),
            "start_location": player_data.get("start_location", ""),
            "hp": max_hp,
            "ac": 10,  # placeholder — effective_ac computed after construction
            "gold": STARTING_GOLD,
            "ability_scores": raw_scores,
            "items": items_data,
        }
        if class_features:
            parse_data["class_features"] = class_features
        if "combat_position" in player_data:
            parse_data["combat_position"] = player_data["combat_position"]

        player = parse_player(parse_data, item_catalog=item_catalog)

        # --- Set correct AC from equipment + modifiers ---
        player.ac = effective_ac(player)

        # Default faction from world config if not specified by player
        if not player.faction_id and session.default_player_faction:
            player.faction_id = session.default_player_faction

        # Default to first location if not specified
        if not player.location_id:
            graph = session.world.location_graph
            ids = graph.all_ids()
            if ids:
                player.location_id = ids[0]

        self._get_entities_layer(session).add_entity(player)
        with contextlib.suppress(Exception):
            self.autosave_session(session_id)
        return player

    def level_up_player(
        self,
        session_id: str,
        fighting_style: FightingStyle | None,
    ) -> PlayerCharacter:
        """Apply a pending level-up to the session's player character.

        Mutates the PlayerCharacter in place and returns the same instance.
        Raises ValueError if there is no player, no pending level-up, or the
        fighting_style argument is incompatible with the class/level transition.
        """
        from dnd_simulator.rules.perform_level_up import perform_level_up

        session = self._get_session(session_id)
        player = session.get_player()
        if player is None:
            raise ValueError("No player in this session")
        perform_level_up(player, fighting_style=fighting_style)
        return player

    def player_status(self, session_id: str, player_id: str | None = None) -> PlayerStatusData:
        """Return a player's full status snapshot.

        All derived fields (AC from equipment+modifiers, XP to next level) are
        already computed. When ``player_id`` is None, returns the first player
        in the session. Raises ValueError if no matching player exists.
        """
        from dnd_simulator.core.character import Ability
        from dnd_simulator.rules.leveling import xp_to_next_level
        from dnd_simulator.service.dto import PlayerStatusData, ResourcePoolView
        from dnd_simulator.service.session import build_equipped_payload, build_inventory_payload

        session = self._get_session(session_id)
        player = session.get_player(player_id) if player_id else session.get_player()
        if player is None:
            raise ValueError("No player in this session")
        scores = player.ability_scores
        return PlayerStatusData(
            player_id=player.id,
            name=player.name,
            race=player.race.value,
            char_class=player.char_class.value,
            level=player.level,
            experience=player.experience,
            level_up_available=player.level_up_available,
            xp_to_next_level=xp_to_next_level(player.experience),
            alignment=player.alignment.value,
            hp=player.current_hp,
            max_hp=player.max_hp,
            ac=effective_ac(player),
            gold=player.gold,
            location_id=player.location_id,
            appearance=player.appearance,
            ability_scores={
                "str": scores[Ability.STR],
                "dex": scores[Ability.DEX],
                "con": scores[Ability.CON],
                "int": scores[Ability.INT],
                "wis": scores[Ability.WIS],
                "cha": scores[Ability.CHA],
            },
            resource_pools=[
                ResourcePoolView(id=p.id, max_uses=p.max_uses, current_uses=p.current_uses)
                for p in player.resource_pools
            ],
            equipped=build_equipped_payload(player),
            inventory=build_inventory_payload(player),
        )

    def _get_session(self, session_id: str) -> GameSession:
        if session_id not in self._sessions:
            # Try to restore from autosave on disk
            self._try_restore_session(session_id)
        if session_id not in self._sessions:
            raise ValueError(f"Session '{session_id}' not found")
        structlog.contextvars.bind_contextvars(session_id=session_id)
        return self._sessions[session_id]

    def _try_restore_session(self, session_id: str) -> None:
        """Attempt to restore a session from its autosave file."""
        save_name = f"session_{session_id}"

        # Search across all world subdirectories
        data: dict[str, object] | None = None
        from dnd_simulator.storage.store import JsonFileStore

        if isinstance(self._store, JsonFileStore):
            for world_name in self._store.list_worlds():
                try:
                    data = self._store.load(save_name, world=world_name)
                    break
                except KeyError:
                    continue

        # Fallback: try root directory (backward compat)
        if data is None:
            try:
                data = self._store.load(save_name)
            except KeyError:
                return

        meta = data.get("meta", {})
        assert isinstance(meta, dict)
        world_name = str(meta.get("world_name", ""))
        lang = str(meta.get("lang", "en"))

        if not world_name:
            return

        # Recreate session from the same world template, then load saved state
        try:
            session = self.start_game(world_name, lang=lang)
        except Exception:
            return

        # Reassign to the original session_id
        del self._sessions[session.session_id]
        session.session_id = session_id

        # Load saved world state (player state is restored as part of entities layer)
        if "world" in data:
            world_data = data["world"]
            assert isinstance(world_data, dict)
            session.world.load(world_data)

            # Reassign brains based on restored ai_type (may differ from template)
            self._assign_brains(self._get_entities_layer(session))

            # Backward compat: old saves have separate "player" block
            player_data = data.get("player", {})
            assert isinstance(player_data, dict)
            if player_data:
                player = session.get_player()
                if player:
                    player.load_save_data(player_data)
                else:
                    # Player was created after session start — recreate
                    from dnd_simulator.content_loader import parse_player

                    new_player = parse_player(player_data)
                    self._get_entities_layer(session).add_entity(new_player)

        self._sessions[session_id] = session
