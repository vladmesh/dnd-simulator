"""Coverage for unsupported entity serialization."""

from collections.abc import Callable

import pytest

from dnd_simulator.core.character import Entity
from dnd_simulator.layers.entities.entity_serialization import entity_to_save_model, serialize_entity


@pytest.mark.parametrize("serialize", [entity_to_save_model, serialize_entity])
def test_serialization_rejects_base_entity(serialize: Callable[[Entity], object]) -> None:
    entity = Entity(id="landmark", name="Standing Stone", location_id="forest")

    with pytest.raises(TypeError, match=r"^Unsupported entity type for save: Entity$"):
        serialize(entity)
