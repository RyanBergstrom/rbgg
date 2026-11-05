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


def _scoring_card(catalog, name):
    return next(card for card in catalog.values() if card.get("scoring") and card["name"] == name)


def _state(country_data, us_hand):
    countries = {name: {"us": 0, "ussr": 0} for name in country_data["countries"]}
    return {
        "countries": countries,
        "tracks": {"defcon": 5, "victory_points": 0, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": us_hand, "ussr": []},
        "draw_pile": [],
        "discard_pile": [],
        "removed_cards": [],
        "turn": 1,
    }


def _europe_country(country_data):
    return next(name for name, c in country_data["countries"].items() if c["region"] == "Europe")


def test_cambridge_five_adds_ussr_influence_to_named_region(catalog, country_data):
    state = _state(country_data, [deepcopy(_scoring_card(catalog, "Europe Scoring"))])
    country = _europe_country(country_data)
    card = deepcopy(catalog[104])

    result = resolve_card_event(
        state, card, "ussr", mode="event",
        country_data=country_data, event_choices={"cambridge_five": country},
    )

    assert result["event_triggered"] is True
    assert result["game_data"]["countries"][country]["ussr"] == 1
    assert result["game_data"]["countries"][country]["us"] == 0


def test_cambridge_five_rejects_region_not_named_on_us_scoring_card(catalog, country_data):
    state = _state(country_data, [deepcopy(_scoring_card(catalog, "Europe Scoring"))])
    asia = next(name for name, c in country_data["countries"].items() if c["region"] == "Asia")
    card = deepcopy(catalog[104])

    with pytest.raises(ValueError, match="Cambridge Five"):
        resolve_card_event(
            state, card, "ussr", mode="event",
            country_data=country_data, event_choices={"cambridge_five": asia},
        )


def test_cambridge_five_fails_closed_without_choice(catalog, country_data):
    state = _state(country_data, [deepcopy(_scoring_card(catalog, "Europe Scoring"))])
    card = deepcopy(catalog[104])

    with pytest.raises(ValueError, match="Cambridge Five"):
        resolve_card_event(state, card, "ussr", mode="event", country_data=country_data)


def test_cambridge_five_without_us_scoring_cards_has_no_effect(catalog, country_data):
    # No US scoring card names a region, so there is no legal target and the event does nothing.
    state = _state(country_data, [])
    country = _europe_country(country_data)
    card = deepcopy(catalog[104])

    result = resolve_card_event(
        state, card, "ussr", mode="event",
        country_data=country_data, event_choices={"cambridge_five": country},
    )

    assert result["event_triggered"] is True
    assert result["game_data"]["countries"][country]["ussr"] == 0
