"""Foundation of the simulation engine.

Defines the core abstractions that everything else builds on:
- GameDateTime (second precision), TimeDelta (seconds-based, with round/hour/day factories)
- Event, Query, Answer, ActionResult, QueryFn, EmitFn — communication protocol between layers
- Layer — abstract base class; tick/handle_event receive query_fn + emit_fn for layer isolation
- World — container that holds layers, manages per-layer tick scheduling, enforces layer ordering via query_fn/emit_fn
- Entity → Creature (in_combat, brain, conditions, weapon) → Character with activation, ability scores, perception
- Action (name + params), END_TURN, SKIP — transport-agnostic creature actions
- TurnBudget, ActionCost — per-turn resource tracking (actions, bonus actions, movement, reaction)
- Condition enum, ConditionsMap — D&D 5e status effects (rounds-based or permanent)
- Item, WeaponDef, ArmorDef, ShieldDef, ItemType — equipment and consumables
- WeaponCategory, ArmorCategory — weapon/armor classification
- Modifier, ModifierOp, StatType, AttackModifiers — modifier pipeline data types for derived stat computation
- ClassFeatures, FighterFeatures, RogueFeatures — composition-based class mechanics (no logic, pure data)
- ResourcePool, RestType — trackable per-creature resources (Second Wind, spell slots)
- ActionDef, CostOverride, CostType, CombatMode — centralized action metadata registry
- Brain ABC, RuleBrain, PlayerBrain — strategy pattern for creature decision-making
- CombatState — tracks initiative order, round number, and auto-exit counter per location
- BattleMap, Position, Wall — 2D combat grid with entity positions, wall collision, random placement
- Location, LocationEdge, LocationGraph — flat navigation graph mapping locations to regions/settlements
- PeacefulAwareness, CombatAwareness, PerceivedEvent — structured awareness data passed to Brain.choose_action

This module has no external dependencies (except i18n for translatable strings).
All other modules depend on it.
"""
