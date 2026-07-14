"""Typed access to action parameters at the domain boundary."""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionRejectedError
from dnd_simulator.core.action_defs import get_action_def
from dnd_simulator.i18n import _


def validate_action_params(action: Action) -> None:
    """Reject missing required params and values that violate ActionDef types."""
    for param in get_action_def(action.name).params:
        if param.name not in action.params:
            if param.required:
                raise ActionRejectedError(
                    _("Action '{action}' requires parameter '{param}'").format(
                        action=action.name.value,
                        param=param.name,
                    )
                )
            continue

        value = action.params[param.name]
        if param.param_type == "string" and not isinstance(value, str):
            raise ActionRejectedError(_("Parameter '{param}' must be a string").format(param=param.name))
        if param.param_type == "integer":
            _parse_integer(value, param.name)


def integer_param(action: Action, name: str, *, default: int | None = None) -> int:
    """Read an integer param, accepting integer strings used by LLM actions."""
    if name not in action.params:
        if default is not None:
            return default
        raise ActionRejectedError(_("Action requires parameter '{param}'").format(param=name))
    return _parse_integer(action.params[name], name)


def _parse_integer(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ActionRejectedError(_("Parameter '{param}' must be an integer").format(param=name))
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as error:
            raise ActionRejectedError(_("Parameter '{param}' must be an integer").format(param=name)) from error
    raise ActionRejectedError(_("Parameter '{param}' must be an integer").format(param=name))
