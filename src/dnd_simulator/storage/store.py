from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SaveStore(ABC):
    """Abstract interface for persisting game state."""

    @abstractmethod
    def save(self, name: str, data: dict[str, Any], *, world: str = "") -> None:
        """Save game state under a given name. Overwrites if exists."""

    @abstractmethod
    def load(self, name: str, *, world: str = "") -> dict[str, Any]:
        """Load game state by name. Raises KeyError if not found."""

    @abstractmethod
    def list_saves(self, *, world: str = "") -> list[str]:
        """List all available save names for a world."""

    @abstractmethod
    def delete(self, name: str, *, world: str = "") -> None:
        """Delete a save by name. Raises KeyError if not found."""

    def autosave(self, data: dict[str, Any], *, world: str = "") -> None:
        """Save with a timestamped name."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self.save(f"autosave_{timestamp}", data, world=world)


class JsonFileStore(SaveStore):
    """Stores game state as JSON files in a directory, organized by world."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, data: dict[str, Any], *, world: str = "") -> None:
        path = self._path_for(name, world=world)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, name: str, *, world: str = "") -> dict[str, Any]:
        path = self._path_for(name, world=world)
        if not path.exists():
            # Fallback: try root directory for backward compat
            if world:
                root_path = self._directory / f"{name}.json"
                if root_path.exists():
                    with root_path.open() as f:
                        data: dict[str, Any] = json.load(f)
                        return data
            raise KeyError(f"Save '{name}' not found")
        with path.open() as f:
            data = json.load(f)
            return data

    def list_saves(self, *, world: str = "") -> list[str]:
        target = self._world_dir(world)
        if not target.exists():
            return []
        return sorted(p.stem for p in target.glob("*.json"))

    def list_worlds(self) -> list[str]:
        """List world names that have saved data."""
        return sorted(p.name for p in self._directory.iterdir() if p.is_dir())

    def delete(self, name: str, *, world: str = "") -> None:
        path = self._path_for(name, world=world)
        if not path.exists():
            raise KeyError(f"Save '{name}' not found")
        path.unlink()

    def _world_dir(self, world: str) -> Path:
        if world:
            return self._directory / world
        return self._directory

    def _path_for(self, name: str, *, world: str = "") -> Path:
        return self._world_dir(world) / f"{name}.json"
