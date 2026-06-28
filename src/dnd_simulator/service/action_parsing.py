"""Parse a raw transport message into a domain ``Action``.

Keeps the ``Action``/``ActionType`` construction out of the WS adapter so the
adapter never imports from ``core``. The adapter catches ``ActionParseError`` and
renders its own i18n reply using the offending ``name``.
"""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType


class ActionParseError(ValueError):
    """Raised when a raw message names an action that is not a valid ``ActionType``.

    Carries the offending ``name`` so the adapter can echo it in an i18n reply.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Unknown action: {name}")


def parse_action(raw: dict[str, object], *, default_name: str) -> Action:
    """Build an ``Action`` from a raw transport message.

    ``default_name`` is used when the message omits ``name`` (``"idle"`` for
    actions, ``"skip"`` for reactions). An unknown name raises ``ActionParseError``.
    """
    name = str(raw.get("name", default_name))
    try:
        action_type = ActionType(name)
    except ValueError as exc:
        raise ActionParseError(name) from exc
    params = raw.get("params", {})
    if not isinstance(params, dict):
        params = {}
    return Action(name=action_type, params=params)
