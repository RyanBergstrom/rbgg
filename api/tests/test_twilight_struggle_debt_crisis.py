from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


def _sa(count):
    names = [n for n, info in DATA["countries"].items() if info.get("region") == "South America"]
    assert len(names) >= count
    return names[:count]


def _state(ussr_by_country=None, us_hand_ids=()):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    for name, value in (ussr_by_country or {}).items():
        countries[name]["ussr"] = value
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [deepcopy(CATALOG[i]) for i in us_hand_ids], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "turn": 1,
    }


def _play(state, choices):
    return resolve_card_event(
        state, CATALOG[95], "ussr", mode="event", country_data=DATA, event_choices=choices,
    )


def test_debt_crisis_is_registered_as_handler():
    assert CATALOG[95]["effect_handler"] == "latin_america_debt_crisis"
    assert CATALOG[95]["alignment"] == "ussr"


def test_doubles_ussr_influence_in_two_chosen_countries_when_us_does_not_discard():
    a, b = _sa(2)
    state = _state({a: 2, b: 3})
    game = _play(state, {"debt_crisis_countries": [a, b]})["game_data"]
    assert game["countries"][a]["ussr"] == 4
    assert game["countries"][b]["ussr"] == 6


def test_zero_ussr_influence_country_stays_zero():
    a, b = _sa(2)
    state = _state({a: 2})
    game = _play(state, {"debt_crisis_countries": [a, b]})["game_data"]
    assert game["countries"][a]["ussr"] == 4
    assert game["countries"][b]["ussr"] == 0


def test_us_discard_of_three_plus_ops_card_prevents_effect():
    a, b = _sa(2)
    three_plus = next(i for i, c in CATALOG.items() if c["operations"] >= 3 and c["deck_card"] and not c["scoring"])
    state = _state({a: 2, b: 2}, us_hand_ids=(three_plus,))
    game = _play(state, {"debt_crisis_discard": three_plus, "debt_crisis_countries": [a, b]})["game_data"]
    assert game["countries"][a]["ussr"] == 2
    assert game["countries"][b]["ussr"] == 2
    assert three_plus in [c["id"] for c in game["discard_pile"]]


def test_discarding_below_three_ops_is_rejected():
    a, b = _sa(2)
    low = next(i for i, c in CATALOG.items() if c["operations"] < 3 and c["deck_card"] and not c["scoring"])
    state = _state({a: 2, b: 2}, us_hand_ids=(low,))
    with pytest.raises(ValueError, match="3\\+ Ops"):
        _play(state, {"debt_crisis_discard": low, "debt_crisis_countries": [a, b]})


def test_requires_two_distinct_south_american_countries():
    a, _ = _sa(2)
    with pytest.raises(ValueError, match="two distinct"):
        _play(_state({a: 2}), {"debt_crisis_countries": [a, a]})


def test_rejects_non_south_american_target():
    a, _ = _sa(2)
    africa = next(n for n, info in DATA["countries"].items() if info.get("region") == "Africa")
    with pytest.raises(ValueError, match="cannot target"):
        _play(_state({a: 2}), {"debt_crisis_countries": [a, africa]})


def test_us_cannot_play_debt_crisis():
    a, b = _sa(2)
    with pytest.raises(ValueError, match="USSR card"):
        resolve_card_event(
            _state({a: 2}), CATALOG[95], "us", mode="event", country_data=DATA,
            event_choices={"debt_crisis_countries": [a, b]},
        )
