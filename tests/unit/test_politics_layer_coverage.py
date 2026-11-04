"""Coverage for appointing a leader during the monthly politics tick."""

import pytest

from dnd_simulator.core.models import ActionResult, Answer, EventType, GameDateTime, TimeDelta
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.politics.models import Leader, LeaderTrait, Nation


@pytest.mark.parametrize("leaderless_first", [True, False])
def test_monthly_tick_appoints_missing_leader_and_ages_existing_leaders(leaderless_first: bool) -> None:
    leaderless = Nation(id="n1", name="North", regions=["r1"])
    ruled = Nation(
        id="n2",
        name="South",
        regions=["r2"],
        leader=Leader(name="Aldric", age=30, trait=LeaderTrait.DIPLOMAT),
    )
    existing_leader = ruled.leader
    nations = [leaderless, ruled] if leaderless_first else [ruled, leaderless]
    politics = PoliticsLayer(nations=nations, seed=0)
    delta = TimeDelta.from_days(30)
    time = GameDateTime()

    events = politics.tick(delta, time, lambda _layer, _query: Answer(value=None), lambda _event: ActionResult())

    appointed = politics.get_nation("n1").leader
    assert appointed is not None
    assert appointed.name
    assert isinstance(appointed.trait, LeaderTrait)
    assert 25 <= appointed.age <= 55
    assert politics.get_nation("n2").leader is existing_leader
    assert existing_leader is not None
    assert existing_leader.age == 31
    assert not any(event.event_type in (EventType.LEADER_DIED, EventType.REBELLION) for event in events)

    appointed_age = appointed.age
    events = politics.tick(
        delta, time.advance(days=30), lambda _layer, _query: Answer(value=None), lambda _event: ActionResult()
    )

    assert politics.get_nation("n1").leader is appointed
    assert appointed.age == appointed_age + 1
    assert politics.get_nation("n2").leader is existing_leader
    assert existing_leader.age == 32
    assert not any(event.event_type in (EventType.LEADER_DIED, EventType.REBELLION) for event in events)
