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

## Phase 2 — NPC Memory & Awareness MVP DONE

### Goal

NPCs remember what happened. LLM gets delta instead of full log. Structured tags enable RuleBrain reactions without LLM.

### Decisions

**NpcMemory model** — new dataclass on `Npc`, replaces `conversation_summary`:

```python
@dataclass
class NpcMemory:
    tags: list[str]            # ["grieving", "hates:orcs", "trusts:player"]
    recent: str                # compressed recent events
    inner_state: str           # "worried about family"
    current_conversation: str  # summary of ongoing conversation
```

Serialized as JSON. `conversation_summary` field migrated into `memory.current_conversation`.

**Structured tags** — flat enum-like strings. Relationships via `:creature_id`. ~15 base tags. RuleBrain reads them in `choose_action()`. Only LLM writes tags (for MVP).

Base tag vocabulary:
- Emotions: `angry`, `tired`, `happy`, `scared`, `grieving`, `suspicious`, `alerted`
- Relations: `loves:<id>`, `hates:<id>`, `trusts:<id>`, `fears:<id>`, `loyal_to:<id>`
- Situational: `in_mourning`, `fleeing`

**Delta log instead of full log** — `LlmBrain` sends only new events since last turn (switch from `get_perceived_log` to `get_new_perceived_events` or equivalent with ~15 line cap).

**Summarizer** — `llm/summarizer.py`. Pure function: takes current `NpcMemory` JSON + delta events → returns updated `NpcMemory` JSON. One cheap LLM call. Triggered by `EntitiesLayer` on context change.

Summarizer triggers:
- End of conversation → compress `current_conversation` into `recent`
- End of combat → compress combat events into `recent`
- `recent` exceeds character limit → compress `recent`

**Combat memory** — no summarization during combat. LLM sees rolling window of ~15 log lines. After combat ends → summarizer writes outcome to `recent`. Long combats: old lines fall out of window, but summarizer captures the result.

### Implementation order

1. `NpcMemory` model + migrate `conversation_summary` → `memory`
2. Tag vocabulary enum + RuleBrain reads tags in `choose_action()`
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
- `_on_combat_ended(location_id)` triggers when combat ends — detected in `end_combat_round()` (idle timeout) and `handle_event()` (last fighter killed/fled).
- Scans `_location_log` backward to find `COMBAT_STARTED`, extracts `turn_order` for participant list.
- Each NPC participant gets combat events perceived from their own POV via `perceive_event`.
- After summarization, checks `needs_compression()` → second call with `"recent_overflow"` if needed.
- `conversation_ended` trigger: deferred (needs conversation detection — manual command or timeout).
- Both `cli.py` (GameService) and `cli_loop.py` inject summarizer when LLM is configured.
- Integration test script: `scripts/test_arena_summarizer.py`.

### 2.5b — RuleBrain canned dialogue DONE

> Implemented in commit (pending)

**Decisions:**

- `CANNED_DIALOGUE` table keyed by `(role, activity)` in `models.py` — 5 roles x 2 activities.
- `MOOD_DIALOGUE` table keyed by mood tag — overrides role+activity when present (angry, scared, grieving, suspicious).
- `canned_line(role, activity, tags)` — mood override > role+activity > activity-only > "..." fallback.
- `RuleBrain._peaceful_action()` queries `new_raw_events` (raw Event objects, not translated strings) for `ENTITY_SAY` from someone else. Responds with canned line via `Action(name="say")`.
- `EntitiesLayer.get_new_raw_events()` — peeks at raw events without advancing the index (non-destructive, safe alongside `get_new_perceived_events`).
- `content_loader.parse_npc()` now loads `memory` from YAML (tags, recent, inner_state, current_conversation).
- Test script: `scripts/test_village_dialogue.py`, test world: `content/worlds/village.yaml`.

**Deferred / future expansion:**
- i18n: wrap canned lines in `_()` for translation
- Relationship overrides: `hates:player` → hostile line, `trusts:player` → friendly line
- Multiple lines per key (random pick)
- Sleeping NPCs: respond only if attacked/shaken, not to speech

---

## Phase 3 — Autonomous Ticks & Trait Evolution (not planned yet)

See brainstorms:
- `brainstorms/npc-lifecycle.md` — L2 triggered ticks, L2+ periodic ticks, NPC tiers
- `brainstorms/game-loop-and-master.md` — three consciousness levels, batch awakening, trait_changes
- `brainstorms/magic-as-prompt-api.md` — spells as CRUD on NPC prompt structure
