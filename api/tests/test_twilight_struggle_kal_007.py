from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


def _state(defcon=5, vp=0, sk_us=0, turn=1):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    countries["S. Korea"]["us"] = sk_us
    return {
        "countries": countries,
        "tracks": {"victory_points": vp, "defcon": defcon, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "turn": turn,
    }


def _play(state, phasing="us"):
    return resolve_card_event(state, CATALOG[89], phasing, mode="event", country_data=DATA)


def test_kal_007_is_registered_as_handler():
    assert CATALOG[89]["effect_handler"] == "kal_007"
    assert CATALOG[89]["alignment"] == "us"
    assert CATALOG[89]["operations"] == 4


def test_degrades_defcon_one_level_and_gives_us_two_vp():
    game = _play(_state(defcon=5, vp=0))["game_data"]
    assert game["tracks"]["defcon"] == 4
    assert game["tracks"]["victory_points"] == 2


def test_defcon_floor_is_one():
    game = _play(_state(defcon=1, vp=0))["game_data"]
    assert game["tracks"]["defcon"] == 1
    assert game["tracks"]["victory_points"] == 0


def test_no_bonus_when_south_korea_not_us_controlled():
    game = _play(_state(sk_us=0))["game_data"]
    assert "kal_007_bonus" not in game["persistent_events"]


def test_bonus_recorded_when_south_korea_us_controlled():
    game = _play(_state(sk_us=10, turn=3))["game_data"]
    bonus = game["persistent_events"]["kal_007_bonus"]
    assert bonus == {"faction": "us", "operations": 4, "expires_turn": 3}


def test_ussr_cannot_play_kal_007():
    with pytest.raises(ValueError, match="US card"):
        _play(_state(), phasing="ussr")


def test_input_state_is_not_mutated():
    state = _state(sk_us=10)
    before = deepcopy(state)
    _play(state)
    assert state == before
