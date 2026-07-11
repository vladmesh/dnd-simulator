# Task: Journey status and UI

**Date:** 2026-07-11
**Sprint:** 022-intents-travel
**Phase:** 3 — Travel as an intent

## Description

Expose the player's current travel state through the existing REST and WebSocket player-status contract, and update the location UI to send the first-class travel action. While a journey is active, the UI must show the final destination and route progress; after arrival it must return to the ordinary location/path view with no stale journey state.

All labels and user-visible journey text must use the existing frontend i18n catalogs, with RU as the default locale.

## Tests First

- Starting travel from `LocationPanel` sends `name: "travel"` with a destination parameter, never a zero-hour wait payload.
- A mid-journey status payload identifies the final destination, current leg/progress, and arrival boundary; a completed journey omits active travel state and reports the arrived location.
- The UI renders an in-progress multi-edge journey from status data and switches cleanly to the destination's neighboring paths when the arrival turn is delivered.
- A save/load/reconnect during travel returns the same journey status and allows the UI to continue displaying progress until the one final completion.

## Implementation

Add a compact optional journey view to the shared `PlayerStatusData` contract and its TypeScript counterpart. Build it from the persisted travel intent in `service/session.py`, resolving location IDs to user-facing names at the service boundary. Update `LocationPanel` and focused component/store tests; add English and Russian gettext/i18n entries. Do not make the frontend infer route progress from event-log strings.

Likely files: `service/dto.py`, `service/session.py`, adapter schema tests, `frontend/src/types/game.ts`, `frontend/src/components/game/LocationPanel.tsx`, its tests, and `frontend/src/i18n/locales/{en,ru}/game.json`.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] REST and WebSocket status use one typed journey contract.
- [x] The location UI sends `TRAVEL` and shows persisted multi-leg progress.
- [x] Arrival clears journey presentation and refreshes the visible location paths.
- [x] New user-visible strings are localized in English and Russian.

## Status

`done`

## Developer Notes

`PlayerStatusData` теперь содержит опциональный типизированный journey view с разрешёнными именами текущей
точки, следующей остановки, оставшегося маршрута и финальной цели. REST и все WS round payloads строят его одним
`build_player_status`; после завершения сохранённого intent поле становится `null`. `LocationPanel` отправляет
`travel` с `destination_id`, показывает persisted route и возвращается к обычным путям после arrival update.
