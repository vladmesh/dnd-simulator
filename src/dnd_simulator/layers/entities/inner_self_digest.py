"""One entry point for consuming a creature's inner-self event buffer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.character import Creature
from dnd_simulator.core.inner_self import DigestBoundary
from dnd_simulator.layers.entities.models import Npc

if TYPE_CHECKING:
    from dnd_simulator.llm.summarizer import MemorySummarizer

logger = structlog.get_logger(domain="entity")


def digest(creature: Creature, boundary: DigestBoundary, summarizer: MemorySummarizer | None) -> None:
    """Consume a nonempty perception buffer once, retaining no failed work for retry.

    The current digest body is deliberately the legacy NPC journal summarizer. Other
    core bearers consume their buffer now so later digest implementations can share
    these boundaries without replaying old events.
    """
    inner_self = creature.inner_self
    if inner_self is None or not inner_self.perceived_event_buffer:
        return

    events = list(inner_self.perceived_event_buffer)
    inner_self.perceived_event_buffer.clear()
    if not isinstance(creature, Npc) or summarizer is None:
        return

    try:
        creature.inner_self = summarizer.summarize(inner_self, [event.description for event in events], boundary.value)
        if creature.inner_self is not None and summarizer.needs_compression(creature.inner_self):
            creature.inner_self = summarizer.summarize(creature.inner_self, [], "journal_overflow")
        logger.info("npc_inner_self_updated", entity_id=creature.id, entity_name=creature.name, trigger=boundary.value)
    except Exception:
        # The buffer was intentionally cleared before calling the fallible body: a
        # permanent LLM failure must not make every later boundary retry old events.
        logger.exception(
            "inner_self_digest_failed", entity_id=creature.id, entity_name=creature.name, boundary=boundary.value
        )
