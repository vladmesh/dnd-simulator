# Task: Identity & role resolution seam

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 1 — Identity & role keystone

## Description

Introduce the request-seam that answers "who is calling, in what role" — the other half of the keystone. Minimal weight: header/config-driven, NO passwords/login/DB. The seam is demonstrated on two surfaces: world-create (stamping `creator` from the caller) and session-create (stamping `created_by` into the session save `meta`). Both are attribution only — broad role-gating and access enforcement are Phase 2+.

**Note on `creator` vs access:** `creator`/`created_by` record *who made* a template/session, immutable attribution. They are NOT access control. Who may view/edit/play is a separate dimension deferred to a future many-to-many (user ↔ resource) model, likely DB-backed. Don't bake access semantics into these fields.

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
- Stamp `creator=identity.user_id` (replacing the body-passed creator from task 1 — body `creator` becomes ignored/removed for these routes; the caller's identity is authoritative).

**Wire (session attribution) — session-create route + save path:**

- Thread the resolved `identity.user_id` into `start_game`/session creation and persist it as `meta.created_by` in the session autosave (the `meta` dict already carries `world_name`/`lang` — `created_by` is one more key, forward-compatible like the manifest `creator`). Unenforced this sprint.

**Default-role decision (documented, revisit in Phase 2):** header-less requests resolve to `user_id="local"`, `role=Role.ADMIN` (configurable via env `DND_DEFAULT_ROLE`). Rationale: single-user localhost dev + every existing header-less integration test keeps full access, so Phase 1 introduces the seam with zero regressions. Phase 2 (which adds real per-role scoping) tightens this and makes role explicit in its tests.

## Tests First

Unit on the resolver + route-level on the seam:

- **Role parsing:** `resolve_identity("alice", "dm")` → `Identity("alice", Role.DM)`; `resolve_identity("alice", "worldbuilder")` → `Role.WORLDBUILDER`.
- **Invalid role rejected:** `resolve_identity("alice", "wizard")` raises `ValueError`; via HTTP, a world-create with `X-Role: wizard` returns **400** and creates no world.
- **Defaults:** `resolve_identity(None, None)` → `Identity("local", <default role>)`; a world-create with NO identity headers still succeeds (backward compat) and the world's `creator == "local"`.
- **Caller creates the world (end-to-end):** `POST /api/master/worlds` with `X-User-Id: alice` → `GET` manifest/list shows that world `creator == "alice"`.
- **Fork via HTTP re-attributes:** forking a base world over HTTP with `X-User-Id: bob` → new world `creator == "bob"`, source unchanged.
- **Session stamps created_by:** `start_game` under `X-User-Id: alice` → the session autosave `meta.created_by == "alice"` (attribution only, no enforcement; access stays open this sprint).

## Implementation

After red: add `service/identity.py`, the `get_identity` dependency, and wire it into the three world-write routes. The creator now flows from identity, not the request body (task 1's body `creator` was a stepping stone). Confirm existing integration tests (header-less) still pass against the default identity.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check` / integration)
- [ ] `Role`/`Identity`/`resolve_identity` live in `service/identity.py`; header parsing in `deps.py` (adapter), validation pure in service
- [ ] Invalid `X-Role` → HTTP 400, no side effect
- [ ] World-create/fork stamp `creator` from the resolved caller identity
- [ ] Session-create stamps `meta.created_by` from the resolved caller identity (attribution, unenforced)
- [ ] Default identity policy documented in code + sprint Decisions

## Status

`pending`
