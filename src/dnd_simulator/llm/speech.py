"""Shared rendering helpers for speech exposed to LLMs."""

from __future__ import annotations


def speech_words(description: str) -> str:
    """Remove the speaker prefix already present in a perceived speech event."""
    prefix, separator, words = description.partition(":")
    return words.lstrip() if prefix and separator else description
