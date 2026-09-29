"""Parse a raw transport message into a domain ``Action``.

Keeps the ``Action``/``ActionType`` construction out of the WS adapter so the
adapter never imports from ``core``. The adapter catches ``ActionParseError`` and
renders its own i18n reply using the offending ``name``.
"""

from __future__ import annotations

from typing import Literal

from dnd_simulator.core.action import Action, ActionType

# Bounds on client-supplied params. ActionDefs declare at most a handful of params, and the longest
# legitimate value is in-character `say` text.
MAX_ACTION_PARAMS = 16
MAX_PARAM_STRING_LENGTH = 2000


class ActionParseError(ValueError):
    """Raised when a raw message names an action that is not a valid ``ActionType``.

    Carries the offending ``name`` so the adapter can echo it in an i18n reply.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Unknown action: {name}")


class ActionParamsError(ValueError):
    """Raised when a raw message carries ``params`` that are not a bounded JSON object.

    ``reason`` is ``"not_object"`` or ``"too_large"``; the adapter renders its own i18n reply.
    """

    def __init__(self, reason: Literal["not_object", "too_large"]) -> None:
        self.reason = reason
        super().__init__(f"Invalid action params: {reason}")


def parse_action(raw: dict[str, object], *, default_name: str) -> Action:
    """Build an ``Action`` from a raw transport message.

    ``default_name`` is used when the message omits ``name`` (``"idle"`` for
    actions, ``"skip"`` for reactions). An unknown name raises ``ActionParseError``; ``params``
    that are not an object with string keys, or exceed the size bounds, raise ``ActionParamsError``.
    """
    name = str(raw.get("name", default_name))
    try:
        action_type = ActionType(name)
    except ValueError as exc:
        raise ActionParseError(name) from exc
    params = raw.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict) or not all(isinstance(key, str) for key in params):
        raise ActionParamsError("not_object")
    if len(params) > MAX_ACTION_PARAMS or any(
        isinstance(value, str) and len(value) > MAX_PARAM_STRING_LENGTH for value in params.values()
    ):
        raise ActionParamsError("too_large")
    return Action(name=action_type, params=dict(params))
