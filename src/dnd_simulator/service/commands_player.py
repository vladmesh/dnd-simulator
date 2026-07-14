"""Player lens: character creation, level-up, and status snapshot off the GameService facade.

Builds a PlayerCharacter from request data (point buy, derived HP/AC, starting gear),
applies pending level-ups, and renders the full status DTO consumed by ``routes_player``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from dnd_simulator.content_loader import load_catalog
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.service.base import GameServiceProtocol

if TYPE_CHECKING:
    from dnd_simulator.core.class_features import FightingStyle
    from dnd_simulator.service.dto import PlayerStatusData

logger = structlog.get_logger(domain="service.player")


class PlayerCommands(GameServiceProtocol):
    """Mixin: player character creation, leveling, and status (player lens)."""

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
        try:
            self.autosave_session(session_id)
        except Exception:
            logger.exception("create_player_autosave_failed", session_id=session_id)
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
        from dnd_simulator.service.errors import PlayerNotFoundError

        session = self._get_session(session_id)
        player = session.get_player()
        if player is None:
            raise PlayerNotFoundError("No player in this session")
        perform_level_up(player, fighting_style=fighting_style)
        return player

    def player_status(self, session_id: str, player_id: str | None = None) -> PlayerStatusData:
        """Return a player's full status snapshot.

        All derived fields (AC from equipment+modifiers, XP to next level) are
        already computed. When ``player_id`` is None, returns the first player
        in the session. Raises ValueError if no matching player exists.
        """
        from dnd_simulator.service.errors import PlayerNotFoundError
        from dnd_simulator.service.transport_payloads import build_player_status

        session = self._get_session(session_id)
        player = session.get_player(player_id) if player_id else session.get_player()
        if player is None:
            raise PlayerNotFoundError("No player in this session")
        return build_player_status(player, session.world.location_graph)
