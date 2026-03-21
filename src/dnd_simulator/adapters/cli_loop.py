"""CLI adapter using the Round orchestrator + PlayerBrain."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from dnd_simulator.content_loader import (
    extract_region_adjacency,
    extract_region_terrains,
    load_battle_maps,
    load_locations,
    load_nations,
    load_npcs,
    load_player,
    load_settlements,
    load_world,
)
from dnd_simulator.core.action import Action
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import Ability, Creature
from dnd_simulator.core.location import LocationGraph
from dnd_simulator.core.models import GameDateTime, Query, TimeDelta
from dnd_simulator.core.world import World
from dnd_simulator.i18n import _
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.llm.summarizer import MemorySummarizer
from dnd_simulator.round import Round

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"


def _quit_input(prompt: str) -> str:
    """Wrapper around input() that handles quit/EOF."""
    try:
        text = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\n" + _("Farewell, adventurer."))
        sys.exit(0)
    if text.strip().lower() == "quit":
        print(_("Farewell, adventurer."))
        sys.exit(0)
    return text


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_peaceful_awareness(creature: Creature, awareness: PeacefulAwareness, events: list[PerceivedEvent]) -> str:
    """Format peaceful awareness + events for CLI display."""
    lines = [
        "\n--- "
        + _("Your turn (HP: {hp}/{max_hp}, time: {hour}:00, day {day})").format(
            hp=creature.current_hp, max_hp=creature.max_hp, hour=f"{awareness.hour:02d}", day=awareness.day
        )
        + " ---"
    ]
    if events:
        lines.append("")
        lines.append(_("What happened:"))
        for ev in events:
            lines.append(f"  \u2022 {ev.description}")
    return "\n".join(lines)


def format_combat_awareness(creature: Creature, awareness: CombatAwareness, events: list[PerceivedEvent]) -> str:
    """Format combat awareness + events for CLI display."""
    lines = [
        "\n--- "
        + _("Combat, round {round} (HP: {hp}/{max_hp}, weapon: {weapon}, speed: {speed} ft)").format(
            round=awareness.round_number,
            hp=awareness.self_hp,
            max_hp=awareness.self_max_hp,
            weapon=awareness.self_weapon,
            speed=awareness.self_speed,
        )
        + " ---"
    ]
    if awareness.nearby:
        lines.append("\n" + _("Around:"))
        for e in awareness.nearby:
            if e.distance_ft and e.direction:
                lines.append(f"  {e.description} [{e.id}] \u2014 {e.distance_ft} ft {e.direction}")
            else:
                lines.append(f"  {e.description} [{e.id}]")
    if awareness.walls:
        lines.append("\n" + _("Walls:"))
        for w in awareness.walls:
            lines.append(f"  {w}")
    if events:
        lines.append("")
        lines.append(_("What happened:"))
        for ev in events:
            lines.append(f"  \u2022 {ev.description}")
    return "\n".join(lines)


def format_status(creature: Creature) -> str:
    """Format creature stats for CLI display."""
    scores = creature.ability_scores
    lines = [
        f"=== {creature.name} ===",
        _("HP: {hp}/{max_hp} | AC: {ac} | Gold: {gold}").format(
            hp=creature.current_hp, max_hp=creature.max_hp, ac=creature.ac, gold=getattr(creature, "gold", 0)
        ),
        f"STR {scores[Ability.STR]}  DEX {scores[Ability.DEX]}  CON {scores[Ability.CON]}"
        f"  INT {scores[Ability.INT]}  WIS {scores[Ability.WIS]}  CHA {scores[Ability.CHA]}",
    ]
    if creature.attacks:
        lines.append(_("Attacks:") + " " + ", ".join(a.name for a in creature.attacks))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI Turn Handler
# ---------------------------------------------------------------------------


class CliTurnHandler:
    """Turn handler for CLI: displays awareness, reads commands, submits Actions.

    Captures world reference for query commands (look) and meta-commands (wait).
    Used as the on_turn callback for PlayerBrain.
    """

    def __init__(
        self,
        world: World,
        brain: PlayerBrain,
        input_fn: Callable[[str], str] = _quit_input,
        output_fn: Callable[[str], object] = print,
    ) -> None:
        self._world = world
        self._brain = brain
        self._input_fn = input_fn
        self._output_fn = output_fn

    def __call__(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> None:
        if isinstance(awareness, CombatAwareness):
            action = self._combat_turn(creature, awareness, events)
        else:
            action = self._peaceful_turn(creature, awareness, events)
        self._brain.submit_action(action)

    def _peaceful_turn(
        self,
        creature: Creature,
        awareness: PeacefulAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        self._output_fn(format_peaceful_awareness(creature, awareness, events))

        while True:
            raw = self._input_fn("> ").strip()
            if not raw:
                continue
            cmd = raw.lower()

            # Informational commands — don't end turn
            if cmd == "look":
                self._cmd_look(creature)
                continue
            if cmd == "status":
                self._output_fn(format_status(creature))
                continue

            # Action commands — end turn
            if cmd == "idle":
                return Action(name="idle")

            if cmd == "wait" or cmd.startswith("wait "):
                return self._parse_wait(cmd)

            if cmd.startswith("say "):
                return Action(name="say", params={"text": raw[4:].strip()})

            if cmd.startswith("attack "):
                target_id = raw[7:].strip().split()[0] if raw[7:].strip() else ""
                if not target_id:
                    self._output_fn(_("Usage: attack <target>"))
                    continue
                return Action(name="attack", params={"target_id": target_id})

            self._output_fn(_("Commands: look, status, say <text>, attack <target>, wait [hours], idle"))

    def _combat_turn(
        self,
        creature: Creature,
        awareness: CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        self._output_fn(format_combat_awareness(creature, awareness, events))

        while True:
            raw = self._input_fn(_("combat> ")).strip()
            if not raw:
                continue
            cmd = raw.lower()

            if cmd == "status":
                self._output_fn(format_status(creature))
                continue

            if cmd == "idle":
                return Action(name="idle")

            if cmd == "dodge":
                return Action(name="dodge")

            if cmd == "flee":
                return Action(name="flee")

            if cmd.startswith("attack "):
                target_id = raw[7:].strip().split()[0] if raw[7:].strip() else ""
                if not target_id:
                    self._output_fn(_("Usage: attack <target>"))
                    continue
                return Action(name="attack", params={"target_id": target_id})

            if cmd.startswith("move ") or cmd.startswith("dash "):
                action = self._parse_move(raw, cmd)
                if action:
                    return action
                continue

            self._output_fn(
                _(
                    "Commands: attack <target>, move <direction> [target], "
                    "dash <direction> [target], dodge, flee, status, idle"
                )
            )

    def _parse_wait(self, cmd: str) -> Action:
        """Parse wait command, return Action."""
        parts = cmd.split()
        hours = 1
        if len(parts) > 1:
            try:
                hours = int(parts[1])
            except ValueError:
                self._output_fn(_("Usage: wait [hours]"))
                return Action(name="idle")
            if hours < 1:
                self._output_fn(_("Minimum 1 hour."))
                return Action(name="idle")
        return Action(name="wait", params={"hours": hours})

    def _parse_move(self, raw: str, cmd: str) -> Action | None:
        """Parse move/dash command. Returns Action or None if invalid."""
        is_dash = cmd.startswith("dash ")
        args = raw[5:].strip().split()
        if not args:
            self._output_fn(_("Usage: move/dash <toward|away|north|south|...> [target]"))
            return None
        params: dict[str, object] = {}
        keyword = args[0].lower()
        if keyword == "toward" and len(args) > 1:
            params["toward"] = args[1]
        elif keyword == "away" and len(args) > 1:
            params["away_from"] = args[1]
        else:
            params["direction"] = keyword
        return Action(name="dash" if is_dash else "move", params=params)

    def _cmd_look(self, creature: Creature) -> None:
        """Describe current location, entities, and paths."""
        world = self._world
        region_id = world.location_graph.region_of(creature.location_id)
        info = world.query_layer("geography", Query(question="region_info", params={"region_id": region_id}))
        weather = world.query_layer("geography", Query(question="weather", params={"region_id": region_id}))
        location = world.location_graph.get(creature.location_id)
        entities = world.query_layer(
            "entities", Query(question="entities_at_location", params={"location_id": creature.location_id})
        )

        lines = [f"=== {location.name} ==="]
        lines.append(
            _("Terrain:")
            + f" {info.value['terrain']}  |  "
            + _("Weather:")
            + f" {weather.value['condition'].replace('_', ' ')}, {weather.value['temperature']}\u00b0C"
        )

        others = [e for e in entities.value if e["id"] != creature.id]
        if others:
            lines.append("\n" + _("Creatures:"))
            for e in others:
                if "activity_flavor" in e:
                    lines.append(f"  {e['name']} [{e['id']}] \u2014 {e['activity_flavor']}")
                elif "role" in e:
                    lines.append(f"  {e['name']} [{e['id']}] ({e['role']}) \u2014 {e['activity']}")
                else:
                    lines.append(f"  {e['name']} [{e['id']}]")

        edges = location.edges
        if edges:
            lines.append("\n" + _("Paths:"))
            for edge in edges:
                target = world.location_graph.get(edge.target_id)
                dist_str = f"{edge.distance_m / 1000:.1f} km" if edge.distance_m >= 1000 else f"{edge.distance_m} m"
                lines.append(f"  {target.name} ({edge.target_id}) \u2014 {dist_str}")

        self._output_fn("\n".join(lines))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_cli_loop() -> None:
    """Start the game using the Round orchestrator + PlayerBrain."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    load_dotenv()

    # LLM setup
    llm: LlmClient | None = None
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("LLM_MODEL")
    if not api_key or not model:
        print(_("Error: set OPENROUTER_API_KEY and LLM_MODEL in .env"))
        sys.exit(1)
    llm = LlmClient(api_key=api_key, model=model)
    print(f"LLM: {model}")

    # Load world (accept filename from argv)
    world_file = sys.argv[1] if len(sys.argv) > 1 else "sword_vale"
    world_path = DEFAULT_CONTENT_DIR / "worlds" / world_file
    regions = load_world(world_path)
    nations = load_nations(world_path)
    settlements = load_settlements(world_path)
    player = load_player(world_path)
    npcs = load_npcs(world_path)
    battle_maps = load_battle_maps(world_path)

    # Inject LLM brain into NPCs that need it
    for npc in npcs:
        if npc.ai_type == "llm":
            npc.brain = LlmBrain(llm)

    # Build location graph
    locations = load_locations(world_path, regions)
    location_graph = LocationGraph(locations)

    # Fall back to first location
    if not player.location_id and locations:
        player.location_id = locations[0].id

    # Build layers
    region_terrains = extract_region_terrains(regions)
    geography = GeographyLayer(regions=regions)
    settlements_layer = SettlementsLayer(settlements=settlements, region_terrains=region_terrains)
    politics = PoliticsLayer(
        nations=nations,
        region_terrains=region_terrains,
        region_adjacency=extract_region_adjacency(regions),
        region_income_fn=settlements_layer.get_region_income,
    )
    summarizer = MemorySummarizer(llm) if llm else None
    entities_layer = EntitiesLayer(entities=[*npcs, player], battle_map_configs=battle_maps, summarizer=summarizer)

    world = World(
        layers=[geography, politics, settlements_layer, entities_layer],
        time=GameDateTime(year=1490, month=6, day=1, hour=10),
        location_graph=location_graph,
    )

    # Initial tick
    world.advance_time(TimeDelta(seconds=0))

    # Wire PlayerBrain with CLI handler
    brain = PlayerBrain()
    handler = CliTurnHandler(world, brain)
    brain.set_on_turn(handler)
    player.brain = brain

    print(_("=== D&D Simulator (Turn-Based) ==="))
    print(_("Commands: look, status, say <text>, attack <target>, idle, quit"))

    game_round = Round(world, entities_layer)
    game_round.run_loop()


if __name__ == "__main__":
    run_cli_loop()
