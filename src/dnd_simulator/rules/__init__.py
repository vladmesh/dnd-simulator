"""Pure functions for game mechanics and world formulas.

Stateless calculations that can be used by any layer or the Master:
- dice: atomic dice rolling (roll("2d6+3"), roll_d20 with advantage/disadvantage)
- checks: D&D 5e check mechanics (attack_roll, ability_check, saving_throw, damage_roll)
- combat: attack resolution (resolve_attack → AttackResult), initiative rolls (roll_initiative)
- actions: action cost rules (action_cost → ActionCost), per-creature budget defaults
- validation: precondition checks (alive, active, budget, target, reach) → ValidationError or None
- handlers/: per-action-type execution split by domain (combat, movement, equipment, items, trade, reactions)
- action_provider: dynamic available-action sources (base, inventory, weapon) per creature+context
- abstract_combat: squad-vs-squad abstract combat formulas
- conditions: condition effects (is_incapacitated, effective_speed, attack_advantage, tick_conditions)
- modifiers: centralized derived stat pipeline (collect modifiers, compute effective AC/speed/attack, resolve advantage)
- weapons: get_weapon_attack — builds Attack from equipped weapon or fallback
- proficiency: proficiency bonus by level, weapon/armor proficiency per class
- sneak_attack: Rogue sneak attack eligibility and dice count (pure functions)
- resources: resource pool management (has_resource, use_resource, reset)
- reactions: OA eligibility (can_opportunity_attack), trigger detection (find_oa_triggers)
- movement: grid distance (D&D 5e diagonal rule), move toward/away/direction with wall collision
- geography: temperature, daylight, travel time, distance calculations
- politics: warfare, trade, stability, diplomacy formulas
- settlements: harvest, population growth, conquest effects

All functions are pure — no side effects, no state, no LLM calls.
Easy to test in isolation.
"""
