---
name: audit
description: Scan the dnd_simulator codebase for dead code, code smells, security issues, architecture violations, and test gaps. Creates/updates docs/audit.md with actionable findings. Use when user says "audit", "scan", "check code quality", "check architecture", or wants to find layer dependency violations, impure rules, missing tests, or drift from design principles in CLAUDE.md.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: "[--scope <path>]"
---

# Code Audit

Scan the codebase for issues that violate the project's design principles and D&D 5e simulator conventions. The goal is to catch architectural drift early — the kind of thing that compiles and works but slowly erodes the layered design.

## Key References
- `CLAUDE.md` — architecture, conventions, dependency flow (source of truth)
- `src/dnd_simulator/core/layer.py` — Layer ABC interface

## Input

- `--scope <path>` — limit audit to a specific directory (e.g. `rules/`). Default: full codebase.

## Protocol

### 1. Scan

Work through each category. Use the grep patterns provided — they exist to make the scan concrete and reproducible rather than vibes-based.

---

#### Dead Code

Unused imports are caught by ruff, so focus on what the linter misses:

```bash
# Run linter to catch unused imports
cd /home/vlad/projects/dnd_simulator && uv run ruff check src/ --select F401
```

**Functions/classes with zero callers** — check definitions against usage. Start with files that feel like they might have accumulated dead weight (utility modules, old helpers):

```bash
# Find all function/method definitions, then spot-check callers
rg -n '^def \w+|^    def \w+' src/dnd_simulator/ --type py
```

For each non-dunder, non-test function: grep for its name. Zero hits outside the definition = dead code.

**Files not imported anywhere:**

```bash
# List all .py files, then check which ones are never imported
rg -l 'from dnd_simulator' src/ --type py
```

Cross-reference: any `.py` file under `src/dnd_simulator/` that isn't `__init__.py` and isn't imported or referenced anywhere is a candidate. Pay special attention to standalone entry points (`if __name__ == "__main__"` guards) — if nothing else in the codebase imports the module, it may be orphaned infrastructure from an older transport or workflow.

**Stale TODOs:**

```bash
rg -n 'TODO|FIXME|HACK|XXX' src/ --type py
```

Check if any reference completed work or are no longer relevant.

---

#### Code Smells

```bash
# Files over 400 lines (Python)
find src/dnd_simulator -name '*.py' -exec wc -l {} + | sort -rn | head -20

# Files over 400 lines (JavaScript)
find src/dnd_simulator -name '*.js' -exec wc -l {} + | sort -rn | head -20

# Functions over 50 lines — look for long def blocks
rg -n '^def \w+|^    def \w+' src/dnd_simulator/ --type py
```

For functions that look long, read them and count lines. Also watch for:
- Deeply nested code (> 3 indent levels inside a function)
- Copy-paste patterns (similar logic repeated across files)
- `# noqa` comments that could be fixed instead of suppressed

**Frontend code smells** — the vanilla JS frontend (`adapters/api/static/js/`) doesn't have a linter, so check manually:

```bash
# Large JS functions (look for function/async function definitions, then check length)
rg -n 'function \w+|async function \w+|const \w+ = (?:async )?\(' src/dnd_simulator/adapters/api/static/js/

# Dead JS functions — defined but never called
rg -n 'function \w+' src/dnd_simulator/adapters/api/static/js/
```

For each JS function, grep for its name across all `.js` and `.html` files. Zero hits outside the definition = dead code.

---

#### Security

Three risk surfaces: secrets/subprocess, the REST+WebSocket API, and the frontend.

**Secrets & subprocess:**

```bash
# Hardcoded secrets, tokens, API keys
rg -ni 'api_key|secret|password|token' src/ --type py --glob '!**/tests/**'

# Check that .env is gitignored
cat .gitignore | grep -q '.env' && echo "OK: .env gitignored" || echo "WARNING: .env not in .gitignore"

# Unsafe subprocess calls
rg -n 'subprocess\.(call|run|Popen)' src/ --type py
```

Flag any hardcoded credential values (not just variable names referencing env vars — those are fine).

**CORS & origin validation:**

```bash
# Check if CORSMiddleware is registered and how it's configured
rg -n 'CORSMiddleware' src/dnd_simulator/adapters/api/ --type py -A5
```

If `allow_origins=["*"]` is used — flag it. For local dev it's OK, but note that it should be locked down before any non-local deployment.

**WebSocket security** — the WS endpoint at `/api/ws/{session_id}` is the primary game transport. It accepts arbitrary JSON from the client and runs game logic in a background thread:

```bash
# Check WS message validation — is incoming JSON validated or blindly trusted?
rg -n 'json\(\)|\.get\(|data\[' src/dnd_simulator/adapters/api/routes_ws.py

# Check for rate limiting or message size limits on WS
rg -n 'rate|limit|max.*size|max.*length|throttl' src/dnd_simulator/adapters/api/ --type py

# Check WS origin validation
rg -n 'origin|Origin' src/dnd_simulator/adapters/api/ --type py
```

Things to flag:
- No validation of message structure before dispatching (a malformed message could crash the handler)
- No rate limiting on incoming messages (a client can spam and overwhelm the server)
- No origin checking on WS upgrade (any page can connect)
- Session ID in the URL without auth — can another client hijack a session?

**LLM prompt injection** — user-supplied text (player actions, `say` command, NPC personality via PATCH) flows into LLM prompts. Check that user input is not interpolated into system prompts without separation:

```bash
# Find where user text enters LLM prompts
rg -n 'system.*\{|f".*\{.*user|f".*\{.*text|f".*\{.*action' src/dnd_simulator/llm/ --type py
```

Use judgment: passing user text as a clearly delineated user-message field is fine. Interpolating it directly into system prompt strings is a risk.

**Input bounds validation** — numeric fields accepted via API (HP, population, wealth, hours) should have reasonable bounds. Check Pydantic models for missing `ge=`, `le=`, `Field(gt=0)` constraints:

```bash
# Pydantic models with bare int/float fields (no Field constraints)
rg -n 'hp:|population:|wealth:|hours:|ac:' src/dnd_simulator/adapters/api/schemas.py
```

Flag fields that accept arbitrary values where negative or extreme numbers make no game sense.

**Frontend XSS** — the vanilla JS frontend renders server responses into the DOM. Check for unsafe patterns:

```bash
# innerHTML with dynamic content (potential XSS)
rg -n 'innerHTML' src/dnd_simulator/adapters/api/static/ --type js

# Check if any user-controlled data flows into innerHTML
# Safe: innerHTML with static HTML templates
# Unsafe: innerHTML with server response data or user input without escaping
rg -n 'innerHTML.*\$\{|innerHTML.*\+' src/dnd_simulator/adapters/api/static/ --type js
```

For each `innerHTML` hit, trace the data source: if it comes from a WebSocket message, REST response, or user input field without escaping, it's an XSS vector. Using `textContent` for user-controlled strings is the safe alternative.

---

#### Architecture Violations

This is the most project-specific category. The layered architecture has clear rules in CLAUDE.md — violations are things that work today but will cause pain as the codebase grows.

**Cross-layer imports** — layers must not import from each other. Each layer depends on `core/` only:

```bash
# Any layer importing from another layer is a violation
rg -n 'from dnd_simulator\.layers\.' src/dnd_simulator/layers/ --type py
```

Then check each hit: importing from your *own* layer package (e.g. `entities/layer.py` importing from `entities/models.py`) is fine. Importing from a *different* layer (e.g. `entities` importing from `settlements`) is a violation.

**Dependency flow violations** — the dependency arrow points: core → layers → round/service → adapters. Anything going backwards is wrong:

```bash
# core/ should not import from layers/, service, round, or adapters
rg -n 'from dnd_simulator\.(layers|service|round|adapters)' src/dnd_simulator/core/ --type py

# rules/ should not import from anything except stdlib and core models
rg -n 'from dnd_simulator\.(layers|service|round|adapters|llm|storage)' src/dnd_simulator/rules/ --type py

# adapters should not import from layers directly
rg -n 'from dnd_simulator\.layers' src/dnd_simulator/adapters/ --type py
```

**Impure rules** — functions in `rules/` must be pure: no state, no I/O, no network calls, no file access. They take data in, return data out.

```bash
# I/O and state in rules/ (should be zero hits)
rg -n 'import os|import sys|import json|open\(|print\(' src/dnd_simulator/rules/ --type py
rg -n 'import requests|import httpx|import aiohttp' src/dnd_simulator/rules/ --type py
rg -n 'self\.' src/dnd_simulator/rules/ --type py
```

`self.` hits in rules/ suggest a class with state — rules should be standalone functions, not methods on stateful objects. (Dataclass methods that just compute from their own fields are fine.)

**LLM instantiation outside injection points** — layers and rules should receive an LlmClient, never create one:

```bash
# Direct LlmClient construction (should only happen in service/adapters/content_loader)
rg -n 'LlmClient\(' src/dnd_simulator/ --type py
```

If `LlmClient(` appears in `layers/` or `rules/`, that's a violation.

**Thick adapter** — per CLAUDE.md, adapters only translate I/O; all logic lives in `GameService`. This applies to both REST routes and the WebSocket handler:

```bash
# Route files importing from core/layers/rules (should go through service)
rg -n 'from dnd_simulator\.(core|layers|rules)\.' src/dnd_simulator/adapters/ --type py
```

Importing Pydantic schemas or the service itself is fine. Importing `Character`, layer models, or rule functions means the adapter is doing business logic.

Check all route files *and* `routes_ws.py` for inline logic — things like game-state queries, conditional branching, or direct layer manipulation that should live in the service layer. The WS handler is the most likely place for this to creep in because it bridges threading/async and the temptation to reach into layers directly is strong.

**Threading safety** — the WebSocket adapter runs `Round.run_loop()` in a background thread while the main async event loop handles WS I/O. Shared mutable state between these two is a race condition risk:

```bash
# Check how the background thread communicates with async code
rg -n 'run_coroutine_threadsafe|Thread\(|threading' src/dnd_simulator/adapters/ --type py

# Check for shared mutable state accessed from both threads
rg -n 'self\._|self\.world|self\.session' src/dnd_simulator/adapters/api/routes_ws.py
```

Things to flag:
- Direct mutation of session/world state from async handlers while the Round thread is running
- Missing locks around shared state
- Callbacks that capture mutable closures without synchronization

**Hardcoded game data that belongs in YAML** — content like NPC names, town descriptions, quest text should live in `content/`, not in Python code:

```bash
# Large string literals in layer code (potential hardcoded content)
rg -n '"""' src/dnd_simulator/layers/ --type py -A1
```

Use judgment: prompt templates are fine, but narrative content (descriptions, dialogue) belongs in YAML.

---

#### Convention Violations

These come directly from the Code Style section of CLAUDE.md.

**Mutable dataclasses where frozen is expected:**

```bash
# Dataclasses without frozen=True
rg -n '@dataclass$' src/dnd_simulator/ --type py
rg -n '@dataclass\(' src/dnd_simulator/ --type py | grep -v 'frozen=True'
```

Models should use `@dataclass(frozen=True)`. Mutable dataclasses are OK only for explicitly stateful objects (like `CombatState`, `GameSession`, entities with HP/position).

**`Any` type usage instead of `object`:**

```bash
# Any in type annotations (should use object for strict mypy)
rg -n ': Any|-> Any|\[Any\]' src/dnd_simulator/ --type py
rg -n 'from typing import.*Any' src/dnd_simulator/ --type py
```

Per CLAUDE.md: use `object` (not `Any`) in state dicts for mypy strict.

**Line length violations:**

```bash
# Lines over 120 chars
rg -n '.{121,}' src/dnd_simulator/ --type py | head -20
```

---

#### Layer Contract Compliance

Every layer must implement the Layer ABC fully. Quick sanity check:

```bash
# Find all Layer subclasses
rg -n 'class \w+.*Layer.*:' src/dnd_simulator/layers/ --type py
```

For each, verify it implements: `name`, `tick_interval`, `tick`, `handle_event`, `query`, `get_state`, `load_state`. Mypy should catch missing methods, but the audit can flag incomplete implementations that pass type checking (e.g. `handle_event` that always returns None without inspecting the event).

---

#### Test Gaps

```bash
# Source files without corresponding tests
ls src/dnd_simulator/rules/*.py | sed 's|src/dnd_simulator/||;s|\.py||;s|/|_|g' | while read mod; do
  [ -f "tests/test_${mod}.py" ] || echo "MISSING: tests/test_${mod}.py"
done

# Skipped tests
rg -n '@pytest.mark.skip|@pytest.mark.xfail' tests/ --type py

# Layer files without tests
for layer in geography politics settlements entities; do
  [ -f "tests/test_${layer}_layer.py" ] || echo "MISSING: tests/test_${layer}_layer.py"
done

# API, WebSocket, and service tests
for mod in api ws; do
  [ -f "tests/test_${mod}.py" ] || echo "MISSING: tests/test_${mod}.py"
done
```

**WebSocket test coverage** — the WS handler (`routes_ws.py`) is the most complex adapter and the primary game transport. Check that `test_ws.py` covers more than just connection:

```bash
# What WS scenarios are tested?
rg -n 'def test_|async def test_' tests/test_ws.py
```

Flag if any of these are missing:
- Connection and basic message exchange
- Malformed/invalid messages from client
- Session not found / invalid session_id
- Disconnect during active game loop

---

### 2. Write Report

Write/overwrite `docs/audit.md`:

```markdown
# Code Audit

> **Date**: <today>
> **Scope**: <full | path>

## Summary
- Dead code: N issues
- Code smells: N issues
- Security: N issues
- Architecture violations: N issues
- Convention violations: N issues
- Layer contract: N issues
- Test gaps: N issues

## Dead Code
| File | Issue | Action |
|------|-------|--------|
| ... | ... | remove / backlog / ignore (reason) |

## Code Smells
| File | Issue | Suggestion |
|------|-------|------------|
| ... | ... | ... |

## Security
| File:Line | Issue | Severity |
|-----------|-------|----------|
| ... | ... | high/medium/low |

## Architecture Violations
| File:Line | Violation | Should Be | Severity |
|-----------|-----------|-----------|----------|
| `layers/entities/layer.py:15` | imports from `layers.settlements` | use events via `handle_event` | high |

## Convention Violations
| File:Line | Violation | Rule |
|-----------|-----------|------|
| `core/models.py:42` | `@dataclass` without frozen | Use `@dataclass(frozen=True)` |

## Layer Contract
| Layer | Issue |
|-------|-------|
| ... | ... |

## Test Gaps
| Source File | Expected Test | Status |
|-------------|---------------|--------|
| `rules/combat.py` | `tests/test_rules_combat.py` | missing |
```

### 3. Commit

```bash
git add docs/audit.md
git commit -m "audit: <scope> — <N> issues found"
```

Do NOT push — doc-only commits stay local.

### 4. Report

Print to console:
- Total issues found
- Breakdown by category
- Top 3 highest-severity items to address first

---

## Self-Feedback

During your final review, if you encountered any of these — append to `docs/skill-feedback.md`:

- A grep pattern in this skill was wrong or missed real violations
- A category was missing something that should be checked
- A step was ambiguous and led to a wrong first attempt

Format:

```markdown
## [audit] — <today's date>
- **Type**: bug | missing-info | optimization
- **Quote**: "<exact line or section>"
- **Problem**: <what went wrong>
- **Suggested fix**: <concrete change>
```
