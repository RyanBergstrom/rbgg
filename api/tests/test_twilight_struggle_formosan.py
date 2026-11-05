from copy import deepcopy

import pytest

from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.scoring import classify_region


@pytest.fixture
def base_state():
    catalog = {card["id"]: card for card in load_standard_card_catalog()}
    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries["Mexico"]["us"] = 2
    return {
        "countries": countries,
        "tracks": {
            "defcon": 5,
            "victory_points": 0,
            "military_operations": {"us": 0, "ussr": 0},
        },
        "hands": {"us": [catalog[35], catalog[4]], "ussr": []},
        "draw_pile": [],
        "discard_pile": [],
        "removed_cards": [],
        "actions_taken": {"us": 0, "ussr": 0},
        "country_data": data,
    }


def test_formosan_resolution_event_sets_persistent_flag(base_state):
    state = deepcopy(base_state)
    data = state.pop("country_data")

    result = play_card_action(state, "us", 35, "event", country_data=data)

    assert result["persistent_events"]["formosan_resolution"]["faction"] == "us"
    assert result["persistent_events"]["formosan_resolution"]["expires_turn"] == 10


def test_formosan_resolution_makes_us_controlled_taiwan_a_battleground_in_asia():
    data = load_country_data()
    influences = {"Taiwan": {"us": 3, "ussr": 0}}

    without = classify_region("Asia", influences, data, set(), formosan_resolution=False)
    with_flag = classify_region("Asia", influences, data, set(), formosan_resolution=True)

    assert without["battleground_count"]["us"] == 0
    assert with_flag["battleground_count"]["us"] == 1


def test_formosan_resolution_ignores_ussr_controlled_taiwan():
    data = load_country_data()
    influences = {"Taiwan": {"us": 0, "ussr": 3}}

    with_flag = classify_region("Asia", influences, data, set(), formosan_resolution=True)

    assert with_flag["battleground_count"]["ussr"] == 0


def test_us_china_card_play_cancels_formosan_resolution(base_state):
    state = deepcopy(base_state)
    data = state.pop("country_data")
    state["china_card"] = {"owner": "us", "face_up": True}
    state["hands"]["us"] = []
    state["persistent_events"] = {"formosan_resolution": {"faction": "us", "expires_turn": 10}}

    result = play_card_action(
        state,
        "us",
        6,
        "operations",
        operations_action={
            "type": "realignment",
            "targets": [{"country": "Mexico", "us_roll": 6, "ussr_roll": 1}],
        },
        country_data=data,
    )

    assert "formosan_resolution" not in result["persistent_events"]
