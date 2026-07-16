"""Pure functions for game mechanics and world formulas.

Stateless calculations that can be used by any layer or the service:
- dice: atomic dice rolling (roll("2d6+3"), roll_d20 with advantage/disadvantage)
- checks: D&D 5e check mechanics (attack_roll, ability_check, saving_throw, damage_roll)
- combat: attack resolution (resolve_attack → AttackResult), initiative rolls (roll_initiative)
- actions: action cost rules (action_cost → ActionCost), per-creature budget defaults
- validation: precondition checks (alive, active, budget, movement left, target, scope, reach) → ValidationError or None
- action_params: typed access to Action params at the domain boundary
- handlers/: per-action-type execution split by domain (combat, movement, equipment, items, trade, loot, reactions,
  rest, triggers, action_surge). Movement handlers own the movement budget: the dispatcher treats move actions as
  FREE and the handler charges the distance actually covered
- action_provider: dynamic available-action sources (base, inventory, equipment, weapon, class feature, trigger)
  per creature+context
- abstract_combat: squad-vs-squad abstract combat formulas
- conditions: condition effects (is_incapacitated, effective_speed, attack_advantage, tick_conditions)
- modifiers: centralized derived stat pipeline (collect modifiers, compute effective AC/speed/attack, resolve advantage)
- weapons: get_weapon_attack — builds Attack from equipped weapon or fallback
- proficiency: proficiency bonus by level, weapon/armor proficiency per class
- sneak_attack: Rogue sneak attack eligibility and dice count (pure functions)
- divine_smite: Paladin smite eligibility and extra damage by slot level
- fighting_style: FightingStyle → self modifiers and attack contribution (shared by Fighter/Paladin)
- resources: resource pool management (has_resource, use_resource, reset)
- character_creation: point buy validation, HP formula (max hit die + CON mod), starting equipment by class
- leveling: XP-by-CR table, PHB thresholds, can_level_up
- perform_level_up: applies class-specific level deltas (stateful; mutates the Character in place)
- reactions: OA trigger detection (find_oa_triggers)
- reputation: effective_relation (personal rep → thresholds → faction fallback), kill reputation drop
- combat_sides: build_combat_sides with relation callback, forced_opponents for attack-initiated combat
- encounters: is_active_at_time — time-of-day gate for spawn rolls (DAY/NIGHT tag vs current phase)
- inventory: transfer_items — the single primitive that moves items and gold between holders (shared by trade and loot)
- trade: buy/sell validation and execution over the transfer primitive
- loot: is_lootable — pure predicate (dead creature or open container)
- lairs: should_deplete — depletion roll for a lair with no core/boss
- movement: grid distance (D&D 5e diagonal rule), move toward/away/direction with wall collision
- geography: temperature, daylight, travel time, distance calculations
- politics: warfare, trade, stability, diplomacy formulas
- settlements: harvest, population growth, conquest effects
- rule_brain: RuleBrain, the utility-scoring combat AI. Lives here because it consumes rules/* and makes no
  LLM calls, so core/ never imports a concrete brain

The formula modules hold no state and do no I/O, which keeps them testable in isolation. The exceptions are
marked above: handlers mutate the creatures they act on, and perform_level_up rewrites a Character.
"""
