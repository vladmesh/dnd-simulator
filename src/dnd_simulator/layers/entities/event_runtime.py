"""Runtime application of activation trigger boundaries."""

from __future__ import annotations

from dnd_simulator.core.intent import IntentInterruptReason
from dnd_simulator.core.models import ActionResult, Event
from dnd_simulator.layers.entities.intent_completion import interrupt_intent
from dnd_simulator.layers.entities.trigger_index import TriggerBoundary, TriggerIndex


class TriggerRuntime:
    """Apply matching trigger boundaries without owning layer orchestration."""

    def __init__(self, trigger_index: TriggerIndex) -> None:
        if not isinstance(trigger_index, TriggerIndex):
            raise TypeError("trigger_index must be a TriggerIndex")
        self._trigger_index = trigger_index

    def apply(self, event: Event) -> None:
        for match in self._trigger_index.match(event):
            if match.boundary is TriggerBoundary.ON:
                if not match.creature.is_alive or match.trigger.active:
                    continue
                match.trigger.active = True
                interrupt_intent(match.creature, IntentInterruptReason.TRIGGER)
                match.creature.active = True
            elif match.trigger.active:
                match.trigger.active = False

    def apply_cascades(self, result: ActionResult) -> ActionResult:
        """Apply events produced locally before World skips their source layer."""
        for event in result.events:
            self.apply(event)
        return result
