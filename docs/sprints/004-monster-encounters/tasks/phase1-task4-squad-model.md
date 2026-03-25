# Task: Squad Model + squads.yaml

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters (living world pivot)
**Phase:** 1 — Data Foundation

## Description

Create the `Squad` dataclass — an abstract group that moves, fights by formulas, and materializes into concrete Creatures when near an active character. Add `squad_id: str | None` to Creature for tracking which squad a materialized creature belongs to. Parse squad definitions from `squads.yaml`. No runtime behavior yet (movement, combat, materialization are Phase 2-3) — just data model and content loading.

**Squad model:**
```python
@dataclass
class Squad:
    id: str
    name: str
    faction_id: str
    squad_type: SquadType  # PATROL, BANDIT, CARAVAN, MONSTER_PACK, WAR_PARTY
    behavior: SquadBehavior  # PATROL, ROAM, GUARD, TRADE, HUNT, RAID
    current_location_id: str
    route: list[str]           # ordered location IDs for PATROL/TRADE
    territory: list[str]       # location IDs for ROAM/HUNT
    strength: int              # abstract power (not HP)
    max_strength: int
    member_templates: list[str]  # MonsterTemplate IDs
    tick_interval: int         # seconds between movement ticks
```

**YAML format** (`squads.yaml` in world directory):
```yaml
kingdom_patrol_1:
  name: {en: Kingdom Patrol, ru: Королевский патруль}
  faction: kingdom
  type: patrol
  behavior: patrol
  start_location: highfield_mountain_pass
  route: [highfield_mountain_pass, highfield_crossroads, greenwood_forest_road]
  strength: 5
  members: [bandit, bandit, bandit]  # reusing templates for now
  tick_interval: 3600  # 1 hour

wolf_pack_1:
  name: {en: Wolf Pack, ru: Стая волков}
  faction: wildlife
  type: monster_pack
  behavior: roam
  start_location: greenwood_deep_forest
  territory: [greenwood_deep_forest, greenwood_forest_road, greenwood_river_crossing]
  strength: 3
  members: [wolf, wolf, wolf]
  tick_interval: 1800  # 30 min
```

**Content:** 3-4 squads for Sword Vale — a kingdom patrol, a bandit gang, a wolf pack, optionally a goblin raiding party.

## Tests First

1. Parse a squad from YAML with all fields → Squad with correct type, behavior, route, strength, member_templates, faction_id.
2. Parse a squad with territory (roam behavior) → territory field populated, route empty.
3. Parse a squad with route (patrol behavior) → route field populated, territory empty.
4. Load squads from directory-format world → all squads parsed correctly.
5. Missing `squads.yaml` → empty dict, no crash (worlds without squads are valid).
6. Creature with `squad_id = "kingdom_patrol_1"` and another with same squad_id → same squad (ally check can use this field).
7. Squad references member_templates that exist in monster_templates → validation passes (or defer validation to runtime).

## Implementation

- `core/squad.py` (new file) — Squad dataclass, SquadType enum, SquadBehavior enum
- `core/character.py` — add `squad_id: str | None = None` to Creature
- `content_loader.py` — `load_squads()`, `parse_squad()` functions, wire into loader
- `content/worlds/sword_vale/squads.yaml` — 3-4 squad definitions
- `service/game_service.py` — load squads in `start_game()`, pass to relevant layer (store on World or EntitiesLayer for now; EcologyLayer comes in Phase 3)

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Squad is a dataclass with all fields from the model
- [ ] squads.yaml parsed correctly with i18n names
- [ ] squad_id field on Creature works
- [ ] Worlds without squads.yaml load without error

## Status

`done`

## Developer Notes

Clean implementation. Squad dataclass in `core/squad.py` with SquadType and SquadBehavior enums. `squad_id: str | None = None` added to Creature. Content loader gets `parse_squad()` and `load_squads()`. Squads stored on EntitiesLayer (`_squads` dict) for now — will move to EcologyLayer in Phase 3. Three Sword Vale squads: kingdom patrol, bandit gang, wolf pack. No old tests broken (929 total passing).
