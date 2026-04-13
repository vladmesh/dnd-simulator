# Project Status

Текущее состояние проекта. Один файл — быстрый ответ на "где мы сейчас".

## Current Sprint

**Sprint:** 017-xp-leveling
**Goal:** Ввести XP (за убийства по CR) и систему уровней с level-up модалкой; исправить уровни Paladin (FS/slots/smite на L2), добавить L2 для всех трёх классов.
**Started:** 2026-04-13
**Phase:** 5 — Post-audit cleanup (task 4 done, task 5 pending) — 2026-04-13

**Audit:** Triaged 2026-04-13. Quick-fix: 0 (both stale carry-forward — already removed). Sprint-relevant: 5 → phase 5 refactor. Backlog: 6 new items added (TurnBudget/ResourcePool mutability, schemas.py `Any`, WS test gaps).

### Phases

1. XP & Leveling Core — механика опыта и уровней, без UI и классовых фич
2. Level-up mechanics + Paladin L2 fix — backend level-up, переезд Paladin FS/slots/smite на L2, Fighter Action Surge, Rogue L2 HP
3. Level-up UI + E2E — React модалка с классовыми выборами, полный цикл через Playwright
4. E2E follow-up bug sweep — 6 багов из phase-3 E2E, каждый с RCA + архитектурным фиксом
5. Post-audit cleanup — sprint-relevant долг из audit 2026-04-13 (purity, unit tests, GameService bypass, Any types)

## Sprint History

| Sprint | Goal | Started | Completed |
|--------|------|---------|-----------|
| 016-tech-sweep | Fix E2E/backlog bugs, resolve architecture violations, add enums + harden fail-fast | 2026-04-12 | 2026-04-13 |
| 015-paladin-spell-slots | Paladin L1-L2: spell slots as ResourcePool, Divine Smite, Lay on Hands, multi-damage weapons, target scope enums | 2026-04-10 | 2026-04-12 |
| 014-faction-reputation | Combat sides from faction relations, personal reputation, auto-hostility, friendly OA fix | 2026-04-09 | 2026-04-10 |
| 013-char-creation | Character creation overhaul — point buy, derived HP/AC, starting equipment, Fighter/Rogue only | 2026-04-01 | 2026-04-09 |
| 012-reactions-oa | D&D 5e reactions — opportunity attacks, Disengage, Brain.choose_reaction, reaction prompt UI | 2026-03-30 | 2026-03-31 |
| 011-class-mechanics-l1 | Structured dice, weapon/armor properties, GWF, Cunning Action choice, SA faction, SRD catalogs | 2026-03-28 | 2026-03-30 |
| 010-e2e-polish | UX-баги из e2e sprint 009 + ActionBar decomposition | 2026-03-28 | 2026-03-28 |
| 009-ui-layout | Dashboard layout + combat map + click-to-move | 2026-03-27 | 2026-03-27 |
| 008-content-schema | Pydantic content models, catalogs, schema-driven forms, DM restructure | 2026-03-26 | 2026-03-27 |
| 007-world-session | Save/load, give item, fork UI, layer editor, partial worlds | 2026-03-26 | 2026-03-27 |
| 006-layer-composition | Library templates, manifest, world builder wizard | 2026-03-26 | 2026-03-26 |
| 005-tech-sweep | God classes split, test gaps, architecture fixes | 2026-03-26 | 2026-03-26 |
| 004-monster-encounters | Squads, ecology layer, faction relations, encounters | 2026-03-25 | 2026-03-26 |
| 003-inventory-trading | Inventory, equip slots, accessories, trading | 2026-03-25 | 2026-03-25 |
| 002-meta-pipeline | Sprint pipeline, skills, integration tests | 2026-03-24 | 2026-03-25 |
| 001-class-mechanics | Fighter/Rogue L1 infrastructure (phases 1-3.5, phase 4 deferred → sprint 011) | 2026-03-24 | 2026-03-25 |
