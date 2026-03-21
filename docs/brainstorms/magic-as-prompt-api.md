# Magic as Prompt API

D&D mental mechanics map directly to CRUD operations on NPC prompt structure (memory, traits, inner_state, schedule).

## Core Insight

NPC — structured data. Spells — API calls to that data. Not a hack, literally what these spells do by lore.

## Spell → Operation Mapping

| D&D Mechanic | Operation | Target |
|---|---|---|
| Detect Thoughts | **read** | `memory.recent` + `inner_state` |
| Insight check | **read** (partial, fuzzy) | `inner_state`, maybe `trait_changes` |
| Charm Person | **write** (temporary) | temp trait: "considers caster a friend" |
| Dominate Person | **write** (override) | full override `schedule` + suppress traits |
| Suggestion | **write** (one-shot) | single `schedule_change` or forced action |
| Modify Memory | **write** (direct) | mutate `memory.recent` or `memory.long_term` |
| Confusion | **corrupt** | randomize next action, ignore traits |
| Zone of Truth | **constraint** | temp trait: "cannot consciously lie" |
| Feeblemind | **delete** | wipe `memory`, traits → "understands nothing" |

## Skill Checks as Permission Levels

Checks control read depth/fidelity:

- **Insight DC 10** → "he's nervous" (fuzzy read of `inner_state`)
- **Insight DC 15** → "he's hiding something about the money" (directional hint from `memory.recent`)
- **Insight DC 20** → "he's lying about the gold — he took it" (specific fact from `memory`)
- **Detect Thoughts (spell)** → full read access to `inner_state` + top layer of `memory`

## Write Operations — Duration & Strength

- **Charm**: adds temporary trait with expiry (spell duration). NPC acts on real traits + charm overlay.
- **Dominate**: suppresses all traits, replaces with caster's commands. Schedule fully overridden.
- **Suggestion**: single instruction injected as high-priority goal. Traits still active (NPC refuses if "obviously harmful" per trait evaluation).
- **Modify Memory**: permanent write. NPC genuinely believes altered memory. No expiry — only Remove Curse / Greater Restoration reverts.

## Implementation Notes

- All mental spells become operations on `NpcMemory` / traits / schedule — no special-case code per spell
- `inner_state` field in memory JSON is the key enabler — without it, Detect Thoughts and Insight have nothing to read
- Concentration spells = temporary overlays that get removed on concentration break
- Saving throws gate whether the write/read succeeds, not what happens after
