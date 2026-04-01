# Task: Guard Monster Template + Content Fixes

**Date:** 2026-04-02
**Sprint:** 013-char-creation
**Phase:** 3 — Content Fixes + Polish

## Description

Create a guard monster template in the catalog and fix all patrol squads that incorrectly use bandits as members.

Changes:
- `content/catalogs/monsters/guard.yaml` — D&D 5e Guard stats: HP 11, AC 16 (chain shirt + shield), STR 13, DEX 12, CON 12, spear attack (1d6+1 piercing, reach 5).
- `content/library/ecology/sword_vale/squads.yaml` — `kingdom_patrol_1.members: [guard, guard, guard]`
- `content/worlds/test_vale/ecology/squads.yaml` — `militia_patrol.members: [guard, guard]`

Note: AC 16 per SRD Guard stat block (chain shirt 13 + DEX mod +1 + shield +2 = 16). Not chain mail — chain mail wouldn't allow DEX bonus.

## Tests First

Unit tests in `tests/unit/test_content_loader.py` (or new file if cleaner):

1. **Guard template loads from catalog** — load `guard.yaml` via catalog loader, verify MonsterTemplate fields: hp=11, ac=16, speed=30, cr=0.125, faction="", ability_scores match SRD guard (str:13, dex:12, con:12, int:10, wis:10, cha:10).
2. **Guard spawn produces correct creature** — call `template.spawn(location, id)`, verify resulting Creature has hp=11, ac=16, correct attacks.
3. **Sword Vale squads reference guard** — load sword_vale ecology content, verify kingdom_patrol_1 members are `["guard", "guard", "guard"]`.

## Implementation

1. Create `content/catalogs/monsters/guard.yaml` with SRD Guard stats.
2. Update `kingdom_patrol_1` members in sword_vale squads.yaml.
3. Update `militia_patrol` members in test_vale squads.yaml.
4. Run tests green.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Guard template matches SRD Guard stat block
- [ ] No patrol squad references bandit as member

## Status

`pending`
