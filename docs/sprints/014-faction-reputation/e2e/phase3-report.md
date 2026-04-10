# Phase 3 E2E Report

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 3 — Reputation Dynamics + Auto-hostility

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Attack neutral NPC (Marta) in Sword Vale | Combat starts with forced_opponents (auto-hostility) | Combat started correctly, initiative order shown | pass |
| Kill neutral NPC | Reputation drops with victim's faction | "Your reputation with kingdom changed (100 -> 80)" in log | pass |
| Reputation change visible in event log | Event shows old/new values | Shown inline in compact log after kill | pass |
| Combat ends after NPC death | Return to peaceful mode | Returned to peaceful, "Nobody around" shown | pass |
| OA reaction prompt during combat | Player gets reaction choice | "Melee attack against Marta" / "Skip" dialog shown | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Landing page | pass | Play/DM cards, language toggle |
| World selection | pass | Sword Vale and Test Vale listed |
| Character creation | pass | Point buy, fighting style, preview all work |
| Load world + first turn | pass | NPC greeting in log, perception panel shows nearby |
| Combat: attack NPC | pass | Battle map, action bar, budget display |
| Combat: move on battle map | pass | Click-to-move works, movement budget updates |
| Combat: OA reaction | pass | Reaction prompt appears, attack resolves |

## Quick Fixes Applied

- None needed during E2E.

## Log Analysis

- "Мёртвые существа не могут действовать" (dead creatures can't act) appears 3x after killing Marta — the round loop still tries to process the dead NPC's remaining turns. Logged at info level, no crash. Pre-existing cosmetic issue (partially fixed in phase 2 close commit 8df78cd).
- No errors or exceptions in session logs beyond the above.

## Blockers

- None.

## Minor Issues

- Dead-mover round processing: after killing an NPC, 3 "dead creature" warnings appear in the event log. Cosmetic only — no gameplay impact. Candidate for backlog.
- Player fights with "fists" despite having longsword in inventory (equipment slot shows "Weapon" but combat says "fists"). Pre-existing issue, not related to phase 3.
