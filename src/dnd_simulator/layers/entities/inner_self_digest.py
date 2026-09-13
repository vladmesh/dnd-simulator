"""One entry point for consuming a creature's inner-self event buffer."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.character import Alignment, Character, Creature
from dnd_simulator.core.inner_self import AlignmentAccumulation, DigestBoundary, InnerSelf
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.rules.inner_self_digest import DigestContext, apply_delta, derive_delta, shift_alignment

if TYPE_CHECKING:
    from dnd_simulator.llm.summarizer import MemorySummarizer

logger = structlog.get_logger(domain="entity")


def dormify(creature: Creature, digest_fn: Callable[[Creature, DigestBoundary], None]) -> None:
    """Transition an active creature to dormant state and consume its buffer once."""
    if not creature.active:
        return
    creature.active = False
    digest_fn(creature, DigestBoundary.DORMANT)


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
    result = apply_delta(inner_self, derive_delta(inner_self, events, DigestContext(creature.id)))
    shifted_character: Character | None = None
    shifted_alignment: Alignment | None = None
    if isinstance(creature, Character) and not isinstance(creature, PlayerCharacter):
        shifted_character = creature
        shifted_alignment, accumulation = shift_alignment(creature.alignment, result.alignment)
        result = _with_alignment(result, accumulation)
    try:
        if isinstance(creature, Npc) and summarizer is not None:
            result = _with_summarized_journal(
                result,
                summarizer.summarize(result, [event.description for event in events], boundary.value),
            )
            if summarizer.needs_compression(result):
                result = _with_summarized_journal(result, summarizer.summarize(result, [], "journal_overflow"))
            logger.info(
                "npc_inner_self_updated", entity_id=creature.id, entity_name=creature.name, trigger=boundary.value
            )
    except Exception:
        # The buffer was intentionally cleared before calling the fallible body: a
        # permanent LLM failure must not make every later boundary retry old events.
        logger.exception(
            "inner_self_digest_failed", entity_id=creature.id, entity_name=creature.name, boundary=boundary.value
        )
    finally:
        # A digest body may replace InnerSelf. The result must never resurrect the
        # buffer consumed above; this assignment is the sole write-back to core.
        result.perceived_event_buffer.clear()
        creature.inner_self = result
        if shifted_character is not None and shifted_alignment is not None:
            shifted_character.alignment = shifted_alignment


def _with_summarized_journal(core: InnerSelf, summary: InnerSelf) -> InnerSelf:
    """Keep a journal-only summarizer from replacing the structured rules core."""
    return InnerSelf(
        relations=list(core.relations),
        mood=core.mood,
        goals=list(core.goals),
        alignment=AlignmentAccumulation(
            law_chaos=core.alignment.law_chaos,
            good_evil=core.alignment.good_evil,
        ),
        journal=summary.journal,
        thoughts=list(core.thoughts),
        current_conversation=summary.current_conversation,
        perceived_event_buffer=list(core.perceived_event_buffer),
    )


def _with_alignment(core: InnerSelf, alignment: AlignmentAccumulation) -> InnerSelf:
    """Return *core* with its rule-derived alignment evidence replaced."""
    return InnerSelf(
        relations=list(core.relations),
        mood=core.mood,
        goals=list(core.goals),
        alignment=alignment,
        journal=core.journal,
        thoughts=list(core.thoughts),
        current_conversation=core.current_conversation,
        perceived_event_buffer=list(core.perceived_event_buffer),
    )
