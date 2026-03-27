# Phase 4 E2E Report

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 4 — NPC Inspect Card

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Click eye icon on NPC in peaceful mode | Modal opens with name, race, role, description, faction, action buttons | Modal showed "Марта", "Человек · Трактирщик", description from YAML, faction "kingdom", Attack + Talk buttons | pass |
| Click eye icon on merchant NPC | Modal includes Trade button in addition to Attack/Talk | Gretta modal showed Attack, Talk, Trade buttons | pass |
| Click eye icon on enemy in combat mode | Modal opens with distance and Attack button | Modal showed "человек", distance "30фт на северо-востоке", Attack button | pass |
| Attack from inspect modal | Modal closes, combat starts, attack executes | Combat initiated, first attack landed (d20+2 vs AC 10), modal closed | pass |
| Talk from inspect modal | Text input appears, message sends, NPC responds | Input appeared in modal, typed "Hello there!", NPC responded "Хочешь что-нибудь купить?" | pass |
| Modal stays open after talk | Modal remains visible after sending message | Modal stayed open with all buttons available | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world + create character | pass | Sword Coast loaded, character created, dashboard rendered with all 3 panels |
| Move between locations | pass | Tavern → Market Square, NPCs and paths updated |
| Basic combat (attack, move, end turn) | pass | Movement toward target, attack rolls, damage, NPC death, "Бой окончен" |
| NPC interaction (rule-based) | pass | Talk to merchant, canned response received |
| Dashboard layout | pass | All panels visible: Nearby, Character+Equipment, Location |
| Action bar | pass | Core buttons, potion drawer, budget display in combat |

## Quick Fixes Applied

- None needed

## Log Analysis

- No errors, warnings, or tracebacks in session or server logs
- One expected validation message: "Цель слишком далеко (30 ft, досягаемость 5 ft)" when attacking out of range — properly handled with user feedback

## Blockers

- None

## Minor Issues

- None observed
