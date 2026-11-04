"""Coverage for zero-valued components in damage descriptions."""

import pytest

from dnd_simulator.core.events import DamageComponentPayload
from dnd_simulator.layers.entities.perception import _format_damage

_ZERO_DAMAGE = DamageComponentPayload(source="str", dice="", dice_detail=(), amount=0, type="slashing")
_WEAPON_DAMAGE = DamageComponentPayload(source="weapon", dice="1d8", dice_detail=(), amount=6, type="slashing")
_DUELING_DAMAGE = DamageComponentPayload(source="dueling", dice="", dice_detail=(), amount=2, type="slashing")


@pytest.mark.parametrize(
    ("components", "expected"),
    [
        pytest.param((_ZERO_DAMAGE,), ", 0 damage", id="only-zero"),
        pytest.param((_ZERO_DAMAGE, _WEAPON_DAMAGE), ", 6 damage (1d8 slashing)", id="leading-zero"),
        pytest.param(
            (_WEAPON_DAMAGE, _ZERO_DAMAGE, _DUELING_DAMAGE, _ZERO_DAMAGE),
            ", 8 damage (1d8 slashing + 2 Dueling)",
            id="middle-and-trailing-zero",
        ),
    ],
)
def test_format_damage_omits_zero_components(components: tuple[DamageComponentPayload, ...], expected: str) -> None:
    damage = sum(component.amount for component in components)

    assert _format_damage(damage, components, critical=False) == expected
