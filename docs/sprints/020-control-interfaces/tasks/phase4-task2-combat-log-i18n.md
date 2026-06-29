# Task: Localize the combat/event log — missing msgids + faction-name leak

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 4 — Save robustness & i18n polish

## Description

First half of backlog `combat-log-i18n-gaps`: the event log that players and spectators read (`layers/entities/perception.py`) still has two real gaps at `DND_LANGUAGE=ru`. The originally-named causes are already fixed (attack msgids with `{oa}` are translated, `.po:276-283`; move/reputation templates translated, `.po:327-331,450-454`; `movement.py` errors now wrapped in `_()`). What remains:

**A. Missing catalog entries.** These strings are wrapped in `_()` in `perception.py` but absent from `src/dnd_simulator/locale/ru/LC_MESSAGES/dnd_simulator.po`, so gettext falls back to the English msgid:

- Loot: `"You loot {target} ({loot})"`, `"{actor} loots {target} ({loot})"`, `"nothing"`, `"{gold} gold"` (~`perception.py:418-425`)
- Lay on Hands (4 variants): `"You lay hands on yourself, restoring {hp} HP (pool {before}→{after})"`, `"You lay hands on {target}, restoring {hp} HP (pool {before}→{after})"`, `"{entity} lays hands on you, restoring {hp} HP"`, `"{entity} lays hands on {target}, restoring {hp} HP"` (~`perception.py:335-347`)
- Action Surge (2 variants): `"You surge with energy, gaining an extra action"`, `"{entity} surges with energy, gaining an extra action"` (~`perception.py:318-320`)
- Inspect: `"Conditions: {list}."` (~`perception.py:277`)

**B. Faction-id leak in the reputation line** (the E2E phase-3 `kingdom` finding). The `REPUTATION_CHANGED` event (`combat_manager.py:428-438`) carries only `faction_id`; `_perceive_reputation_change` (`perception.py:505-506`) does `d.get("faction_name", d["faction_id"])` and renders the raw slug, e.g. «Твоя репутация с **kingdom** изменилась (100 → 80)». The reputation *template* is already translated — only the interpolated faction value leaks. A `QueryType.FACTION_NAME` query (handled in `layers/politics/layer.py:336`, already used by `awareness_builder.py:331`) resolves a faction_id to its localized display name. `_handle_death` already has `query_fn` in scope (it uses it for `FACTION_RELATION`).

## Tests First

Product-level. Follow the existing i18n test pattern for asserting Russian output (set `DND_LANGUAGE=ru` / the i18n context the suite already uses; ensure `.mo` is compiled).

1. **Faction display name, not the slug.** In a world whose faction has a distinct display name, a kill that drops reputation produces a perceived reputation line containing that display name, not the raw `faction_id` slug. Assert the event now carries `faction_name` and the rendered line does not contain the bare id.
2. **Faction fallback is safe.** When the faction name cannot be resolved (no `query_fn` / unknown faction), the line still renders (falls back to `faction_id`) — no crash, no `KeyError`.
3. **Log lines render in Russian.** With `ru` active, perceiving a loot event, a Lay-on-Hands heal, an Action Surge, and an inspect-with-conditions yields the Russian translations (the `msgstr`), not the English msgid. One assertion per event family is enough.

## Implementation

- **Code (faction leak):** in `combat_manager._handle_death`, before/at the `REPUTATION_CHANGED` event build (`~426-438`), resolve the name via `query_fn` when present: `Query(QueryType.FACTION_NAME, {"faction_id": target.faction_id})`. Add `"faction_name"` to the event `data` only when a non-empty name comes back; otherwise omit it so perception's existing `faction_id` fallback applies. Do not touch `perception.py` line 506 — it already reads `faction_name` first.
- **Catalog:** `make messages` (extract to `.pot`), add the Russian `msgstr` for each missing entry above in the `ru` `.po`, then `make compile-messages` (regenerate `.mo`). Keep the `→` arrow and `{placeholders}` identical between msgid and msgstr.

Gotcha: the lay-on-hands msgids contain `→` (U+2192) and paired `{before}`/`{after}` — copy the msgid verbatim into the `.po` or the entry won't match.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Loot / Lay-on-Hands / Action-Surge / Conditions log lines render in Russian at `DND_LANGUAGE=ru`
- [ ] Reputation line shows the faction's display name; raw `kingdom`-style slug no longer leaks
- [ ] `.mo` recompiled; `make messages` leaves no untranslated combat/event-log msgids for these events

## Status

`pending`
