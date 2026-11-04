"""Coverage for missing settlement lookups through the public layer API."""

import pytest

from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.layers.settlements.models import Settlement, SettlementType


def test_get_settlement_rejects_unknown_id_without_affecting_existing_settlements() -> None:
    settlement = Settlement(
        id="millbrook",
        name="Millbrook",
        region_id="greenvale",
        type=SettlementType.VILLAGE,
        population=300,
        prosperity=55.0,
        defenses=15.0,
    )
    layer = SettlementsLayer(settlements=[settlement])

    with pytest.raises(KeyError, match="Settlement 'missing' not found"):
        layer.get_settlement("missing")

    assert layer.get_settlement("millbrook") is settlement
