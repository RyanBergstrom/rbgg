from copy import deepcopy

import pytest

from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.headlines import reveal_headlines


@pytest.fixture
def catalog():
    return {card["id"]: card for card in load_standard_card_catalog()}


@pytest.fixture
def country_data():
    return load_country_data()


def _state(country_data, us_hand, ussr_hand, headlines=None):
    countries = {name: {"us": 0, "ussr": 0} for name in country_data["countries"]}
    return {
        "countries": countries,
        "tracks": {
            "defcon": 5,
            "victory_points": 0,
            "military_operations": {"us": 0, "ussr": 0},
        },
        "hands": {"us": us_hand, "ussr": ussr_hand},
        "draw_pile": [],
        "discard_pile": [],
        "removed_cards": [],
        "actions_taken": {"us": 0, "ussr": 0},
        "current_phase": "headline_reveal_ready",
        "headline_cards": headlines or {"us": 103, "ussr": 5},
        "country_data": country_data,
    }


def test_us_defectors_headline_cancels_ussr_headline(catalog, country_data):
    # Five Year Plan (ops 3) would normally resolve first; Defectors must cancel it.
    state = _state(country_data, [deepcopy(catalog[103])], [deepcopy(catalog[5])])

    result = reveal_headlines(state, country_data)

    assert {card["id"] for card in result["discard_pile"]} == {5, 103}
    assert any(entry.get("canceled") for entry in result["revealed_headlines"] if entry["faction"] == "ussr")
    assert result["hands"]["us"] == [] and result["hands"]["ussr"] == []


def test_defectors_headline_only_cancels_ussr_not_us(catalog, country_data):
    state = _state(country_data, [deepcopy(catalog[103])], [deepcopy(catalog[5])])

    result = reveal_headlines(state, country_data)

    us_entries = [entry for entry in result["revealed_headlines"] if entry["faction"] == "us"]
    assert us_entries and not us_entries[0].get("canceled")


def test_ussr_played_defectors_gives_us_one_vp(catalog, country_data):
    state = _state(country_data, [], [deepcopy(catalog[103])])

    result = play_card_action(state, "ussr", 103, "event", country_data=country_data)

    assert result["tracks"]["victory_points"] == 1


def test_us_played_defectors_as_event_gives_no_vp(catalog, country_data):
    state = _state(country_data, [deepcopy(catalog[103])], [])

    result = play_card_action(state, "us", 103, "event", country_data=country_data)

    assert result["tracks"]["victory_points"] == 0
