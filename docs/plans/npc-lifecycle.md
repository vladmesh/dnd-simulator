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

**Delta log instead of full log** — `LlmBrain` sends only new events since last turn (switch from `get_perceived_log` to `get_new_perceived_events` or equivalent with ~15 line cap).

**Summarizer** — `llm/summarizer.py`. It receives InnerSelf JSON and delta events, preserves the typed core, and rewrites only the journal/conversation layer. One cheap LLM call, triggered by `EntitiesLayer` on context change.

Summarizer triggers:
- End of conversation → compress `current_conversation` into `journal`
- End of combat → compress combat events into `journal`
- `journal` exceeds character limit → compress `journal`

**Combat journal** — no summarization during combat. LLM sees a rolling window of ~15 log lines. After combat ends the summarizer writes the outcome to `journal`.

### Implementation order

1. `InnerSelf` model + v1 save migration
2. Typed relationships/mood + RuleBrain reads them in `choose_action()`
3. Delta log — switch LlmBrain to send only new events
4. Summarizer (`llm/summarizer.py`) + triggers in EntitiesLayer

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

## Phase 2.5 — Wire Summarizer Triggers + RuleBrain Dialogue

### Goal

Connect the summarizer to actual game events. Give RuleBrain NPCs minimal dialogue without LLM.

### 2.5a — Summarizer triggers DONE

> Implemented in commit `ebac0a6`

**Decisions:**

- `EntitiesLayer` gets optional `summarizer: MemorySummarizer | None`, injected at construction. `None` = skip summarization.
- Active core-bearers now retain a structured, saveable perception buffer without changing their brain log cursor. One digest entry point is called at combat end, active → dormant, intent completion/interruption, and buffer capacity.
- Combat consumes buffers for the recorded combat participants; it no longer rebuilds events by scanning `_location_log` from `COMBAT_STARTED`.
- The current digest body remains NPC journal summarization, then calls `needs_compression()` for `journal_overflow`; non-NPC core-bearers consume the buffer as a no-op pending the rules digest.
- A failed summarizer call logs `inner_self_digest_failed` after clearing the buffer, so it cannot retry stale events indefinitely.
- `conversation_ended` trigger: deferred (needs conversation detection — manual command or timeout).
- Both `cli.py` (GameService) and `cli_loop.py` inject summarizer when LLM is configured.
- Integration test script: `scripts/test_arena_summarizer.py`.

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
