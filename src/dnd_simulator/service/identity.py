"""Identity & role resolution — the request-seam keystone.

Pure, service-layer. Answers "who is calling, in what role" from already-parsed
inputs (the adapter reads the actual headers). No passwords, no login, no DB —
minimal weight for Sprint 020. `user_id` feeds `creator`/`created_by` attribution;
`role` is carried for the Phase 2 lens projection but not enforced yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

DEFAULT_USER_ID = "local"


class Role(StrEnum):
    WORLDBUILDER = "worldbuilder"
    DM = "dm"
    ADMIN = "admin"
    PLAYER = "player"


@dataclass(frozen=True)
class Identity:
    """Who is calling, in what role."""

    user_id: str
    role: Role


def resolve_identity(
    user_id: str | None,
    role: str | None,
    *,
    default_role: Role = Role.ADMIN,
) -> Identity:
    """Build an Identity from raw (header) values.

    - Blank/None ``user_id`` → ``DEFAULT_USER_ID`` ("local").
    - Blank/None ``role`` → ``default_role``.
    - A non-blank ``role`` that is not a valid :class:`Role` → ``ValueError``
      (the adapter maps this to HTTP 400).
    """
    resolved_user = user_id.strip() if user_id and user_id.strip() else DEFAULT_USER_ID

    if not role or not role.strip():
        return Identity(user_id=resolved_user, role=default_role)

    try:
        resolved_role = Role(role.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid role: {role!r}") from exc
    return Identity(user_id=resolved_user, role=resolved_role)
