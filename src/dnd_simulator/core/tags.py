"""Structured tag vocabulary and helpers for NPC state.

Emotions are plain strings. Relations use "tag:creature_id" format.
Readable by both RuleBrain (direct checks) and LLM (in prompt context).
"""

from __future__ import annotations


class NpcTag:
    """Structured tag constants."""

    # Emotions / states
    ANGRY = "angry"
    TIRED = "tired"
    HAPPY = "happy"
    SCARED = "scared"
    GRIEVING = "grieving"
    SUSPICIOUS = "suspicious"
    ALERTED = "alerted"

    # Relations (use as f"{tag}:{creature_id}")
    LOVES = "loves"
    HATES = "hates"
    TRUSTS = "trusts"
    FEARS = "fears"
    LOYAL_TO = "loyal_to"

    # Situational
    IN_MOURNING = "in_mourning"
    FLEEING = "fleeing"


def find_tags(tags: list[str], prefix: str) -> list[str]:
    """Extract creature IDs matching a tag prefix, e.g. find_tags(tags, "hates") → ["orc_chief"]."""
    p = prefix + ":"
    return [t[len(p) :] for t in tags if t.startswith(p)]


def has_tag(tags: list[str], tag: str) -> bool:
    """Check if a plain (non-relation) tag is present."""
    return tag in tags
