from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SaveStore(ABC):
    """Abstract interface for persisting game state."""

    @abstractmethod
    def save(self, name: str, data: dict[str, Any]) -> None:
        """Save game state under a given name. Overwrites if exists."""

    @abstractmethod
    def load(self, name: str) -> dict[str, Any]:
        """Load game state by name. Raises KeyError if not found."""

    @abstractmethod
    def list_saves(self) -> list[str]:
        """List all available save names."""

    @abstractmethod
    def delete(self, name: str) -> None:
        """Delete a save by name. Raises KeyError if not found."""

    def autosave(self, data: dict[str, Any]) -> None:
        """Save with a timestamped name."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        self.save(f"autosave_{timestamp}", data)


class JsonFileStore(SaveStore):
    """Stores game state as JSON files in a directory."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, data: dict[str, Any]) -> None:
        path = self._path_for(name)
        with path.open("w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, name: str) -> dict[str, Any]:
        path = self._path_for(name)
        if not path.exists():
            raise KeyError(f"Save '{name}' not found")
        with path.open() as f:
            data: dict[str, Any] = json.load(f)
            return data

    def list_saves(self) -> list[str]:
        return sorted(p.stem for p in self._directory.glob("*.json"))

    def delete(self, name: str) -> None:
        path = self._path_for(name)
        if not path.exists():
            raise KeyError(f"Save '{name}' not found")
        path.unlink()

    def _path_for(self, name: str) -> Path:
        return self._directory / f"{name}.json"
