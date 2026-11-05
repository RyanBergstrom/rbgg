import pytest

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event


DATA = load_country_data()
WESTERN = ["U.K.", "France", "Benelux", "Italy", "Norway", "Sweden", "Denmark"]


def _state(influence=None):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    for name, values in (influence or {}).items():
        countries[name].update(values)
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "persistent_events": {},
        "turn": 1,
    }


def _play(state, card_id, handler, name, phasing, choices=None):
    card = {"id": card_id, "name": name, "effect_handler": handler, "alignment": phasing, "event_removed": False}
    return resolve_card_event(
        state,
        card,
        phasing,
        mode="event",
        country_data=DATA,
        rng=None,
        event_choices=choices or {},
    )


def test_vietnam_revolts_adds_two_ussr_and_sets_flag():
    result = _play(_state(), 9, "vietnam_revolts", "Vietnam Revolts", "ussr")
    game = result["game_data"]
    assert game["countries"]["Vietnam"]["ussr"] == 2
    assert game["persistent_events"]["vietnam_revolts"] == {"expires_turn": 1}


def test_marshall_plan_adds_one_us_to_seven_western_countries():
    result = _play(_state(), 23, "marshall_plan", "Marshall Plan", "us", choices={"marshall_plan": WESTERN})
    game = result["game_data"]
    for name in WESTERN:
        assert game["countries"][name]["us"] == 1
    assert game["persistent_events"]["marshall_plan"] is True


def test_marshall_plan_rejects_ussr_controlled_country():
    state = _state(influence={"France": {"ussr": DATA["countries"]["France"]["stability"]}})
    with pytest.raises(ValueError):
        _play(state, 23, "marshall_plan", "Marshall Plan", "us", choices={"marshall_plan": WESTERN})


def test_marshall_plan_rejects_wrong_count():
    with pytest.raises(ValueError):
        _play(_state(), 23, "marshall_plan", "Marshall Plan", "us", choices={"marshall_plan": WESTERN[:6]})


def test_de_stalinization_relocates_ussr_influence():
    state = _state(influence={"E. Germany": {"ussr": 3}})
    choice = {"from": {"E. Germany": 3}, "to": {"Poland": 2, "Hungary": 1}}
    game = _play(state, 33, "de_stalinization", "De-Stalinization", "ussr", choices={"de_stalinization": choice})["game_data"]
    assert game["countries"]["E. Germany"]["ussr"] == 0
    assert game["countries"]["Poland"]["ussr"] == 2
    assert game["countries"]["Hungary"]["ussr"] == 1


def test_de_stalinization_rejects_more_than_two_per_destination():
    state = _state(influence={"E. Germany": {"ussr": 3}})
    choice = {"from": {"E. Germany": 3}, "to": {"Poland": 3}}
    with pytest.raises(ValueError):
        _play(state, 33, "de_stalinization", "De-Stalinization", "ussr", choices={"de_stalinization": choice})


def test_de_stalinization_rejects_us_controlled_destination():
    state = _state(influence={"E. Germany": {"ussr": 1}, "Poland": {"us": DATA["countries"]["Poland"]["stability"]}})
    choice = {"from": {"E. Germany": 1}, "to": {"Poland": 1}}
    with pytest.raises(ValueError):
        _play(state, 33, "de_stalinization", "De-Stalinization", "ussr", choices={"de_stalinization": choice})
