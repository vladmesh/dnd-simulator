# Logging Architecture

Structured logging via `structlog` with contextvar-based context propagation, domain tagging, and file dispatch for navigation.

## Quick Start

```bash
# Default: WARNING level, JSON to stderr
make serve

# Debug mode: DEBUG level, pretty console output
LOG_LEVEL=DEBUG make serve

# Debug + file dispatch: writes denormalized JSONL files
LOG_LEVEL=DEBUG LOG_DIR=./logs make serve
```

## Configuration

`logging_config.py` — called once during app lifespan (`adapters/api/app.py`).

| Env var   | Effect                                                        |
|-----------|---------------------------------------------------------------|
| `LOG_LEVEL` | Verbosity: DEBUG, INFO, WARNING (default), ERROR, CRITICAL. Pretty console when DEBUG + TTY. |
| `LOG_DIR`   | Enable file dispatch — denormalized JSONL per session/domain  |

Processor chain: `merge_contextvars → add_log_level → timestamp → [file_dispatch] → renderer`

## Domains

Every logger is tagged with a `domain` for routing and filtering:

| Domain            | Module                        | What it logs                                      |
|-------------------|-------------------------------|---------------------------------------------------|
| `llm`             | `llm/client.py`               | API requests, tool calls, responses, errors        |
| `llm.brain`       | `llm/brain.py`                | NPC turn start, mode (peaceful/combat)             |
| `llm.context`     | `llm/client.py`               | Full prompt + response (debug, file dispatch only) |
| `llm.summarizer`  | `llm/summarizer.py`           | Memory summarization calls                         |
| `brain`           | `core/brain.py`               | RuleBrain decisions (target selection, actions)     |
| `action`          | `rules/action_handlers.py`    | Action execution (attack, move, say, equip, etc.)  |
| `combat`          | `layers/entities/combat_manager.py` | Combat start/end, attack resolution, movement |
| `round`           | `round.py`                    | Round lifecycle, turn budget, awareness             |
| `entity`          | `layers/entities/layer.py`    | Activation, queries, NPC memory updates             |
| `session`         | `service/session.py`          | Session lifecycle, listeners, round thread          |
| `transport`       | `adapters/api/routes_ws.py`   | WebSocket connect/disconnect                        |
| `world`           | `core/world.py`               | Time advancement                                    |

## Context Propagation

Uses `structlog.contextvars` for automatic context binding across the call stack:

- **Session-level**: `session_id` — bound in `GameSession._bind_session_context()`, called at entry of every public session method. Propagated to the round thread via `contextvars.copy_context()`.
- **Creature-level**: `entity_id`, `entity_name`, `phase` (combat/peaceful), `location_id` — bound via `structlog.contextvars.bound_contextvars()` in `Round.run_creature_turn()`, auto-reverts when the turn ends.

Every log entry within a creature's turn automatically includes session, entity, and location context without explicit passing.

## File Dispatch

When `LOG_DIR` is set, `FileDispatchProcessor` writes each log entry to multiple denormalized JSONL files based on domain and context. This enables fast navigation — open the right file instead of grepping.

### Directory Structure

```
logs/
  session_{id}/
    full.jsonl                    # Everything for this session
    llm/
      all.jsonl                   # All LLM calls
      {entity_id}.jsonl           # LLM calls for one NPC
      contexts/
        {entity}_{time}.json      # Full prompt + tools + response (one file per call)
    entities/
      {entity_id}.jsonl           # All logs mentioning this entity
    combat/
      summary.jsonl               # combat_start / combat_end events
    actions/
      all.jsonl                   # All action executions
      failed.jsonl                # Failed actions only
    round/
      all.jsonl                   # round_start, round_end, combat awareness
  session_unknown/
    full.jsonl                    # Logs without session context (e.g. World.advance_time)
```

### Routing Rules

| Condition                          | Target files                                         |
|------------------------------------|------------------------------------------------------|
| Always                             | `full.jsonl`                                         |
| `domain.startswith("llm")`         | `llm/all.jsonl`, `llm/{entity_id}.jsonl`             |
| `entity_id` present                | `entities/{entity_id}.jsonl`                         |
| `domain == "combat"`, start/end    | `combat/summary.jsonl`                               |
| `domain == "action"`               | `actions/all.jsonl`, `actions/failed.jsonl` on error |
| `domain == "round"`                | `round/all.jsonl`                                    |
| `domain == "llm.context"`          | `llm/contexts/{entity}_{time}.json` (separate JSON)  |

### LLM Context Files

Full LLM prompts are large (system prompt + tools schema + response), so they're written as separate pretty-printed JSON files rather than JSONL lines. Each file contains:

```json
{
  "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
  "tools": [...],
  "response_tool": "attack",
  "response_text": null,
  "tokens_in": 721,
  "tokens_out": 35,
  "elapsed_ms": 1285,
  "entity_id": "paladin",
  "session_id": "abc123"
}
```

## Key Log Events

### LLM Lifecycle

```
npc_turn_start     npc=Marta mode=peaceful          # NPC turn begins
llm_request        tools=[say, idle, move, attack]   # API call with available tools
llm_tool_call      tool=say args="text=..." tokens_in=523 tokens_out=74 elapsed_ms=2412
llm_error          elapsed_ms=150 tools=[...]        # API error (401, timeout, etc.)
```

### Combat

```
combat_start       location_id=arena initiative=[(razor, Razor), (paladin, Paladin)]
attack_roll        attacker=Paladin target=Razor weapon=sword modifier=6 advantage=false
attack_result      roll=14 total=20 target_ac=13 outcome=HIT damage=7
combat_end         location_id=arena
```

### Round Lifecycle

```
round_start        game_time=... active_creatures=5 combat_locations=1
combat_turn_start  weapon="sword (grants: [bless])" conditions={blessed: 2}
combat_awareness   actions=[move, attack, dodge] weapon=sword conditions=[blessed]
action_failed      action=move error="Cannot move there — blocked."
round_end          game_time=... tick_events=0
```

## Debugging Workflows

**"Why did the NPC do X?"** — Read `logs/session_{id}/llm/{npc_id}.jsonl` for the sequence of LLM requests and responses. Open the corresponding context file in `llm/contexts/` to see the exact prompt.

**"What happened in combat?"** — Read `logs/session_{id}/combat/summary.jsonl` for start/end, then `actions/all.jsonl` for the blow-by-blow.

**"Why is movement failing?"** — Filter `actions/failed.jsonl` or grep for `action_failed` in `round/all.jsonl`.

**"What does this entity see?"** — Read `entities/{id}.jsonl` — contains all logs where that entity was the active actor, including awareness data.

**"LLM API issues?"** — Grep for `llm_error` in `llm/all.jsonl`. Check `elapsed_ms` for latency issues.
