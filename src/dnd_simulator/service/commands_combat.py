from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.service.session import GameSession, MasterResponse

if TYPE_CHECKING:
    from dnd_simulator.core.player import PlayerCharacter


class CombatCommands:
    """Mixin: combat-related commands and queries."""

    def _require_player(self, session: GameSession) -> PlayerCharacter:
        raise NotImplementedError

    def _cmd_attack(self, session: GameSession, target_id: str) -> MasterResponse:
        """Attack a target entity."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        if not target_id:
            return MasterResponse(text="Usage: attack <target_id>")

        result = session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": player.id, "target_id": target_id},
            )
        )
        if not result.success:
            return MasterResponse(text=result.error)

        descriptions = [e.description for e in result.events if e.description]
        return MasterResponse(text="\n".join(descriptions) if descriptions else "Attack!", events_summary=descriptions)

    def _cmd_say(self, session: GameSession, text: str) -> MasterResponse:
        """Say something in the current location."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data={"entity_id": player.id, "text": text},
            )
        )
        return MasterResponse(text=f'{player.name} says: "{text}"')

    def _cmd_dodge(self, session: GameSession) -> MasterResponse:
        """Take the dodge action."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_DODGE,
                source_layer="entities",
                data={"entity_id": player.id},
            )
        )
        return MasterResponse(text=f"{player.name} takes the Dodge action.")

    def _cmd_move(self, session: GameSession, text: str, dash: bool = False) -> MasterResponse:
        """Move or dash in combat."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        args = text[5:].strip().split()
        if not args:
            return MasterResponse(text="Usage: move/dash <toward|away|north|south|...> [target]")

        event_data: dict[str, object] = {"entity_id": player.id}
        keyword = args[0].lower()
        if keyword == "toward" and len(args) > 1:
            event_data["toward"] = args[1]
        elif keyword == "away" and len(args) > 1:
            event_data["away_from"] = args[1]
        else:
            event_data["direction"] = keyword

        result = session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_DASH if dash else EventType.ENTITY_MOVE,
                source_layer="entities",
                data=event_data,
            )
        )
        if not result.success:
            return MasterResponse(text=result.error)
        descriptions = [e.description for e in result.events if e.description]
        return MasterResponse(text="\n".join(descriptions) if descriptions else "Moved.")

    def _cmd_flee(self, session: GameSession) -> MasterResponse:
        """Attempt to flee combat."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        result = session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_FLEE,
                source_layer="entities",
                data={"entity_id": player.id},
            )
        )
        if not result.success:
            return MasterResponse(text=result.error)
        descriptions = [e.description for e in result.events if e.description]
        return MasterResponse(text="\n".join(descriptions) if descriptions else "You flee!")

    def get_combat_state(self, session_id: str) -> dict[str, Any] | None:
        """Get combat state from the player's perspective. Returns None if not in combat."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        player = self._require_player(session)

        if not player.in_combat:
            return None

        return player._build_combat_awareness(session.world)
