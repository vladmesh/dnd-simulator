# Tabletop battle map — focused browser check

Date: 2026-09-05
Branch: `feat/tabletop-battle-map`

A small CSS perspective view uses the existing battle-map coordinates, server-computed reachable cells and move_to action. A toggle restores the flat grid. Miniatures are decorative CSS shapes, not exported 3D models. No additional dependencies or game-rule changes.

## Validation

- `make check-frontend`: passed, 39 files / 307 tests. Output: `/tmp/dnd-frontend-check.log`.
- `npx vite build`: passed. Output: `/tmp/dnd-vite-build.log`.
- `npm run build`: failed with 33 TypeScript diagnostics in existing ActionBar, Perception, test fixtures and Vite config; no diagnostics in changed files. Existing backlog entry: `tsc-build-test-looseness`. The repository's `tsc --noEmit` command does not validate referenced projects like `tsc -b` does.
- `git diff --check`: passed.

## Live browser scenarios

Used the installed Playwright Node package and local Chromium (the Claude-specific Playwright MCP transport is unavailable). Exercised the actual stack at `http://109.235.67.14:5173` with rule-based NPCs, no LLM calls.

- RU setup: choose Level-up Test Arena, create Fighter with Defense style, enter game — passed.
- Attack practice_thug and enter combat — passed.
- Tabletop enabled by default — passed.
- Click reachable tile and verify authoritative player position changes — passed.
- Toggle to flat view and repeat movement — passed.
- Toggle back and click an enemy miniature: inspect dialog opens — passed.
- Browser pageerror events — none on successful run.
- Narrow viewport (390px): map renders, but existing dashboard scrolling/layout clips the map behind the action bar. Desktop is the validated play surface; this is not a mobile-layout fix.
- Initial run attacking the XP dummy triggered its level-up modal, which prevented access to background buttons; reran against the sturdier practice_thug.

Screenshots: `/tmp/dnd-tabletop.png`, `/tmp/dnd-tabletop-mobile.png`.

## Running stack

Left running as explicitly requested:

- Backend: `127.0.0.1:8001`, log `/tmp/dnd-backend.log`.
- Frontend: `0.0.0.0:5173`, log `/tmp/dnd-frontend.log`; proxies API and WebSocket to the backend.
- Entry: `http://109.235.67.14:5173/play`.
- HTTP page and proxied health endpoint return 200 via the server's public IP. Browser session creation and combat used that same address. Access from the user's own network has not been independently tested.

This is a running development preview, not a reboot-persistent production service.

## Follow-up: TypeScript and external access

- The 33 TypeScript diagnostics above were fixed later on 2026-09-05. `npm run build` now passes. Makefile and CI both use `tsc -b`; a temporary invalid application file was correctly rejected by the gate and then removed.
- Full `make check`: 2589 backend tests and 307 frontend tests passed, with lint and type checks. Logs: `/tmp/dnd-types-check-all.log`, `/tmp/dnd-types-build.log`, `/tmp/dnd-typecheck-probe.log`.
- Initial external access failed because UFW allowed only ports 22/80/443. Added a labelled temporary rule for TCP 5173; user confirmed the game opened afterward.
