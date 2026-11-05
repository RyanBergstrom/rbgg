from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event


@pytest.fixture
def catalog():
    return {card["id"]: card for card in load_standard_card_catalog()}


@pytest.fixture
def country_data():
    return load_country_data()


def _state(country_data, uk_influence, nato=False):
    countries = {name: {"us": 0, "ussr": 0} for name in country_data["countries"]}
    countries["U.K."] = dict(uk_influence)
    persistent = {"nato": {"faction": "us", "expires_turn": 10}} if nato else {}
    return {
        "countries": countries,
        "tracks": {"defcon": 5, "victory_points": 0, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [], "ussr": []},
        "draw_pile": [],
        "discard_pile": [],
        "removed_cards": [],
        "persistent_events": persistent,
        "turn": 1,
    }


def _uk_neighbor(country_data):
    return country_data["adjacency"]["U.K."][0]


def test_special_relationship_adds_us_influence_next_to_uk_without_nato(catalog, country_data):
    state = _state(country_data, {"us": 6, "ussr": 0})
    neighbor = _uk_neighbor(country_data)
    result = resolve_card_event(
        state, deepcopy(catalog[105]), "us", mode="event",
        country_data=country_data, event_choices={"special_relationship": neighbor},
    )

    assert result["event_triggered"] is True
    assert result["game_data"]["countries"][neighbor]["us"] == 1
    assert result["game_data"]["tracks"]["victory_points"] == 0


def test_special_relationship_rejects_non_adjacent_target_without_nato(catalog, country_data):
    state = _state(country_data, {"us": 6, "ussr": 0})
    far = next(
        name for name in country_data["countries"]
        if name not in country_data["adjacency"]["U.K."] and name != "U.K."
    )
    with pytest.raises(ValueError):
        resolve_card_event(
            state, deepcopy(catalog[105]), "us", mode="event",
            country_data=country_data, event_choices={"special_relationship": far},
        )


def test_special_relationship_with_nato_adds_two_influence_and_two_vp(catalog, country_data):
    state = _state(country_data, {"us": 6, "ussr": 0}, nato=True)
    result = resolve_card_event(
        state, deepcopy(catalog[105]), "us", mode="event",
        country_data=country_data, event_choices={"special_relationship": "France"},
    )

    assert result["game_data"]["countries"]["France"]["us"] == 2
    assert result["game_data"]["tracks"]["victory_points"] == 2


def test_special_relationship_with_nato_rejects_non_western_european_target(catalog, country_data):
    state = _state(country_data, {"us": 6, "ussr": 0}, nato=True)
    with pytest.raises(ValueError):
        resolve_card_event(
            state, deepcopy(catalog[105]), "us", mode="event",
            country_data=country_data, event_choices={"special_relationship": "Poland"},
        )


def test_special_relationship_no_effect_when_uk_not_us_controlled(catalog, country_data):
    state = _state(country_data, {"us": 1, "ussr": 4})
    result = resolve_card_event(
        state, deepcopy(catalog[105]), "us", mode="event",
        country_data=country_data, event_choices={},
    )

    assert result["event_triggered"] is True
    assert result["game_data"]["tracks"]["victory_points"] == 0
    assert all(c["us"] == 0 for name, c in result["game_data"]["countries"].items() if name != "U.K.")
