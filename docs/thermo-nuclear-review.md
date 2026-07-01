# Thermo-Nuclear Code Quality Review — full codebase

Date: 2026-06-29 · Branch: `vladmesh/audit` · Scope: entire `src/dnd_simulator/` (~22k LOC) + `frontend/src/` (~15.8k LOC)

Method: 7 independent deep-read agents, one per subsystem (core, entities+round, world-sim layers, rules, service/adapters/llm, content_loader, frontend), plus an orchestrator pass for cross-module evidence (import direction, hidden globals, type hygiene, duplicate-named modules). Findings are structural: abstraction quality, spaghetti growth, boundary/type cleanliness, file size, missed simplifications. This is not a bug hunt, but several behavioral bugs surfaced and are called out separately.

## Verdict

**NOT a clean bill of health.** The architecture is sound in the large (layer stack, pure-rules intent, strategy-based brains, thin transport are all real and mostly honored), and type hygiene at the syntactic level is good (`cast(`: 0, `# type: ignore`: 5 total). But the codebase has three pervasive, cross-cutting structural debts that each touch most subsystems, plus two data-loss/UX bugs. Against the approval bar (no structural regression, no untyped-boundary churn, no boundary leak, no avoidable duplication), this would not pass review as-is. None of it is catastrophic; all of it is fixable with the focused refactors below.

### Severity tally
| | BLOCKER | MAJOR | MINOR |
|---|---|---|---|
| core/ | 1 | 5 | 5 |
| entities/ + round.py | 0 | 7 | 6 |
| world-sim layers | 0 | 5 | 6 |
| rules/ + handlers | 0 | 8 | 6 |
| service/adapters/llm | 0 | 9 | 5 |
| content_loader/ | 1 | 6 | 5 |
| frontend/ | 0 | 9 | 4 |
| **total** | **2** | **49** | **37** |

---

## The three dominant themes (fix these, ~60% of findings collapse)

### Theme 1 — Untyped boundaries are the default, so every consumer re-validates by hand
This is the single most repeated finding across all 7 agents. The system passes data across its most important seams as opaque `object` / `dict[str, Any]` / `Record<string, unknown>`, then each reader re-discovers the shape with `isinstance` / `.get(default)` / `as` casts.

- **Inter-layer query protocol:** `Answer.value: object` (`core/models.py:268`) and `Query.params: dict[str, Any]` (`core/models.py:253`). Consumed with `isinstance`/`str()`/`assert isinstance` at 15+ sites in `awareness_builder.py` alone (`:66,82,91,100,114,351,380`), plus `combat_manager.py:106`, `ecology/layer.py:376`, `settlements/layer.py:78-103`.
- **Squad/lair cross-boundary dicts:** `activation_manager.py:307,353-361,463-471,503-511` hand-coerce `int(info["strength"])` etc. off bare dicts ecology returns.
- **Core messaging payloads:** `Event.data`, `Action.params`, `ReactionTrigger.data`, `PerceivedEvent.data` all open dicts though their key sets are fixed.
- **LLM path:** `llm/brain.py:142-186` converts typed `CombatAwareness`/`PeacefulAwareness` dataclasses *to* `dict[str, Any]` only so `prompts.py:27-30,116-120` can read them back by string key. Pure self-inflicted type loss, no transport boundary in between.
- **Content schemas:** `ItemContent` (`schemas.py:113-154`) and `class_features` (`schemas.py:422,453`) are stringly-typed `str | None` / `dict[str, Any]` even though every field maps to an existing enum; validation is deferred into converters where it raises raw `ValueError`/`KeyError`.
- **Frontend:** `WorldStateResponse` regions/nations/settlements/entities are `Array<Record<string, unknown>>` (`types/api.ts:147-154`); the 37 `as` casts in the app concentrate on reading them.

**Fix:** bind result types to queries (typed dataclasses per `QueryType`, or typed accessors `query_relation`/`query_dict` so the cast lives once); type the content-schema fields with their real enums + sub-models; have the prompt builders take the typed awareness directly; generate frontend response types from the backend OpenAPI schema. Each change deletes a cluster of defensive casts.

### Theme 2 — One concept modeled by hand N times instead of as data/registry
Abstractions that exist are not used as the single source; the same structure is spelled out per-instance.

- **Equipment slots are written three ways:** 6 parallel `equipped_*` fields (`character.py:226-231`), 12 near-identical equip/unequip `ActionType`s + `ActionDef`s (`action_defs.py:301-418`), a `_EQUIPMENT_FIELDS` tuple (`player.py:56-63`), and 12 two-line handler wrappers + 6 config constants (`handlers/equipment.py:147-234`). The `EquipmentSlot` enum and `SLOT_CONFIGS` already prove the slot is the real key. → `equipped: dict[EquipmentSlot, Item]` + one `EQUIP`/`UNEQUIP` action with a `slot` param + factory-generated handlers. Net deletion of ~10 ActionDefs, 12 wrappers, 6 constants, a field tuple.
- **`query()` is a stringly-dispatched if/elif chain in all four layers** (`geography:121-208`, `politics:291-340`, `settlements:149-199`, `ecology:172-200`), each ending in a copy of `raise ValueError`. → `dict[QueryType, Callable]` table on a shared base.
- **"Find a layer by isinstance" reimplemented 5×** (`game_service.py:251-267`, `action_dispatcher.py:219-223,248-252`), with inconsistent failure (raise vs return None). → `World.get_layer[L](kind: type[L]) -> L`.
- **Exception→HTTPException ladder copy-pasted across ~40 route handlers**; `routes_content.py` repeats a type-guard ladder in all 10 CRUD handlers. → app-level `@app.exception_handler` registrations; handlers just call the service.
- **`ActionProvider` probe boilerplate** repeated 7× (`action_provider.py:44-166`). → one `available(creature, ctx, types)` helper.
- **Frontend twins:** `WorldOverview` Nations/Settlements tables (`:64-193` vs `:195-331`) and `EventLog` CompactLog/FullLog (`:214-289` vs `:295-388`) are the same component duplicated. → generic `EditableStatsTable<T>`; `useStickyScroll`/`useLogInteraction` hooks.

### Theme 3 — Serialization is split-brain and duplicated, with no single source of truth
Save/load and wire formats are hand-built in multiple places that drift independently.

- **Item wire format is owned twice in two layers:** `_serialize_item` hand-rolls the flat dict (`core/player.py:13-53`) while `deserialize_item` rebuilds via `ItemContent` Pydantic (`content_loader/items.py:229`). This is also the BLOCKER below.
- **Player status exists in 3-4 parallel representations:** `PlayerStatusData` DTO (`dto.py:21`), `PlayerStatusResponse` Pydantic (`schemas.py:180`), `_player_to_dict` WS (`session.py:164`), `_to_response` manual copy (`routes_player.py:72`). Frontend mirrors it again as `PlayerStatus` vs `PlayerStatusResponse` twins.
- **Per-layer `to_dict` copy-pasted 2-3× per layer** (geography/politics/settlements each build the same entity dict in query branches and `get_state`); ecology already shows the fix (`_squad_to_dict`).
- **`GameDateTime` (de)serialization copy-pasted 4× in `World.save/load`** (`world.py:131-181`) though sibling models have `to_dict`/`from_dict`.
- **Ability-scores conversion triplicated** (`creatures.py:59-70`, `monsters.py:36-45`, `creatures.py:293-310`); **ref/base merge duplicated with divergent dump semantics** (`items.py:164-186` uses `exclude_none`, `monsters.py:100-126` uses `by_alias`).

**Fix:** make the producing function the one source (e.g. `player_status` returns `PlayerStatusData`, everything else `model_validate(asdict(...))`); add `to_dict`/`from_dict` to `GameDateTime`; extract per-layer `_x_to_dict` helpers (or a `DictBackedLayer` base); one `merge_catalog_ref` helper; one `AbilityScoresContent.to_runtime()`.

---

## Behavioral bugs surfaced (not just smells)

1. **[BLOCKER] Accessory modifiers silently dropped on every save→load.** `_serialize_item` writes key `grant_modifiers` (`core/player.py:47`) but `ItemContent` expects `modifiers` (`schemas.py:152`) and has no `model_config`, so Pydantic's default `extra="ignore"` discards it on `model_validate` (`items.py:237`). An equipped ring with +1 STR loads fine from authored YAML but loses its modifier after one autosave cycle. **Fix:** symmetric names (`alias="modifiers"` + `populate_by_name`), add a round-trip regression test, set `extra="forbid"` so future drift fails loud.
2. **[MAJOR] `lay_on_hands` log events render no icon.** `EVENT_ICONS["entity_lay_on_hands"] = "hand-heart"` (`logProcessing.ts:68`) but `ICON_MAP` has no `"hand-heart"` (`EventLog.tsx:50-83`); `EventIcon` returns `null`. Live rendering bug from two hand-synced registries. **Fix:** collapse to one `Record<EventType, LucideIcon>` or add a `satisfies` exhaustiveness check.
3. **[MAJOR] `handle_wait` reports success while doing nothing.** On an unreachable/misnamed travel target, `handlers/movement.py:248-249` falls through to `pass` and returns `ActionResult(success=True)`. **Fix:** split `handle_travel` from `handle_wait`, resolve destination once, return `success=False` on no route.
4. **[MAJOR] HTTP status chosen by substring-matching the exception message.** `routes_player.py:64-68` does `"No player" in msg or "not found" in msg` to pick 404 vs 400. Rewording or translating the message changes the status. **Fix:** distinct exception types + app-level handlers.
5. **[MINOR] Healing / Second Wind rolls are not reproducible under seeded replay.** `handlers/items.py:71,221` call `roll(...)` without a threaded `rng`, falling back to the process-global; attack resolution threads `rng` but these don't, so reproducibility is bimodal. **Fix:** thread `rng` through `ActionContext` into all handlers.

---

## Layering & purity (the load-bearing invariants)

Import direction is clean at module level for `rules→` and `layers→` (grep: none reach up into service/adapters). But the **`core/` "no external dependencies" claim is false in practice**, and **`rules/` purity has eroded in two files**:

- **[BLOCKER] `core/player.py:117` imports `content_loader`** — bottom of the stack reaching the top, a real cycle broken only by a function-local import.
- **[MAJOR] `core/` has 26 runtime in-function upward imports** dodging cycles: `class_features.py:33,41`→`rules.fighting_style`, `combat.py:161`→`rules.dice`, `monster.py:28`→`rules.leveling`, `player.py:117`→`content_loader`. `core/__init__.py:29` asserts "no external dependencies". **Fix:** push the rules-consuming behavior out of the data objects (xp-on-spawn → spawning caller; `place_randomly` → a rules placement helper taking `BattleMap`+`rng`; invert `ClassFeatures.collect_*` so `rules.modifiers` reads plain data).
- **[MAJOR] Pure-rules modules log via structlog** while their docstring says "No state, no I/O": `sneak_attack.py:22,138`. **Fix:** return the reason, let the impure caller log.
- **[MAJOR] Handler errors bypass gettext**, breaking the i18n invariant: `handlers/items.py`, `equipment.py`, `trade.py`, `action_surge.py`, `loot.py`, `combat.py` return raw English f-strings while `movement.py` wraps everything in `_()`. Russian (the default) silently falls back to English on equip/use/trade failures. **Fix:** wrap in `_()`, or return a machine `code` + params and localize at the boundary.
- **[MINOR] Module-global mutable RNG** (`dice.py:14`) with un-threaded callers in `ecology/layer.py:146` (lair depletion), `handlers/items.py` (healing). Determinism survives only because `app.py` seeds once. **Fix:** thread `rng`; document `get_global_rng()` as the one sanctioned impurity.
- **[MAJOR] `core` base classes carry NPC-only hooks and duck-type `settlement_id`** (`character.py:295,312` + stubs `:240,261,286,291`); `perceive` reads `getattr(self, "settlement_id", None)`, so renaming the field on `Npc` keeps compiling but silently stops name-recognition. **Fix:** move `perceive`/NPC hooks onto `Npc` or a `Perceiver` Protocol.
- **[MAJOR] `round.py:339` imports `resolve_abstract_move` from `service.session`** — the orchestrator reaching up into the layer the `CreatureHost` Protocol exists to decouple from. The function is pure. **Fix:** move it to `rules/movement.py`.
- **[MINOR] Lair depletion rule + RNG roll live in the ecology layer** (`ecology/layer.py:141-149`) not in `rules/`. **Fix:** `rules/lairs.should_deplete(lair, roll)`.

---

## File-size / decomposition (no file >1000 lines, but several mix concerns)

| File | LOC | Concerns mixed | Suggested split |
|---|---|---|---|
| `layers/entities/activation_manager.py` | 614 | activation + encounters + materialization (squad & lair dup the same algorithm) | `activation.py` / `encounters.py` / `materialization.py` w/ a generic tracker |
| `round.py` | 619 | turn loop + awareness assembly; combat & peaceful loops are near-twins | one `_run_turn_loop(...)`; move builders to `AwarenessBuilder` |
| `layers/entities/layer.py` | 629 | layer orchestration + 230-line entity serializer (double-serializes player) | `entity_serialization.py` (mirror `combat_serialization.py`) |
| `service/session.py` | 536 | listener Protocol + 8 wire serializers + movement rule + lifecycle | `service/wire.py`; move `resolve_abstract_move` to rules |
| `service/commands_worldbuilder.py` | 535 | 100-line manual serializer + 10 CRUD pass-throughs | table-driven CRUD; `model_dump` view; split worlds/content |
| `layers/ecology/layer.py` | 457 | route + roam movement + squad combat + lairs (politics already decomposed; ecology never was) | `ecology/movement.py` / `squad_combat.py` / `lairs.py` |
| `content_loader/schemas.py` | 457 | 6 content domains in one module | `schemas/` package, flat re-export |
| `core/combat.py` | 303 | grid model + wall math + RNG placement + ASCII rendering | extract `wall_edges()`; move rendering to presentation; placement to rules |
| `frontend SchemaForm.tsx` | 488 | per-branch label boilerplate + defaults built twice | `<FieldShell>` + one `buildDefaults` + `localizedCodec` |
| `frontend TargetDropdown.tsx` | 354 | generic targeting + smite flow + lay-on-hands slider | reduce to target-pick; `AttackAction`/`LayOnHandsAction` wrappers |

---

## Recommended remediation order (highest leverage first)

1. **Fix the 2 BLOCKERs** (item-modifier data loss; `core/player.py`→`content_loader` cycle) — one is data corruption, the other unblocks enforcing import direction with a linter.
2. **Type the inter-layer query boundary** (Theme 1) — deletes the largest single cluster of defensive casts and makes the layer contracts checkable.
3. **Collapse the equipment slot triplication** (Theme 2) — biggest concrete line-deletion, removes a whole class of "touch 6 places to add a slot".
4. **App-level exception handlers + `World.get_layer`** — two small additions that delete repetition across ~45 files.
5. **Unify player-status + GameDateTime + per-layer serialization** (Theme 3) — kills the silent REST/WS drift risk.
6. **Restore `rules/` purity** (drop structlog, wrap i18n, thread `rng`) — cheap, protects the invariant the design leans on.
7. **Decompose the 600-line files** along the seams in the table — do after the above so you split cleaner code.
8. **Frontend:** generate types from OpenAPI; extract the table/log/form duplications; move D&D rule math out of `CharacterForm`.

---

# Appendix — full per-subsystem findings

Every finding cites `path:line` and a concrete remedy. Format: **title** — where · problem · remedy.

## core/

- **[BLOCKER] `core/player.py` imports `content_loader`; item serialization split-brain.** `player.py:117` + `_serialize_item` `:13-53` vs `content_loader/items.py:229`/`ItemContent`. Cycle broken by local import; wire format owned in two layers, neither canonical. → move both serialize+deserialize into `content_loader` driven by `ItemContent`; `to_full_save_data` delegates or relocate player save/load to content_loader/service.
- **[MAJOR] `core` claims no deps but lazy-imports `rules`/`content_loader`.** `__init__.py:29` vs `class_features.py:33,41`, `combat.py:161`, `monster.py:28`, `player.py:117`. → push rules-consuming behavior out of data objects (see Layering section).
- **[MAJOR] `Character`/`Creature` carry NPC-only hooks + duck-typed `settlement_id`.** `character.py:295,312` + stubs `:240,261,286,291`; real impls `layers/entities/models.py:45,72-92`. `getattr` recognition silently no-ops. → move onto `Npc` or a `Perceiver` Protocol.
- **[MAJOR] Inter-layer query protocol fully untyped (`Answer.value: object`).** `models.py:268`; casts at `awareness_builder.py:66,82,91,100,114,351,380`, `combat_manager.py:106`, `ecology/layer.py:376`. → typed dataclasses per query or typed accessors.
- **[MAJOR] Six `equipped_*` fields + 12 equip/unequip ActionTypes hand-encode one slot abstraction.** `character.py:226-231`, `action.py:22-33`, `action_defs.py:301-418`, `player.py:56-63`; `EquipmentSlot` already exists `items.py:27`. → `equipped: dict[EquipmentSlot, Item]` + one EQUIP/UNEQUIP with `slot` param.
- **[MAJOR] `core/combat.py` mixes grid model + wall math + RNG placement + text rendering; wall→edge logic duplicated.** `combat.py` 303; dup `_get_blocked_edges:120-147` vs `render_ascii:240-252`; `place_randomly:161` pulls global RNG. → extract `wall_edges()`; move rendering to presentation; placement to rules.
- **[MINOR] `ClassFeatures.collect_*` are pass-through delegators with empty stubs.** `class_features.py:32-49,60-64,82-86,100-108`; `rules/modifiers.py` calls back. → let `rules.modifiers` read plain data; drop `collect_*` from core.
- **[MINOR] `EntityKind` fuses two vocabularies.** `models.py:9-21` (PLAYER/NPC/CREATURE/CONTAINER vs PLAYER/NPC/MONSTER). → split `EntityKind` (persistence) and `EntityCategory` (API).
- **[MINOR] Untyped payload dicts pervade core messaging.** `models.py:229,253`, `action.py:57`, `reactions.py:31`, `awareness.py:189`. → typed fields/dataclasses; keep `dict` only for `EventType.CUSTOM`.
- **[MINOR] `GameDateTime` (de)serialization copy-pasted 4× in `World.save/load`.** `world.py:131-139,142-149,159-166,174-181`. → add `GameDateTime.to_dict()/from_dict()`.
- **[MINOR] Dead logger in `core/character.py`.** `:23` + `import structlog :9`, never referenced. → delete.

## layers/entities/ + round.py

- **[MAJOR] `round.py:339` reaches up into `service.session` for pure move-resolution.** → move `resolve_abstract_move` to `rules/movement.py`.
- **[MAJOR] Activation runs twice per loop iteration.** `round.py:572` `_activate()` then `run_round()` re-activates at `:526`. Heaviest per-round op double-runs; latent double-spawn. → one owner; build query/emit fns once.
- **[MAJOR] `query_fn → FactionRelation` adapter closure hand-rolled 4× (6 sites).** `combat_manager.py:101,405,374`, `awareness_builder.py:346,375`, `activation_manager.py:281`. Already diverge (NEUTRAL default vs assert). → `make_relation_fn(query_fn)` in `rules/reputation.py`.
- **[MAJOR] `activation_manager.py` (614) bundles 3 concerns; squad & lair materialization duplicate the algorithm.** `:55-146`, `:148-293`, `:297-349` vs `:453-501`. → split + generic tracker.
- **[MAJOR] `EntitiesLayer.get_state/load_state` (401-629) mixes serialization into the layer + double-serializes player.** Creature branch `:413-456` serializes equipment, then `:459` `to_full_save_data()` does it again and overwrites. → `entity_serialization.py`; serialize equipment once.
- **[MAJOR] `run_combat_turn` and `run_peaceful_turn` are the same loop with divergent special cases.** `round.py:298-365` vs `:367-433`. → one `_run_turn_loop(creature, ctx, awareness_fn, should_end_fn, on_failure)`.
- **[MAJOR] Awareness assembly leaks into the `Round` orchestrator.** `round.py:101-174,268-296`; `replace()`-patches the DTO `AwarenessBuilder` just built; `_build_equipped` re-imports `Item` in a loop to assert. → move builders into `AwarenessBuilder`.
- **[MINOR] `_build_available_items` carries a dead `available_actions` param.** `round.py:101-113`, called `:283,398`. → drop it or actually filter.
- **[MINOR] `_last_seen_log_index` is one cursor mutated by two methods in two classes; `get_new_raw_events` dead.** `layer.py:231-232` + `query_handler.py:189-191`; `NEW_RAW_EVENTS` zero prod callers. → one writer; delete dead query.
- **[MINOR] `_event_location` duplicated; "combat ended" reverse-engineered.** `layer.py:331-350` vs `combat_manager.py:483-491`; `had_combat` snapshot/recheck `layer.py:192-197,275-283`. → hoist one helper; give `CombatManager` an `on_combat_ended` callback.
- **[MINOR] Squad/lair query results cross the boundary as `dict[str, Any]`; tracker state is a positional tuple.** `activation_manager.py:307,353-361,463-511`; tuple `layer.py:88`. → frozen `SquadInfo`/`LairInfo`; `MaterializedSquad` dataclass.
- **[MINOR] `BattleMap._inner_walls` read from 3 external modules; wall→dict duplicated.** `combat_manager.py:82`, `combat_serialization.py:14`, `awareness_builder.py:207`. → public `walls_as_dicts()` / `Wall.to_dict()`.
- **[MINOR] `EntitiesLayer` is a facade of pass-throughs, several only exercised by tests.** `layer.py:207-219,319-329`. → point tests at sub-managers; delete test-only wrappers.

## layers/ (geography, politics, settlements, ecology)

- **[MAJOR] Per-entity `to_dict` copy-pasted 2-3× per layer; ecology shows the fix.** geography `:181-193` vs `:210-226`; politics `:299-317` vs `:342-360`; settlements `:164-175,183-193,205-213`; ecology `_squad_to_dict :425-437`. → per-layer `_x_to_dict` helpers.
- **[MAJOR] No shared Layer base/mixin; ABC scaffolding duplicated across all four.** no-op `handle_event` geography `:117-119`, politics `:287-289`; repeated dict-of-entities init/get_state/load_state. → `DictBackedLayer[ModelT]` base.
- **[MAJOR] `query()` is a stringly-dispatched if/elif chain in every layer.** geography `:121-208`, politics `:291-340`, settlements `:149-199`, ecology `:172-200`. → `dict[QueryType, Callable]` table.
- **[MAJOR] `ecology/layer.py` (457) is a monolith while politics is decomposed.** movement `:265-321`, squad combat `:327-423`, lairs `:127-170`. → `ecology/movement.py`/`squad_combat.py`/`lairs.py`.
- **[MAJOR] `load_state/get_state` use untyped `dict[str, object]` with isinstance+coercion ladders; inner type inconsistent.** geography `:228-261`, politics `:376-419`, settlements `:216-232`, ecology `:226-259`; `dict[str,Any]` vs `dict[str,dict[str,object]]`. → `TypedDict` per layer or shared `_enum_safe_asdict`/`from_dict`.
- **[MINOR] Lair depletion rule + RNG roll live in the ecology layer, not rules/.** `:141-149`. → `rules/lairs.should_deplete(lair, roll)`.
- **[MINOR] `_relation_key` duplicated, `clamp` duplicated, bidirectional-relations dict rebuilt everywhere.** `politics/layer.py:64` + `diplomacy.py:12`; `clamp` `rules/politics.py:120` + `rules/settlements.py:116`; ad-hoc key logic in layer/economy/warfare/diplomacy. → `RelationMap` + shared `clamp`.
- **[MINOR] Cross-layer query results are untyped `object` dicts consumers re-validate.** `Answer.value: object` (`models.py:268`); settlements `:78-103`. → typed payloads + accessor.
- **[MINOR] `Query.params: dict[str,Any]`; access + KeyError handling inconsistent.** guarded getter in geography but raw index politics `:300`/settlements `:165`/ecology `:192`. → guarded `get_X`; `params.require`/`params.opt`.
- **[MINOR] Settlements hardcodes the 30-day magic number twice + duplicates the politics sub-tick loop.** `:43,66`; politics names it `_TICK_INTERVAL_SECONDS:31`. → name the constant; shared catch-up helper.
- **[MINOR] Geography recomputes identical `base_temp` inside the weather-step loop.** `:88-96` (steps+1 times). → compute once before loop.

## rules/ + rules/handlers/

- **[MAJOR] Pure modules log via structlog despite "No state, no I/O".** `sneak_attack.py:22,138` (and `rule_brain.py:28`). → return reason; caller logs.
- **[MAJOR] Handler errors bypass gettext.** `handlers/items.py:47,102,114,123`, `equipment.py:100-107,131`, `trade.py:43,46`, `action_surge.py:29-38`, `loot.py:35`, `combat.py`. → wrap in `_()` or return code+params.
- **[MAJOR] `check_target_scope` is a tri-state maze; TAKE special-cased across 3 checks.** `validation.py:290-357`; TAKE bailouts `:142-143,183-184,296-297`. → per-action validator selection in `action_defs`; `resolve_hostility(...) -> Hostility` enum.
- **[MAJOR] equipment.py: 12 thin wrappers + 6 constants over 2 generic functions.** `:147-234,149-154`. → factory `make_equip_handler(cfg)` keyed off `SLOT_CONFIGS`.
- **[MAJOR] Duplicated validate-probe boilerplate across every ActionProvider.** `action_provider.py:44-166`. → one `available(creature, ctx, types)` helper.
- **[MAJOR] Compass tables + diagonal-cost logic duplicated 3-4× in movement.py.** dirs `:16-25,49-59,70-80,91-101`; diag cost `:39,152-159,195-198,221-225`. → one `_COMPASS` dict + one `diag_step_cost()`.
- **[MAJOR] `attack_modifiers` (80 lines) mixes mechanics with UI breakdown.** `modifiers.py:235-315`. → `compute_attack_mechanics()` + thin `build_roll_breakdown()`.
- **[MAJOR] `handle_wait` does silent best-effort travel; no-ops as success.** `handlers/movement.py:222-258`, name-match fallback `:240-250`, `pass` `:248-249`. → split `handle_travel`; single `graph.resolve()`; return failure.
- **[MINOR] `perform_level_up._rebuild_features` silently drops unknown feature types.** `perform_level_up.py:80-92` (no `else`). → `ClassFeatures.leveled_up(...)`.
- **[MINOR] `compute_stat` keys the no-double-stack map on `id(m)`, mixing `str|int`.** `modifiers.py:143-147`. → local counter or sum sourceless ADDs directly.
- **[MINOR] `effective_ac` does `max(stored, computed)` for unarmored Characters.** `modifiers.py:223-224`. → pick one canonical source.
- **[MINOR] RuleBrain re-derives `(budget.x if budget else 0)` ~10×.** `rule_brain.py:218-331`; `_CombatContext :38-50`. → normalized fields on `_CombatContext`.
- **[MINOR] Trade inverts the transfer primitive by passing negative gold.** `trade.py:55-66`; primitive `inventory.py:17-23`. → keep gold non-negative; make direction explicit (`pay(payer, payee, price)`).
- **[MINOR] Module-global mutable RNG; some rolls non-reproducible.** `dice.py:14,17-20`; un-threaded `handlers/items.py:71,221`, `ecology/layer.py:146`. → thread `rng` via `ActionContext`.
- Clean & well-factored (agent note): geography, politics, settlements, character_creation, checks, combat, combat_sides, encounters, leveling, proficiency, reputation, conditions, loot, inventory, abstract_combat, fighting_style, weapons. Trivial dupes to sweep: `clamp` (politics/settlements), `handle_dodge`/`handle_flee` identical stubs.

## service/ + adapters/ + llm/

- **[MAJOR] Player status in 3-4 parallel representations with hand remapping.** `dto.py:21`, `schemas.py:180`, `session.py:164`, `routes_player.py:72`. → `player_status` single source; `model_validate(asdict(...))`.
- **[MAJOR] Exception→HTTPException boilerplate across every route; content routes repeat type-guard ladder 10×.** `routes_content.py:43-181`, `routes_session.py:63-271`, `routes_world.py:118-247`. → app-level handlers; `_parse_entity_type(raw, *, kind=...)`.
- **[MAJOR] Typed Pydantic requests flattened to `dict[str,Any]`, re-validated by hand.** `routes_session.py:106,117,142,172,186` → `commands_creatures.py:73-132`, `commands_politics.py:11-35`. → pass typed model or `{field:(attr,setter)}` table.
- **[MAJOR] "Find a layer by isinstance" reimplemented 5×; inconsistent failure.** `game_service.py:251-267`, `action_dispatcher.py:219-223,248-252`. → `World.get_layer[L](kind)`.
- **[MAJOR] `session.py` (536) mixes 4 concerns; wire serializers belong in own module.** `:34-253`. → `service/wire.py`; move `resolve_abstract_move` to rules.
- **[MAJOR] `start_round` is ~100 lines of nested closures; `on_turn` re-duplicates `_build_round_state`.** `session.py:389-489` vs `:365-383`. → optional `awareness` override param; promote callbacks to methods.
- **[MAJOR] `commands_worldbuilder.py` (535): hand-rolled serializer + 10 near-identical CRUD pass-throughs.** `:60-157,392-518`. → `model_dump` view; table-driven CRUD; split module.
- **[MAJOR] LLM prompts round-trip typed awareness through `dict[str,Any]`.** `llm/brain.py:142-186` → `prompts.py:27-30,116-120`. → builders take typed dataclasses; delete converters.
- **[MAJOR] Route picks HTTP status by substring-matching the exception message.** `routes_player.py:64-68`. → distinct exception types + handlers.
- **[MINOR] Stringly-typed `"library"` check; `_resolve_layer_path` downcasts the enum.** `commands_worldbuilder.py:298-313`, checked `:368,428,444,459`. → return `LayerSource`; `_require_writable_layer`.
- **[MINOR] Game-time formatting duplicated + computed inside an adapter.** `routes_session.py:277-279` + `commands_world_state.py:64`. → `GameDateTime.format()`.
- **[MINOR] `GiveItemRequest` models a discriminated union as 25 optional fields.** `schemas.py:68-92`, `routes_session.py:142`. → Pydantic discriminated union on `type`.
- **[MINOR] Dead code: `apply_session_lang`, `LlmResponse.raw_message`.** `deps.py:20-28`, `client.py:31,158`. → delete or actually use.
- **[MINOR] Untyped `dict[str,object]` passthrough responses bypass schema validation.** `routes_world.py:156-163`, `schemas.py:207-213`. → Pydantic response models.

## content_loader/

- **[BLOCKER] Accessory modifiers dropped on save/load round-trip.** `schemas.py:152` (`modifiers`) vs `core/player.py:47` (`grant_modifiers`) vs `items.py:90,237`; no `model_config` → `extra="ignore"` discards. → symmetric names + `extra="forbid"` + regression test.
- **[MAJOR] `ItemContent` stringly-typed; enum validation in converters not at the boundary.** `schemas.py:113-154`, `items.py:36-104`. → real enums + `ModifierContent` submodel.
- **[MAJOR] Ability-scores→runtime conversion triplicated.** `creatures.py:59-70,293-310`, `monsters.py:36-45`. → `AbilityScoresContent.to_runtime()`.
- **[MAJOR] Duplicated ref/base merge with inconsistent dump semantics.** `items.py:164-186` (`exclude_none`) vs `monsters.py:100-126` (`by_alias`). → one `merge_catalog_ref(...)`.
- **[MAJOR] crud.py: 4 near-identical create/update funcs + 2 parallel storage families.** `:180-234,280-331`. → `_persist(entry,id,data,*,must_exist)`; `KeyedFileStore`/`PerFileStore` strategy.
- **[MAJOR] `class_features` escapes Pydantic as `dict[str,Any]`, dict-walked + pointlessly re-wrapped.** `schemas.py:422,453`, `creatures.py:73-103,137-139,234-236`. → `ClassFeaturesContent` submodel.
- **[MAJOR] Same `monsters.yaml` entry validated against two schemas (CRUD vs loader).** `crud.py:106-111` (loose `MonsterTemplateEntryContent`) vs `monsters.py:96,125` (strict `MonsterTemplateContent`). → single resolution path reused by CRUD/schema-gen.
- **[MINOR] Items validated twice via model→dict→model round-trip.** `creatures.py:130-133,225-228`, `monsters.py:212-215`, `items.py:189-208`. → `items_from_models(list[ItemContent])`.
- **[MINOR] Dead defensive `hasattr` on a guaranteed Pydantic field.** `items.py:90`. → `model.modifiers or []`.
- **[MINOR] `load_factions` re-implements `resolve_text` and swallows malformed entries.** `world.py:223-234`. → `FactionContent` schema; `resolve_text`; raise on non-dict.
- **[MINOR] `# type: ignore[arg-type]` masks list-vs-tuple mismatch on `combat_position`.** `creatures.py:172,263`, `schemas.py:376-396`. → validator returns `tuple[int,int]`.
- **[MINOR] `schemas.py` (457) mixes six content domains.** → `schemas/` package, flat re-export.
- Follow-up (agent note): `parse_ability_scores`/`parse_attacks` are reached by `commands_creatures.py:202-218` and `layers/entities/layer.py:524-535`, which hand-walk raw YAML and **bypass the `NpcContent`/`PlayerContent` schemas entirely**. That parallel unvalidated parse path is worth its own task.

## frontend/

- **[MAJOR] Two icon registries drift — `lay_on_hands` renders no icon (live bug).** `logProcessing.ts:68` vs `EventLog.tsx:50-83`. → one `Record<EventType, LucideIcon>` or `satisfies` check.
- **[MAJOR] Player/creature types are hand-maintained twins.** `types/game.ts:256-275` vs `types/api.ts:128-145`; `AbilityScores` vs `Record<string,number>`. → generate from OpenAPI.
- **[MAJOR] D&D rule logic hardcoded inside `CharacterForm`.** `setup/CharacterForm.tsx:21-74` + cast `:154`. → `lib/characterPreview.ts`; source constants from backend; typed request.
- **[MAJOR] Smite-choice UI implemented twice.** `SmiteChoice.tsx` vs `TargetDropdown.tsx:141-194`; param-building dup `:107-115` + `NpcInspectModal.tsx:186-193`. → render `<SmiteChoice>`; extract `buildAttackParams`.
- **[MAJOR] `TargetDropdown` (354) is a god-component.** `:70-194,245-354`. → reduce to target-pick; `AttackAction`/`LayOnHandsAction` wrappers.
- **[MAJOR] `WorldOverview` Nations/Settlements tables are copy-paste twins over untyped rows.** `:64-193` vs `:195-331`. → generic `EditableStatsTable<T>` + typed rows.
- **[MAJOR] `turnSlice` handlers duplicate awareness/time-apply logic.** `turnSlice.ts:73-134` (time extraction verbatim `:88,112,130`). → `applyCommon(msg)` + `extractGameTime`.
- **[MAJOR] `EventLog` CompactLog/FullLog duplicate scroll-stickiness, expand state, modal wiring.** `:214-289` vs `:295-388`. → `useStickyScroll`/`useLogInteraction` hooks.
- **[MAJOR] `SchemaForm` (488) repeats label/required boilerplate per branch + builds defaults twice.** `:228-389,70-87,434-442`. → `<FieldShell>` + one `buildDefaults` + `localizedCodec`.
- **[MINOR] `WorldStateResponse` is `Array<Record<string,unknown>>`, forcing cast soup.** `types/api.ts:147-154`, `WorldOverview.tsx:46-54`. → `Region`/`Nation`/`Settlement` interfaces.
- **[MINOR] FastAPI validation-error parsing duplicated + inconsistent across forms.** `CreatureForm.tsx:96-104`, `LayerEditor.tsx:60`, `GiveItemDialog.tsx:72`; `ApiError` `apiClient.ts:36-46`. → `ApiError.detailMessage()`.
- **[MINOR] `NpcInspectModal` overloads `talkText` as input value + visibility flag.** `:165,199,204`. → `showTalk` boolean.
- **[MINOR] `connectionSlice.connect()` re-lists every turn/player field to reset state.** `connectionSlice.ts:78-91` vs `turnSlice.ts:62-71`. → export `initialTurnState`/`initialPlayerState`.
