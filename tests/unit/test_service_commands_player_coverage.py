"""Coverage for player creation validation and explicit combat positions."""

from pathlib import Path

import pytest

from dnd_simulator.service import GameService, GameSession
from dnd_simulator.storage.store import JsonFileStore

FIGHTER_SCORES = {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8}


@pytest.fixture
def player_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[GameService, GameSession]:
    monkeypatch.setenv("DND_WORLD_SEED", "42")
    monkeypatch.setenv("DND_DICE_SEED", "42")
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    return service, service.start_game(world_name="sword_vale")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"class": "not_a_class"}, "^Unknown class: not_a_class$"),
        ({"ability_scores": {"luck": 10}}, "^Invalid ability scores: 'luck' is not a valid Ability$"),
        ({"ability_scores": {"str": "strong"}}, "^Invalid ability scores: invalid literal for int"),
    ],
    ids=["unknown-class", "unknown-ability", "nonnumeric-score"],
)
def test_create_player_rejects_invalid_input_without_adding_player(
    player_session: tuple[GameService, GameSession], overrides: dict[str, object], message: str
) -> None:
    service, session = player_session
    player_data = {"class": "fighter", "ability_scores": FIGHTER_SCORES, **overrides}

    with pytest.raises(ValueError, match=message):
        service.create_player(session.session_id, player_data)

    assert session.get_player() is None


@pytest.mark.parametrize("position", [(0, 0), (15, 25)])
def test_create_player_preserves_explicit_combat_position(
    player_session: tuple[GameService, GameSession], position: tuple[int, int]
) -> None:
    service, session = player_session

    player = service.create_player(
        session.session_id,
        {"class": "fighter", "ability_scores": FIGHTER_SCORES, "combat_position": list(position)},
    )

    assert player.combat_position == position
    assert session.get_player(player.id) is player
    assert player.max_hp == 12


def test_create_player_validates_forwarded_combat_position(
    player_session: tuple[GameService, GameSession],
) -> None:
    service, session = player_session

    with pytest.raises(ValueError, match="combat_position values must be multiples of 5"):
        service.create_player(
            session.session_id,
            {"class": "fighter", "ability_scores": FIGHTER_SCORES, "combat_position": [1, 2]},
        )

    assert session.get_player() is None
