"""Shared types for subjective entity-event descriptions."""

from __future__ import annotations

from collections.abc import Callable

from dnd_simulator.core.character import Entity

GetEntityFn = Callable[[str], Entity | None]
