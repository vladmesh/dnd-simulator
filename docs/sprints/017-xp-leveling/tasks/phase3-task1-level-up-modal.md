# Task: Level-up modal component + API client

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 3 — Level-up UI + E2E

## Description

Add `LevelUpModal` React component that presents the level-up flow to the player.

- Class-conditional form:
  - **Paladin L1→L2**: required dropdown `fighting_style` (Defense / Dueling / Great Weapon Fighting — values must match backend `FightingStyle` enum).
  - **Fighter L1→L2**: no choice, just a confirmation (highlights Action Surge unlock).
  - **Rogue L1→L2**: no choice, just a confirmation (HP + proficiency bump).
- Header: "Level up to L<N>".
- Body: shows current → next level, HP max delta, new resource pools (Action Surge, spell slots), new features (Fighting Style placeholder for Paladin).
- Footer: Cancel + Confirm. Confirm disabled until required choices filled.
- Calls API via new `apiClient.levelUp(sessionId, { fighting_style? })` method — wraps `POST /api/player/sessions/{id}/level-up`.
- Returns updated `PlayerStatus`; caller decides what to do with it (integration is the next task).

No store wiring, no auto-open logic in this task — pure component + API client. Keep it focused.

## Tests First

Vitest + React Testing Library, mirroring existing patterns (`AttackCardModal.test.tsx`, `SmiteChoice` usage).

Product-level scenarios:

1. **Paladin L1 sees fighting-style dropdown with three options and confirm button is disabled until a style is selected.** Selecting "Dueling" enables confirm.
2. **Fighter L1 sees no dropdown; confirm is enabled immediately and the Action Surge unlock is mentioned in the body.**
3. **Rogue L1 sees no dropdown; confirm is enabled immediately and HP gain is displayed.**
4. **Submitting as Paladin with "Dueling" calls the API client once with `{ fighting_style: "dueling" }`** and invokes `onSuccess` with the returned `PlayerStatus`.
5. **Submitting as Fighter calls the API with no `fighting_style` field** (or `null`) — backend enum must not be confused by empty string.
6. **API error surfaces as an inline error message**, confirm button becomes re-enabled so the player can retry.
7. **Cancel fires `onClose` without calling the API.**

Mock `apiClient.levelUp`. Build `PlayerStatus` fixtures for each class (L1 with `level_up_available: true`).

## Implementation

- New: `frontend/src/components/game/LevelUpModal.tsx` — accepts `{ open, onClose, player, onSuccess }`. Uses `Dialog` from `components/ui/dialog.tsx`. Class branch derived from `player.class`.
- New: `frontend/src/components/game/__tests__/LevelUpModal.test.tsx`.
- Extend: `frontend/src/transport/apiClient.ts` — add `levelUp(sessionId, body)` returning `Promise<PlayerStatus>`. Follow existing method signatures.
- Extend: `frontend/src/types/game.ts` — add `LevelUpRequest` type mirroring backend schema.
- i18n: all user-visible strings via the existing i18n helper. Fighting-style labels match what the backend enum defines; dropdown values are the raw enum values.
- No store changes, no `PlayerStats` changes — those belong in task 2.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] `make check` still passes (backend) and frontend `npm test` passes via make target
- [ ] Modal does not yet appear in the app — only exported
- [ ] API client method is typed end-to-end (no `any`)

## Status

`done`

## Developer Notes

- `apiClient.levelUp` returns `PlayerStatus` (from `types/game.ts`) rather than `PlayerStatusResponse` (api.ts) so the store/WS consumer shape matches without an adapter. Backend response is a structural superset — no runtime issue.
- Modal submits `{}` for Fighter/Rogue (no `fighting_style` key) to avoid sending an empty string the backend would reject when decoding `FightingStyle`.
- HP delta is approximated on the client from class hit-die average + CON mod (Fighter/Paladin d10 → 6, Rogue d8 → 5). Good enough for a pre-confirmation preview; backend remains the source of truth.
- No store wiring / auto-open — that belongs to phase3-task2.
