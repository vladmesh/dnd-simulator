"""Coverage for cold-cache loading and missing NPC behavior data."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from dnd_simulator.core.character import NpcRole
from dnd_simulator.layers.entities import npc_behaviors
from dnd_simulator.layers.entities.models import NpcActivity


@pytest.fixture(autouse=True)
def _unloaded_behaviors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(npc_behaviors, "_schedule_templates", None)
    monkeypatch.setattr(npc_behaviors, "_activity_flavor", None)
    monkeypatch.setattr(npc_behaviors, "_activity_generic", None)


@pytest.mark.parametrize(
    "first_getter",
    [
        npc_behaviors.get_schedule_templates,
        npc_behaviors.get_activity_flavor,
        npc_behaviors.get_activity_generic,
    ],
)
def test_first_access_loads_all_behavior_data(first_getter: Callable[[], object]) -> None:
    first_result = first_getter()

    assert npc_behaviors.get_schedule_templates()[NpcRole.BLACKSMITH] == [
        (21, 7, NpcActivity.SLEEPING, "home"),
        (7, 19, NpcActivity.WORKING, "smithy"),
        (19, 21, NpcActivity.IDLE, "tavern"),
    ]
    assert npc_behaviors.get_activity_flavor()[(NpcRole.GUARD, NpcActivity.WORKING)] == "standing watch"
    assert npc_behaviors.get_activity_generic() == {
        NpcActivity.WORKING: "busy at work",
        NpcActivity.IDLE: "standing around",
        NpcActivity.SLEEPING: "sleeping",
    }
    assert first_getter() is first_result


def test_missing_yaml_raises_with_file_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing_path = tmp_path / "missing_npc_behaviors.yaml"
    monkeypatch.setattr(npc_behaviors, "_YAML_PATH", missing_path)

    with pytest.raises(RuntimeError, match=rf"^NPC behaviors YAML not found: {re.escape(str(missing_path))}$"):
        npc_behaviors.get_schedule_templates()
