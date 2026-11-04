"""Direct lifecycle tests for lair population write-back and respawn."""

from __future__ import annotations

import random
from copy import deepcopy

import pytest

from dnd_simulator.core.events import EntityDiedPayload, LairDematerializedPayload
from dnd_simulator.core.lair import Lair, LairMemberRole, LairOrigin, LairState
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.layers.ecology.lairs import apply_lair_death, apply_lair_dematerialize, respawn_lairs


@pytest.fixture
def lair() -> Lair:
    return Lair(
        id="warren",
        name="Warren",
        faction_id="goblins",
        location_id="cave",
        members=["goblin", "goblin"],
        core="chief",
        respawn_interval=60,
        last_respawn_time=100,
    )


@pytest.mark.parametrize(
    "origin",
    [
        None,
        LairOrigin("missing", "goblin", LairMemberRole.MEMBER),
        LairOrigin("warren", "goblin", LairMemberRole.CORE),
        LairOrigin("warren", "chief", LairMemberRole.MEMBER),
    ],
    ids=["no-origin", "unknown-lair", "wrong-core-template", "unknown-member-template"],
)
def test_unrelated_death_leaves_lairs_unchanged(lair: Lair, origin: LairOrigin | None) -> None:
    lairs = {lair.id: lair}
    before = deepcopy(lairs)

    apply_lair_death(lairs, EntityDiedPayload("creature", lair_origin=origin))

    assert lairs == before


def test_member_deaths_remove_one_each_and_ignore_exhausted_roster(lair: Lair) -> None:
    lairs = {lair.id: lair}
    origin = LairOrigin(lair.id, "goblin", LairMemberRole.MEMBER)
    first_death = EntityDiedPayload("goblin_1", lair_origin=origin)

    apply_lair_death(lairs, first_death)
    assert lair.alive_members == ["goblin"]
    assert lair.death_writebacks == {"goblin_1"}

    apply_lair_death(lairs, first_death)
    assert lair.alive_members == ["goblin"]
    assert lair.death_writebacks == {"goblin_1"}

    apply_lair_death(lairs, EntityDiedPayload("goblin_2", lair_origin=origin))
    assert lair.alive_members == []
    assert lair.death_writebacks == {"goblin_1", "goblin_2"}
    assert lair.core_alive is True
    assert lair.state is LairState.ACTIVE
    before = deepcopy(lairs)

    apply_lair_death(lairs, EntityDiedPayload("goblin_3", lair_origin=origin))

    assert lairs == before


def test_core_death_depletes_lair_without_removing_members(lair: Lair) -> None:
    apply_lair_death(
        {lair.id: lair},
        EntityDiedPayload("chief_1", lair_origin=LairOrigin(lair.id, "chief", LairMemberRole.CORE)),
    )

    assert lair.core_alive is False
    assert lair.state is LairState.DEPLETED
    assert lair.alive_members is None
    assert lair.members == ["goblin", "goblin"]
    assert lair.death_writebacks == {"chief_1"}


def test_unknown_lair_dematerialization_leaves_population_and_rng_unchanged(lair: Lair) -> None:
    lairs = {lair.id: lair}
    before = deepcopy(lairs)
    rng = random.Random(3)
    rng_before = rng.getstate()
    event = Event(
        EventType.LAIR_DEMATERIALIZED,
        "entities",
        LairDematerializedPayload("missing", False, (), 200),
    )

    apply_lair_dematerialize(lairs, event, rng)

    assert lairs == before
    assert rng.getstate() == rng_before


@pytest.mark.parametrize(
    ("initial_state", "reported_core_alive", "expected_state", "expected_core_alive"),
    [
        (LairState.ACTIVE, True, LairState.ACTIVE, True),
        (LairState.ACTIVE, False, LairState.DEPLETED, False),
        (LairState.DEPLETED, True, LairState.DEPLETED, False),
    ],
)
def test_dematerialization_syncs_survivors_and_preserves_depletion(
    lair: Lair,
    initial_state: LairState,
    reported_core_alive: bool,
    expected_state: LairState,
    expected_core_alive: bool,
) -> None:
    lair.state = initial_state
    lair.core_alive = initial_state is LairState.ACTIVE
    event = Event(
        EventType.LAIR_DEMATERIALIZED,
        "entities",
        LairDematerializedPayload(lair.id, reported_core_alive, ("goblin",), 200),
    )

    apply_lair_dematerialize({lair.id: lair}, event, random.Random(3))

    assert lair.alive_members == ["goblin"]
    assert lair.core_alive is expected_core_alive
    assert lair.state is expected_state
    assert lair.last_respawn_time == 200


@pytest.mark.parametrize(
    ("state", "survivors", "now", "should_respawn"),
    [
        (LairState.DEPLETED, [], 200, False),
        (LairState.ACTIVE, None, 200, False),
        (LairState.ACTIVE, ["goblin", "goblin"], 200, False),
        (LairState.ACTIVE, [], 159, False),
        (LairState.ACTIVE, [], 160, True),
        (LairState.ACTIVE, ["goblin"], 200, True),
    ],
    ids=["depleted", "implicit-full-roster", "explicit-full-roster", "too-soon", "at-interval", "after-interval"],
)
def test_respawn_refills_only_eligible_lairs(
    lair: Lair, state: LairState, survivors: list[str] | None, now: int, should_respawn: bool
) -> None:
    lair.state = state
    lair.alive_members = survivors
    expected = deepcopy(lair)
    if should_respawn:
        expected.alive_members = None
        expected.last_respawn_time = now

    respawn_lairs({lair.id: lair}, now)

    assert lair == expected
