# NPC Lifecycle — Plan

## Phase 1 — Locations, Schedule, Movement (0 LLM) DONE

> Implemented in commits `89de182`, `ebd2c5e`

### Decisions

- **World as location graph**: `Location`, `LocationEdge`, `LocationGraph` in `core/location.py`. Flat graph on `World.location_graph`. ~40 locations for sword_vale.
- **Entity.region_id removed**, replaced with `Entity.location_id`. Region derived via `graph.region_of()`.
- **Movement**: `go <location_id>` — adjacent node only. Time = distance / speed with terrain and weather modifiers. Min 1 minute.
- **NPC schedule is computed, not state**: `scheduled_location(hour)`, `scheduled_activity(hour)` — pure functions. `location_override` for combat/dialogue/manual movement. `DEFAULT_SCHEDULE_TEMPLATES` + `resolve_schedule(role, settlement_id)`.
- **`look` filters by location**: `entities_at_location` computes who is where by schedule. Market at 10am → merchant; at 22:00 → empty.
- **Flavor strings**: `activity_flavor(role, activity)` → "hammering at the anvil", "standing watch".
- **Backward compat**: no `locations.yaml` → auto-generate from regions (1 location = 1 region).

### Not implemented (deferred)

- Travel as process with interruptions (random encounters, weather changes, camping on long roads)
- Cartography skill, purchased maps, fast travel
- Automatic `location_override` on conversation start/end

---

## Phase 2 — NPC inner self & awareness DONE

### Goal

NPCs retain a typed inner self. LLM gets delta instead of a full log; RuleBrain reads typed mood and relationships without LLM.

### Decisions

**InnerSelf model** — a core-domain dataclass on persistent NPCs, replacing the former memory fields:

```python
@dataclass
class InnerSelf:
    relations: list[Relationship]
    mood: Mood
    goals: list[TypedGoal | FreeformGoal]
    alignment: AlignmentAccumulation
    journal: str
    thoughts: list[str]
    current_conversation: str  # summary of ongoing conversation
```

Serialized as JSON. Released v1 saves migrate the former fields into `inner_self`.

**Typed core** — relationships are `(target_id, type, intensity)`, mood is a single enum, and goals have an explicit status. RuleBrain reads hates/fears and scared mood in `choose_action()`.

Mood vocabulary: `neutral`, `angry`, `tired`, `happy`, `scared`, `grieving`, `suspicious`, `alerted`. Relationship types: `loves`, `hates`, `trusts`, `fears`, `loyal_to`.

**Delta log instead of full log** — `LlmBrain` sends only new events since last turn (switch from `get_perceived_log` to `get_new_perceived_events` or equivalent with ~15 line cap). Other creatures' `ENTITY_SAY` entries are rendered as heard content, never as instructions.

**Decision prompt and thought** — every decision and reaction tool has an optional `thought` string. A nonempty response is trimmed, bounded, and added to the thoughts ring buffer in the same tool call, never passed to the action handler or sent through a separate LLM call. Peaceful and combat prompts render explicit relationships, non-neutral mood, goals with statuses, journal, and recent thoughts; they omit the raw event buffer, alignment accumulation, and current conversation.

**LLM digest** — `llm/inner_self_digest.py`. At a digest boundary, a creature with `LlmBrain` receives its pre-boundary core, raw structured buffered events, thoughts, allowed target ids, and a rules proposal after the events. Heard events carry an explicit flag and quoted heard wording. It returns a complete strict-validated core plus journal; one enclosing JSON code fence is tolerated, while surrounding prose is rejected. Digest-only timeout and retry limits turn provider failures into the existing rules proposal. RuleBrain and all other creatures digest only through rules and make no LLM call.

**Alignment and free layer** — rules propose and ultimately shift alignment; the LLM may add only `-1..1` evidence per axis. It cannot write thoughts or `current_conversation`; they carry over from the pre-boundary core. The journal is bounded deterministically.

### Implementation order

1. `InnerSelf` model + v1 save migration
2. Typed relationships/mood + RuleBrain reads them in `choose_action()`
3. Delta log — switch LlmBrain to send only new events
4. LLM digest (`llm/inner_self_digest.py`) at the existing entity digest boundaries

### Open questions

- (none currently — all discussed and resolved)

### Deferred to later phases

- Cascade `recent → long_term` (for now single `recent` bucket)
- L2 awakening and batch ticks (Phase 3)
- Trait/personality evolution via LLM (Phase 3)
- Tag metadata (source, expires, intensity)
- RuleBrain writing tags by rules (attacked → `angry`, HP < 25% → `scared`)
- Magic as prompt API (see brainstorm: `magic-as-prompt-api.md`)
- RuleBrain canned dialogue responses

---

## Phase 2.5 — Digest Boundaries + RuleBrain Dialogue

### Goal

Connect digest boundaries to actual game events. Give RuleBrain NPCs minimal dialogue without LLM.

### 2.5a — Digest boundaries DONE

> Implemented in commit `ebac0a6`

**Decisions:**

- Active core-bearers now retain a structured, saveable perception buffer without changing their brain log cursor. One digest entry point is called at combat end, active → dormant, intent completion/interruption, and buffer capacity.
- Combat consumes buffers for the recorded combat participants; it no longer rebuilds events by scanning `_location_log` from `COMBAT_STARTED`.
- Every core-bearer first receives the pure rules digest, including RuleBrain and LlmBrain: attacks on the bearer create or strengthen `hates` and set `angry`; allied deaths set `grieving`; deaths resolve active `kill`/`protect` goals; the bearer's attack on an ally accumulates chaos/evil evidence. Grieving wins over angry. The rules use only core relationships, active protect targets, and optional caller-supplied ally IDs; they do not change combat sides or effective faction relation.
- LlmBrain alone may replace the proposed core and journal through its own client; a rejected completion leaves the complete proposal intact. Every three alignment-evidence steps shift a non-player `Character` one axis step; signed pressure is halved after a shift and capped at a terminal edge. Positive law/chaos pressure means chaos, positive good/evil pressure means evil.
- A failed LLM digest logs `inner_self_llm_digest_rejected` with its validation/provider message after clearing the buffer, so it cannot retry stale events indefinitely.
- `conversation_ended` trigger: deferred (needs conversation detection — manual command or timeout).
- GameService assigns the brain once; the digest reads the client from LlmBrain, so a configured service client does not enable LLM digestion for RuleBrain NPCs.

### 2.5b — RuleBrain canned dialogue DONE

> Implemented in commit (pending)

**Decisions:**

- `CANNED_DIALOGUE` table keyed by `(role, activity)` in `models.py` — 5 roles x 2 activities.
- `MOOD_DIALOGUE` table keyed by inner-self mood — overrides role+activity when present (angry, scared, grieving, suspicious).
- `canned_line(role, activity, mood)` — mood override > role+activity > activity-only > "..." fallback.
- `RuleBrain._peaceful_action()` queries `new_raw_events` (raw Event objects, not translated strings) for `ENTITY_SAY` from someone else. Responds with canned line via `Action(name="say")`.
- `EntitiesLayer.get_new_raw_events()` — peeks at raw events without advancing the index (non-destructive, safe alongside `get_new_perceived_events`).
- `content_loader.parse_npc()` loads `inner_self` from YAML (relationships, mood, goals, alignment, journal, thoughts, conversation).
- Test script: `scripts/test_village_dialogue.py`, test world: `content/worlds/village.yaml`.

**Deferred / future expansion:**
- i18n: wrap canned lines in `_()` for translation
- Relationship overrides: a hate relation to the player → hostile line, a trust relation → friendly line
- Multiple lines per key (random pick)
- Sleeping NPCs: respond only if attacked/shaken, not to speech

---

## Phase 3 — Autonomous Ticks & Trait Evolution (not planned yet)

See brainstorms:
- `brainstorms/npc-lifecycle.md` — L2 triggered ticks, L2+ periodic ticks, NPC tiers
- `brainstorms/game-loop-and-master.md` — three consciousness levels, batch awakening, trait_changes
- `brainstorms/magic-as-prompt-api.md` — spells as CRUD on NPC prompt structure
