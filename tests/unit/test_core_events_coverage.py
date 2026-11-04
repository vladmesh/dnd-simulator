"""Coverage for list-valued data in typed event payload serialization."""

import pytest

from dnd_simulator.core.events import EntitySecondWindPayload, payload_to_data
from dnd_simulator.core.models import EventType
from dnd_simulator.core.rolls import DieRoll


@pytest.mark.parametrize(
    ("details", "expected"),
    [
        pytest.param([], [], id="empty-list"),
        pytest.param(
            [DieRoll(sides=10, result=4)],
            [{"sides": 10, "result": 4, "original": None}],
            id="list-of-dice",
        ),
        pytest.param(
            [[DieRoll(sides=10, result=4)], {"bonus": [2, 3], "source": EventType.ENTITY_SECOND_WIND}],
            [
                [{"sides": 10, "result": 4, "original": None}],
                {"bonus": [2, 3], "source": EventType.ENTITY_SECOND_WIND.value},
            ],
            id="nested-lists",
        ),
    ],
)
def test_payload_to_data_encodes_list_dice_details(details: list[object], expected: list[object]) -> None:
    payload = EntitySecondWindPayload(entity_id="fighter", healed=9, dice_detail=(details,))

    assert payload_to_data(payload) == {
        "entity_id": "fighter",
        "healed": 9,
        "dice_detail": [expected],
    }
