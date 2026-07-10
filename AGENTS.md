# AGENTS.md

Guidance for non-Claude coding agents (Codex, etc.) working in this repo. Claude Code reads CLAUDE.md instead; this file points to the same sources of truth — do not duplicate content here.

## Conventions (details in CLAUDE.md)

- Pipe test output to a file and read the file: `make check 2>&1 | tee /tmp/check.log`. Never rerun a suite just to re-read its output.
- Halves: `make check-backend` / `make check-frontend`; the pre-push hook scope-filters via `scripts/classify-scope.sh` (docs-only pushes run nothing).
- Never add `Co-Authored-By` or any AI attribution to commit messages or PR bodies.
- User-visible strings go through gettext `_()`; default locale is RU.
- Dev servers: uvicorn on :8001, vite on :5173. Start detached (`setsid <cmd> > /tmp/x.log 2>&1 &`), kill them when done. Browser E2E runs are serialized on these ports — if you work under a coordinator, ask before running E2E.
- `main` is protected: changes land via PR (merge commits, not squash). Do not merge your own PR unless told to.
- Product vision: [docs/VISION.md](docs/VISION.md) · current state: [docs/STATUS.md](docs/STATUS.md) · simulation model: [docs/brainstorms/simulation-core.md](docs/brainstorms/simulation-core.md) · backlog: [docs/BACKLOG.md](docs/BACKLOG.md).

## Pipeline playbooks (executable checklists)

The sprint pipeline is defined as skill files shared with Claude. Treat each `SKILL.md` as a step-by-step checklist: follow the body, ignore Claude-specific frontmatter (`allowed-tools`, trigger phrases). The flow itself is described in [docs/SPRINT_PIPELINE.md](docs/SPRINT_PIPELINE.md); `docs/STATUS.md` is the single project-state file and must be updated by any step that changes state.

| Request | Checklist |
|---|---|
| plan a new sprint | `.claude/skills/new-sprint/SKILL.md` |
| plan a phase / generate tasks | `.claude/skills/plan-phase/SKILL.md` |
| implement a task | `.claude/skills/implement/SKILL.md` |
| close a phase | `.claude/skills/close-phase/SKILL.md` |
| run E2E | `.claude/skills/e2e/SKILL.md` + [docs/e2e-playbook.md](docs/e2e-playbook.md) |
| audit the codebase | `.claude/skills/audit/SKILL.md` (writes `docs/audit.md`) |
| triage audit findings | `.claude/skills/audit-triage/SKILL.md` |
| close the sprint | `.claude/skills/close-sprint/SKILL.md` |
| sync documentation | `.claude/skills/update-docs/SKILL.md` |

## Claude-specific → generic equivalents

- "run in background" (Claude Bash tool feature) → `setsid <cmd> > /tmp/x.log 2>&1 &`.
- A skill invoking another skill (e.g. `/e2e` inside close-phase) → open that skill's `SKILL.md` and continue with it.
- `AskUserQuestion` / user prompts → if you run under an Orca coordinator, use `orca orchestration ask` and poll for the reply; otherwise stop and report.
