"""One entry point for consuming a creature's inner-self event buffer."""

from __future__ import annotations

from collections.abc import Callable

import structlog

from dnd_simulator.core.character import Alignment, Character, Creature
from dnd_simulator.core.inner_self import AlignmentAccumulation, DigestBoundary, InnerSelf
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.rules.inner_self_digest import DigestContext, apply_delta, derive_delta, shift_alignment

logger = structlog.get_logger(domain="entity")


def dormify(creature: Creature, digest_fn: Callable[[Creature, DigestBoundary], None]) -> None:
    """Transition an active creature to dormant state and consume its buffer once."""
    if not creature.active:
        return
    creature.active = False
    digest_fn(creature, DigestBoundary.DORMANT)


def digest(creature: Creature, boundary: DigestBoundary) -> None:
    """Consume a nonempty perception buffer once, retaining no failed work for retry."""
    inner_self = creature.inner_self
    if inner_self is None or not inner_self.perceived_event_buffer:
        return

    events = list(inner_self.perceived_event_buffer)
    inner_self.perceived_event_buffer.clear()
    proposal = _with_free_layer(
        apply_delta(inner_self, derive_delta(inner_self, events, DigestContext(creature.id))), inner_self
    )
    result = proposal
    shifted_character: Character | None = None
    shifted_alignment: Alignment | None = None
    try:
        from dnd_simulator.llm.brain import LlmBrain
        from dnd_simulator.llm.inner_self_digest import digest_with_llm

        if isinstance(creature.brain, LlmBrain):
            result = digest_with_llm(creature.brain.llm, inner_self, events, boundary.value, proposal, creature.id)
    except Exception as error:
        # The buffer was intentionally cleared before the fallible LLM call: a
        # permanent failure must not make every later boundary retry stale events.
        logger.warning(
            "inner_self_llm_digest_rejected",
            entity_id=creature.id,
            entity_name=creature.name,
            boundary=boundary.value,
            reason=type(error).__name__,
        )
    finally:
        if isinstance(creature, Character) and not isinstance(creature, PlayerCharacter):
            shifted_character = creature
            shifted_alignment, accumulation = shift_alignment(creature.alignment, result.alignment)
            result = _with_alignment(result, accumulation)
        # A digest body may replace InnerSelf. The result must never resurrect the
        # buffer consumed above; this assignment is the sole write-back to core.
        result.perceived_event_buffer.clear()
        creature.inner_self = result
        if shifted_character is not None and shifted_alignment is not None:
            shifted_character.alignment = shifted_alignment


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


def _with_free_layer(core: InnerSelf, before: InnerSelf) -> InnerSelf:
    """Carry LLM-only fields across a pure rules proposal without exposing them to rules."""
    return InnerSelf(
        relations=list(core.relations),
        mood=core.mood,
        goals=list(core.goals),
        alignment=AlignmentAccumulation(core.alignment.law_chaos, core.alignment.good_evil),
        journal=before.journal,
        thoughts=list(before.thoughts),
        current_conversation=before.current_conversation,
        perceived_event_buffer=list(core.perceived_event_buffer),
    )
