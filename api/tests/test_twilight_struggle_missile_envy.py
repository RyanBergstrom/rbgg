from copy import deepcopy

import pytest

from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data


@pytest.fixture
def catalog():
    return {card["id"]: card for card in load_standard_card_catalog()}


@pytest.fixture
def country_data():
    return load_country_data()


def _synthetic(card_id, ops, alignment):
    return {
        "id": card_id,
        "name": f"Test {card_id}",
        "operations": ops,
        "alignment": alignment,
        "scoring": False,
        "special": False,
        "event_removed": False,
        "effect_handler": None,
        "era": 1,
    }


def _state(country_data, us_hand, ussr_hand, defcon=5):
    countries = {name: {"us": 0, "ussr": 0} for name in country_data["countries"]}
    return {
        "countries": countries,
        "tracks": {"defcon": defcon, "victory_points": 0, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": deepcopy(us_hand), "ussr": deepcopy(ussr_hand)},
        "draw_pile": [],
        "discard_pile": [],
        "removed_cards": [],
        "persistent_events": {},
        "turn": 1,
    }


def _ids(cards):
    return [card["id"] for card in cards]


def test_missile_envy_exchanges_highest_ops_card_to_opponent(catalog, country_data):
    missile_envy = deepcopy(catalog[49])
    state = _state(
        country_data,
        us_hand=[missile_envy],
        ussr_hand=[_synthetic(900, 2, "ussr"), _synthetic(901, 4, "ussr")],
    )
    result = play_card_action(state, "us", 49, "event", country_data=country_data)
    game = result if "hands" in result else result["game_data"]
    assert 49 in _ids(game["hands"]["ussr"])
    assert 901 not in _ids(game["hands"]["ussr"])
    assert 901 in _ids(game["hands"]["us"])
    assert 900 in _ids(game["hands"]["ussr"])


def test_missile_envy_is_not_duplicated_in_discard(catalog, country_data):
    state = _state(
        country_data,
        us_hand=[deepcopy(catalog[49])],
        ussr_hand=[_synthetic(901, 4, "ussr")],
    )
    result = play_card_action(state, "us", 49, "event", country_data=country_data)
    game = result if "hands" in result else result["game_data"]
    assert 49 not in _ids(game["discard_pile"])
    assert _ids(game["hands"]["ussr"]) == [49]


def test_missile_envy_records_pending_obligation_for_opponent(catalog, country_data):
    state = _state(
        country_data,
        us_hand=[deepcopy(catalog[49])],
        ussr_hand=[_synthetic(901, 4, "ussr")],
    )
    result = play_card_action(state, "us", 49, "event", country_data=country_data)
    game = result if "hands" in result else result["game_data"]
    obligation = game["persistent_events"]["missile_envy"]
    assert obligation["faction"] == "ussr"
    assert obligation["card_id"] == 49
    assert obligation["pending"] is True


def test_missile_envy_own_aligned_taken_event_resolves_immediately(catalog, country_data):
    # SALT Negotiations (43) improves DEFCON by 2; a copy aligned to US is taken and fires at once.
    taken_salt = deepcopy(catalog[43])
    taken_salt["operations"] = 4
    taken_salt["alignment"] = "us"
    state = _state(
        country_data,
        us_hand=[deepcopy(catalog[49])],
        ussr_hand=[taken_salt],
        defcon=3,
    )
    result = play_card_action(state, "us", 49, "event", country_data=country_data)
    game = result if "hands" in result else result["game_data"]
    assert game["tracks"]["defcon"] == 5
    assert 43 in _ids(game["discard_pile"]) or 43 in _ids(game["removed_cards"])
    assert 43 not in _ids(game["hands"]["us"])
    assert 49 in _ids(game["hands"]["ussr"])


def test_missile_envy_opponent_aligned_taken_card_stays_in_hand(catalog, country_data):
    state = _state(
        country_data,
        us_hand=[deepcopy(catalog[49])],
        ussr_hand=[_synthetic(901, 4, "ussr")],
    )
    result = play_card_action(state, "us", 49, "event", country_data=country_data)
    game = result if "hands" in result else result["game_data"]
    assert 901 in _ids(game["hands"]["us"])
    assert 901 not in _ids(game["discard_pile"])


def test_missile_envy_with_empty_opponent_hand_is_discarded(catalog, country_data):
    state = _state(country_data, us_hand=[deepcopy(catalog[49])], ussr_hand=[])
    result = play_card_action(state, "us", 49, "event", country_data=country_data)
    game = result if "hands" in result else result["game_data"]
    assert 49 in _ids(game["discard_pile"])
    assert "missile_envy" not in game["persistent_events"]
