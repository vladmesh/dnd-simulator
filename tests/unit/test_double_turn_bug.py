"""Investigation: NPC gets more turns per round than expected.

Reproduces the bug from docs/bug_double_attack.md:
  - 1v1 Goblin vs Hero, 3 attack+end_turn cycles
  - Goblin should attack at most 3 times, but actually attacks more
"""

from __future__ import annotations

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Ability, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.round import Round
from dnd_simulator.rules.rule_brain import RuleBrain
from dnd_simulator.service.action_dispatcher import ActionDispatcher

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_world(entities: list[Creature]) -> tuple[World, EntitiesLayer]:
    region = Region(
        id="r1",
        name="Field",
        terrain=TerrainType.PLAINS,
        latitude=45.0,
        longitude=0.0,
        elevation=100,
        water_proximity=0.0,
        connections=[],
    )
    geography = GeographyLayer(regions=[region])
    settlements = SettlementsLayer(settlements=[], region_terrains={"r1": TerrainType.PLAINS})
    politics = PoliticsLayer(
        nations=[],
        region_terrains={"r1": TerrainType.PLAINS},
        region_adjacency={},
        region_income_fn=settlements.get_region_income,
    )
    entities_layer = EntitiesLayer(entities=list(entities))
    world = World(
        layers=[geography, politics, settlements, entities_layer],
        time=GameDateTime(year=1, month=1, day=1, hour=10),
        location_graph=LocationGraph([Location(id="r1", name="Field", region_id="r1")]),
    )
    return world, entities_layer


CLUB = Attack(
    name="club",
    ability=Ability.STR,
    damage=(DamageComponent(dice="1d4", type=DamageType.BLUDGEONING),),
    reach=5,
)

SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent(dice="1d8", type=DamageType.SLASHING),),
    reach=5,
)


class ScriptedBrain(Brain):
    """Brain that plays a scripted sequence of actions, then END_TURN forever."""

    def __init__(self, actions: list[Action]) -> None:
        self._actions = list(actions)
        self._index = 0
        self.call_log: list[str] = []

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        if self._index >= len(self._actions):
            self.call_log.append("end_turn(auto)")
            return END_TURN
        action = self._actions[self._index]
        self._index += 1
        self.call_log.append(action.name)
        return action


class TrackingRuleBrain(RuleBrain):
    """RuleBrain that logs every choose_action call."""

    def __init__(self) -> None:
        super().__init__()
        self.call_log: list[str] = []

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        action = super().choose_action(creature, awareness, events)
        self.call_log.append(action.name)
        return action


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTurnCountPerRound:
    """Each creature must get exactly one turn per run_round() call."""

    def _make_1v1(self) -> tuple[Round, EntitiesLayer, PlayerCharacter, Creature, ScriptedBrain, TrackingRuleBrain]:
        """Create Hero vs Goblin, both high HP so nobody dies."""
        player_brain = ScriptedBrain([])  # will be replaced per-round
        player = PlayerCharacter(
            id="player",
            name="Hero",
            location_id="r1",
            max_hp=200,
            current_hp=200,
            ac=18,
            attacks=(SWORD,),
            brain=player_brain,
        )

        goblin_brain = TrackingRuleBrain()
        goblin = Creature(
            id="goblin",
            name="Goblin",
            location_id="r1",
            max_hp=200,
            current_hp=200,
            ac=13,
            speed=30,
            attacks=(CLUB,),
            brain=goblin_brain,
        )

        world, el = _make_world([player, goblin])
        game_round = Round(world, el)
        return game_round, el, player, goblin, player_brain, goblin_brain

    def test_detailed_budget_trace(self) -> None:
        """Trace every brain call with budget state to find the extra attack."""
        game_round, el, player, goblin, _, _ = self._make_1v1()

        # Start combat
        el._combat.start_combat("r1")

        budget_trace: list[dict[str, object]] = []

        class TracingBrain(RuleBrain):
            def choose_action(self, creature, awareness, events):  # type: ignore[override]
                budget = awareness.turn_budget
                action = super().choose_action(creature, awareness, events)
                budget_trace.append(
                    {
                        "creature": creature.name,
                        "action": action.name,
                        "budget_before": (
                            f"a={budget.actions},b={budget.bonus_actions},m={budget.movement_remaining}"
                            if budget
                            else "None"
                        ),
                    }
                )
                return action

        goblin.brain = TracingBrain()

        # Player: attack + end_turn
        player.brain = ScriptedBrain(
            [
                Action(name=ActionType.ATTACK, params={"target_id": "goblin"}),
                END_TURN,
            ]
        )

        # Also trace run_creature_turn
        turn_log: list[str] = []
        original_run = game_round.run_creature_turn

        def tracking_run(creature, *args, **kwargs):  # type: ignore[no-untyped-def]
            turn_log.append(creature.id)
            return original_run(creature, *args, **kwargs)

        game_round.run_creature_turn = tracking_run  # type: ignore[assignment]

        # Patch dispatcher.dispatch to track actual executions
        executed_actions: list[tuple[str, str]] = []
        original_dispatch = ActionDispatcher.dispatch

        def tracking_dispatch(self_disp, actor, action, ctx, emit_fn):  # type: ignore[no-untyped-def]
            executed_actions.append((actor.name, action.name))
            return original_dispatch(self_disp, actor, action, ctx, emit_fn)

        ActionDispatcher.dispatch = tracking_dispatch  # type: ignore[assignment]

        try:
            game_round.run_round()
        finally:
            ActionDispatcher.dispatch = original_dispatch  # type: ignore[assignment]

        print("\n=== Budget trace ===")
        for entry in budget_trace:
            print(f"  {entry}")
        print(f"\n=== Turn log: {turn_log}")
        print("\n=== Executed actions ===")
        for name, action in executed_actions:
            print(f"  {name} → {action}")

        # Count EXECUTED goblin attacks (not brain proposals)
        goblin_executed_attacks = sum(1 for n, a in executed_actions if n == "Goblin" and a == ActionType.ATTACK)
        print(f"\nGoblin executed attacks: {goblin_executed_attacks}")

        assert turn_log.count("goblin") == 1, f"Goblin got {turn_log.count('goblin')} turns"
        assert goblin_executed_attacks <= 1, f"Goblin executed {goblin_executed_attacks} attacks in 1 turn"

    def test_full_ws_scenario_3_cycles(self) -> None:
        """Replicate the exact WS scenario: 3 cycles of attack+end_turn.

        Track both brain calls and actual execute_action calls.
        """
        game_round, _el, player, _goblin, _, _ = self._make_1v1()

        total_turn_log: list[tuple[int, str]] = []
        executed_actions: list[tuple[int, str, str]] = []
        round_num = 0

        original_run = game_round.run_creature_turn

        def tracking_run(creature, *args, **kwargs):  # type: ignore[no-untyped-def]
            total_turn_log.append((round_num, creature.id))
            return original_run(creature, *args, **kwargs)

        game_round.run_creature_turn = tracking_run  # type: ignore[assignment]

        original_dispatch = ActionDispatcher.dispatch

        def tracking_dispatch(self_disp, actor, action, ctx, emit_fn):  # type: ignore[no-untyped-def]
            executed_actions.append((round_num, actor.name, action.name))
            return original_dispatch(self_disp, actor, action, ctx, emit_fn)

        ActionDispatcher.dispatch = tracking_dispatch  # type: ignore[assignment]

        try:
            for i in range(3):
                round_num = i + 1
                player.brain = ScriptedBrain(
                    [
                        Action(name=ActionType.ATTACK, params={"target_id": "goblin"}),
                        END_TURN,
                    ]
                )
                game_round.run_round()
        finally:
            ActionDispatcher.dispatch = original_dispatch  # type: ignore[assignment]

        print("\n=== Turn log ===")
        for rn, cid in total_turn_log:
            print(f"  Round {rn}: {cid}")

        print("\n=== Executed actions ===")
        for rn, name, action in executed_actions:
            print(f"  Round {rn}: {name} → {action}")

        goblin_total_attacks = sum(1 for _, n, a in executed_actions if n == "Goblin" and a == ActionType.ATTACK)
        player_total_attacks = sum(1 for _, n, a in executed_actions if n == "Hero" and a == ActionType.ATTACK)
        print(f"\nPlayer executed attacks: {player_total_attacks}")
        print(f"Goblin executed attacks: {goblin_total_attacks}")

        # Goblin should execute at most 3 attacks across 3 rounds
        assert goblin_total_attacks <= 3, f"Goblin executed {goblin_total_attacks} attacks in 3 rounds"

        # Each round: at most 1 turn per creature
        for rn in range(1, 4):
            round_turns = [cid for r, cid in total_turn_log if r == rn]
            assert round_turns.count("goblin") <= 1, (
                f"Round {rn}: Goblin got {round_turns.count('goblin')} turns: {round_turns}"
            )
            assert round_turns.count("player") <= 1, (
                f"Round {rn}: Player got {round_turns.count('player')} turns: {round_turns}"
            )
