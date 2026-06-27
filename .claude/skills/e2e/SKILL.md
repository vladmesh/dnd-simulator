---
name: e2e
description: >
  Run E2E regression tests via Playwright against the live app. Follows the playbook in docs/e2e-playbook.md
  plus auto-discovered scenarios from recent changes. Writes a report to docs/e2e-reports/. Use when user
  says "e2e", "run e2e", "regression", "test everything", "full test", "smoke test", or wants to validate
  the app works end-to-end. By default skips LLM scenarios; pass --with-llm to include them.
  Can also be invoked by other skills (close-phase, close-sprint) as part of their workflow.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Agent, mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_click, mcp__playwright__browser_fill_form, mcp__playwright__browser_press_key, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_console_messages, mcp__playwright__browser_wait_for, mcp__playwright__browser_evaluate, mcp__playwright__browser_tabs, mcp__playwright__browser_navigate_back, mcp__playwright__browser_select_option, mcp__playwright__browser_hover
argument-hint: "[--with-llm] [--section N[,N...]]"
---

# E2E Regression Test

Run end-to-end regression tests through the real UI using Playwright. Tests follow the playbook plus auto-discovered scenarios from recent changes.

## Arguments

- `--with-llm` — include section 8 (LLM scenarios). Burns tokens, use when changes touched LLM behavior.
- Without this flag, section 8 is skipped (default).
- `--section N[,N...]` — run only specific playbook sections (e.g. `--section 3,4` for combat + class features). Useful for targeted testing.
- `--context LABEL` — label for the report filename and title (e.g. `sprint017-phase3`). Defaults to `regression`.
- `--report PATH` — write the report to PATH instead of the default `docs/e2e-reports/<date>-<context>.md`. Used by `/close-phase` for its per-phase report.

## Protocol

### 1. Read the playbook

Read `docs/e2e-playbook.md`. This is the regression baseline — every scenario here gets tested unless filtered by `--section`.

Unless `--with-llm` was passed: skip section 8 entirely.

### 2. Auto-discover recent changes

Find the date of the last E2E report:

```bash
ls -t docs/e2e-reports/*.md 2>/dev/null | head -1
```

If a previous report exists, read its date. Then check what changed since:

```bash
git log --oneline --since="<last_report_date>" --name-only
```

From changed files, identify areas that might need additional testing beyond the playbook:

- Changes in `rules/` → test the specific mechanic
- Changes in `adapters/api/` → test the affected endpoints through UI
- Changes in `layers/` → test world behavior (time, settlements, NPCs)
- Changes in `frontend/` → test the affected UI components
- Changes in `content/` → test with the modified world

Add ad-hoc scenarios for changed areas. These supplement the playbook, not replace it.

### 2b. Verify Playwright MCP is available

Before starting the stack, confirm that Playwright MCP tools are accessible:

```
ToolSearch: query="+playwright", max_results=3
```

If tools like `mcp__playwright__browser_navigate` are returned — proceed.

**If no Playwright tools are found — this is a BLOCKER. Do NOT proceed.**

Playwright MCP is installed as a Claude Code plugin (`@playwright/mcp`). If it disconnected mid-session, it cannot be restarted without restarting the Claude Code session itself.

Action when Playwright is unavailable:
1. Stop immediately. Do NOT run E2E without browser testing.
2. Tell the user: "Playwright MCP is not available. Restart the Claude Code session (`/exit` then re-launch) and re-run the skill."
3. Do NOT write an E2E report without browser testing.

### 3. Start the stack

First confirm Playwright MCP is available:

```
ToolSearch: query="+playwright", max_results=3
```

If no `mcp__playwright__browser_*` tools are returned, **stop — this is a blocker.** Playwright MCP can't be restarted mid-session; tell the user to restart Claude Code (`/exit` then re-launch) and re-run. Do NOT write a report without browser testing.

Kill any running instances and start fresh with full debug:

```bash
# Kill existing processes
pkill -f 'uvicorn.*dnd_simulator' 2>/dev/null
pkill -f 'vite' 2>/dev/null
sleep 2

# Start backend with debug logging
mkdir -p /tmp/dnd-e2e-logs
LOG_LEVEL=DEBUG LOG_DIR=/tmp/dnd-e2e-logs nohup uv run uvicorn dnd_simulator.adapters.api.app:app --host 0.0.0.0 --port 8001 --reload --reload-exclude 'saves/*' > /tmp/dnd-e2e-backend.log 2>&1 &
echo $! > /tmp/dnd-e2e-backend.pid

# Start frontend
cd frontend && nohup npx vite --host 0.0.0.0 --port 5173 > /tmp/dnd-e2e-frontend.log 2>&1 &
echo $! > /tmp/dnd-e2e-frontend.pid
cd ..

# Wait for readiness
sleep 5
```

Verify both are up:

```bash
curl -s http://localhost:8001/health && echo " backend OK"
curl -s http://localhost:5173/ > /dev/null && echo " frontend OK"
```

If either fails — check logs, fix, retry. Don't proceed with a broken stack.

### 4. Run scenarios

Your job is to find problems, not to confirm the app works. Approach every screen like a paranoid QA engineer who gets paid per bug found. The playbook tells you what to do — but noticing what's wrong on each screen is your responsibility, not the playbook's.

Work through each playbook scenario (filtered by `--section` and `--no-llm`). For each scenario:

1. **State what you're testing** and what you expect
2. **Execute** via Playwright MCP tools (navigate, click, fill, snapshot)
3. **Inspect the snapshot thoroughly** — this is the critical step. Don't just check "did the expected thing appear". Scrutinize everything visible on the screen:
   - **Text content:** Are all strings in the correct language? Any raw IDs, enum values, or keys leaking into the UI? Any typos, broken encoding, or placeholder text left in?
   - **Data correctness:** Do numbers make sense? Are HP, AC, damage, gold values consistent with what should be there? Do calculated values match expectations (armor + DEX + bonuses = displayed AC)?
   - **Formatting:** Are log entries properly formatted? Do dice rolls show the full breakdown? Are timestamps, dates, names displaying correctly?
   - **UI state:** Are buttons that should be disabled actually disabled? Are panels that should be visible/hidden in the right state? Any visual elements that look out of place, duplicated, or missing?
   - **Consistency:** If the UI language is RU, is everything in RU — including log messages, toasts, item names, damage types, action names? Mixed languages = finding.
   - **Edge cases on screen:** Anything weird in adjacent panels you weren't specifically testing? An NPC list that seems off, a stale value, a tooltip that doesn't make sense?
4. **Record** the result: pass / fail / partial
5. **Record every anomaly** — even if the primary scenario "passed", any deviation from expected behavior is a finding. Don't save it for later, don't minimize it, write it into the scenario notes immediately.
6. **If failed** — take a screenshot, check console messages, note the error

The difference between a useful E2E and a rubber-stamp one: a rubber-stamp looks at the snapshot and asks "is the button there?" A real QA looks at the snapshot and reads every word on the screen.

For scenarios that need a fresh session (combat, class features), create one via the setup flow or API before testing.

**Important:** Don't test LLM-brain NPCs unless `--with-llm` was passed. When interacting with NPCs in rule-based mode, expect canned responses, not creative dialogue.

#### Quick fixes

If a failure is clearly a small bug fixable in <5 minutes:
- Fix it
- Re-run just that scenario
- Note the fix in the report

If it's bigger — note as a finding and move on. Don't spend E2E time debugging.

### 5. Check logs

After all scenarios:

```bash
# Check for errors in backend logs
grep -i 'error\|exception\|traceback' /tmp/dnd-e2e-backend.log | tail -20

# Check structured logs for warnings
ls /tmp/dnd-e2e-logs/
```

Read any log files that look relevant. Note silent errors — things that didn't show in the UI but appeared in logs.

### 6. Write the report

Create the report at `--report PATH` if it was provided, otherwise `docs/e2e-reports/<date>-<context>.md` (e.g. `2026-03-25-regression.md` or `2026-03-25-sprint003-phase2.md`):

```markdown
# E2E Report: <context>

**Date:** <today>
**Flags:** --no-llm | --llm
**Sections tested:** all | 1,3,5
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: N tested, M passed, K failed
- Quick fixes: N applied
- Blockers: N found

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Create character and enter game | pass | |
| 1.2 | Language toggle | pass | |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception — nearby entities | pass | |
| ... | ... | ... | ... |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| <what was tested> | <what changed> | pass/fail | |

## Quick Fixes

- <description of fix, file:line>

## Findings

### Blockers
- <serious issues>

### Minor
- <suboptimal behavior, cosmetic issues, edge cases>

## Log Analysis

- <notable warnings/errors from debug logs>
```

### 7. Cleanup

```bash
# Kill the stack
kill $(cat /tmp/dnd-e2e-backend.pid 2>/dev/null) 2>/dev/null
kill $(cat /tmp/dnd-e2e-frontend.pid 2>/dev/null) 2>/dev/null
rm -f /tmp/dnd-e2e-backend.pid /tmp/dnd-e2e-frontend.pid
```

### 8. Report to user

```
E2E: <context>
  Tested: N scenarios (M from playbook, K auto-discovered)
  Passed: N
  Failed: N
  Quick fixes: N
  Blockers: N
  Report: docs/e2e-reports/<filename>.md
```

If there are blockers — list them. If clean — say so.
