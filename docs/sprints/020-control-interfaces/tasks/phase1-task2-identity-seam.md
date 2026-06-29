# Task: Identity & role resolution seam

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 1 — Identity & role keystone

## Description

Introduce the request-seam that answers "who is calling, in what role" — the other half of the keystone. Minimal weight: header/config-driven, NO passwords/login/DB. The seam exists and is demonstrated on world-create (stamping owner from the caller); broad role-gating is Phase 2.

**Model — `service/identity.py` (new, pure):**

- `Role(StrEnum)`: `WORLDBUILDER`, `DM`, `ADMIN`, `PLAYER`.
- `Identity` (frozen dataclass): `user_id: str`, `role: Role`.
- `resolve_identity(user_id: str | None, role: str | None) -> Identity` — pure constructor/validator:
  - `user_id` blank/None → default `"local"`.
  - `role` blank/None → default role (see decision below).
  - `role` present but not a valid `Role` value → raise a typed error (e.g. `ValueError`) — the adapter maps this to HTTP 400.

**Seam — `adapters/api/deps.py`:**

- `get_identity(request: Request) -> Identity` FastAPI dependency: read headers `X-User-Id` and `X-Role`, call `resolve_identity`, translate its `ValueError` into `HTTPException(400)`.

**Wire (demonstration surface) — `adapters/api/routes_world.py`:**

- Add `identity: Identity = Depends(get_identity)` to `create_world`, `assemble_world`, `fork_world`.
- Stamp `owner=identity.user_id` (replacing the body-passed owner from task 1 — body `owner` becomes ignored/removed for these routes; the caller's identity is authoritative).

**Default-role decision (documented, revisit in Phase 2):** header-less requests resolve to `user_id="local"`, `role=Role.ADMIN` (configurable via env `DND_DEFAULT_ROLE`). Rationale: single-user localhost dev + every existing header-less integration test keeps full access, so Phase 1 introduces the seam with zero regressions. Phase 2 (which adds real per-role scoping) tightens this and makes role explicit in its tests.

## Tests First

Unit on the resolver + route-level on the seam:

- **Role parsing:** `resolve_identity("alice", "dm")` → `Identity("alice", Role.DM)`; `resolve_identity("alice", "worldbuilder")` → `Role.WORLDBUILDER`.
- **Invalid role rejected:** `resolve_identity("alice", "wizard")` raises `ValueError`; via HTTP, a world-create with `X-Role: wizard` returns **400** and creates no world.
- **Defaults:** `resolve_identity(None, None)` → `Identity("local", <default role>)`; a world-create with NO identity headers still succeeds (backward compat) and the world is owned by `"local"`.
- **Caller owns created world (end-to-end):** `POST /api/master/worlds` with `X-User-Id: alice` → `GET` manifest/list shows that world `owner == "alice"`.
- **Fork via HTTP re-owns:** forking a base world over HTTP with `X-User-Id: bob` → new world `owner == "bob"`, source unchanged.

## Implementation

After red: add `service/identity.py`, the `get_identity` dependency, and wire it into the three world-write routes. The owner now flows from identity, not the request body (task 1's body `owner` was a stepping stone). Confirm existing integration tests (header-less) still pass against the default identity.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check` / integration)
- [ ] `Role`/`Identity`/`resolve_identity` live in `service/identity.py`; header parsing in `deps.py` (adapter), validation pure in service
- [ ] Invalid `X-Role` → HTTP 400, no side effect
- [ ] World-create/fork stamp `owner` from the resolved caller identity
- [ ] Default identity policy documented in code + sprint Decisions

## Status

`pending`
