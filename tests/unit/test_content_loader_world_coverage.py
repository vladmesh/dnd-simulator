"""Coverage for optional battle maps and permissive faction entries."""

from pathlib import Path

import pytest
import yaml

from dnd_simulator.content_loader.world import load_factions, load_location_battle_maps
from dnd_simulator.layers.politics.models import FactionRelation


@pytest.mark.parametrize("content", [None, "", "{}"], ids=["missing", "empty", "empty-mapping"])
def test_location_battle_maps_without_locations(tmp_path: Path, content: str | None) -> None:
    if content is not None:
        (tmp_path / "locations.yaml").write_text(content)

    assert load_location_battle_maps(tmp_path) == {}


@pytest.mark.parametrize(
    "invalid_entry",
    [None, "not a faction", 42, ["not", "a", "mapping"]],
    ids=["null", "string", "number", "list"],
)
def test_factions_skip_non_mappings_and_preserve_plain_names(tmp_path: Path, invalid_entry: object) -> None:
    (tmp_path / "factions.yaml").write_text(
        yaml.safe_dump(
            {
                "invalid": invalid_entry,
                "wardens": {"name": "Wardens", "relations": {"bandits": "hostile"}},
                "bandits": {"name": {"en": "Bandits", "fr": "Brigands"}},
            },
            sort_keys=False,
        )
    )

    factions = load_factions(tmp_path, lang="fr")

    assert factions.names == {"wardens": "Wardens", "bandits": "Brigands"}
    assert factions.relations == {("bandits", "wardens"): FactionRelation.HOSTILE}
