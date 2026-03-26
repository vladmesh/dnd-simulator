---
name: clean
description: Kill the dev stack, wipe accumulated artifacts (saves, logs, screenshots), and kill any hanging processes on backend/frontend ports or MCP Playwright sessions. Use when the user says "clean", "clean up", "wipe", "reset environment", "kill everything", "убери мусор", "почисти", or wants a fresh dev environment before starting new work.
---

# Clean

Nuke all accumulated dev artifacts and hanging processes. Leave the repo in a clean state ready for a fresh run.

## What to clean

### 1. Processes (kill first, clean files second)

**Backend (port 8001):**
```bash
fuser -k 8001/tcp 2>/dev/null
```

**Frontend (port 5173):**
```bash
fuser -k 5173/tcp 2>/dev/null
```

**MCP Playwright browser sessions:**
Playwright MCP spawns headless Chromium instances that sometimes outlive their parent process. Find and kill them:
```bash
# Kill any playwright/chromium processes owned by the current user
pkill -f 'playwright' 2>/dev/null
pkill -f 'chromium.*--remote-debugging' 2>/dev/null
```

### 2. Artifacts

All paths are relative to the project root.

| Target | What | How |
|--------|------|-----|
| `saves/*` | Session save files | `rm -rf saves/*/` — keeps `.gitkeep` |
| `logs/*` | Session event logs (biggest offender, 100s of MB) | `rm -rf logs/*/` |
| `.playwright-mcp/*.png` | MCP browser screenshots | `rm -f .playwright-mcp/*.png` |
| `.playwright-mcp/*.jpeg` | MCP browser screenshots | `rm -f .playwright-mcp/*.jpeg` |
| `.playwright-mcp/*.log` | MCP console logs | `rm -f .playwright-mcp/*.log` |
Do NOT touch:
- `docs/e2e-reports/` — these are kept intentionally
- `content/worlds/e2e_*` — E2E test worlds, kept intentionally
- `.venv/`, `node_modules/`, cache dirs (`.mypy_cache`, `.pytest_cache`, `.ruff_cache`) — these are expensive to rebuild and not "junk"
- Any committed files — only gitignored artifacts
- `saves/.gitkeep` — keep it

### 3. Verification

After cleanup, verify the environment is actually clean. Report a summary table:

| Check | Status |
|-------|--------|
| Port 8001 | free / was killed |
| Port 5173 | free / was killed |
| Playwright processes | none / N killed |
| saves/ | empty / N files removed |
| logs/ | empty / N dirs removed |
| .playwright-mcp/ | clean / N files removed |

## Execution

Run all cleanup commands in a single pass. Don't ask for confirmation — the whole point of `/clean` is a quick reset. Report what was found and cleaned in the summary table.

If something fails to kill (e.g., permission denied on a port), report it clearly so the user can handle it manually.
