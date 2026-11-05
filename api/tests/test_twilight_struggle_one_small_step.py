from copy import deepcopy

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


def _state(us=0, ussr=0, vp=0):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    return {
        "countries": countries,
        "tracks": {
            "victory_points": vp,
            "defcon": 5,
            "military_operations": {"us": 0, "ussr": 0},
            "space_race": {"us": us, "ussr": ussr},
        },
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "turn": 1,
    }


def _play(state, phasing):
    return resolve_card_event(state, CATALOG[80], phasing, mode="event", country_data=DATA)


def test_one_small_step_is_registered_as_handler():
    assert CATALOG[80]["effect_handler"] == "one_small_step"
    assert CATALOG[80]["alignment"] == "both"


def test_behind_player_moves_two_boxes_and_gains_second_box_vp():
    # US lands on box 3 (2/0) after the USSR already reached it, so it is second there: 0 VP.
    result = _play(_state(us=1, ussr=4), "us")
    game = result["game_data"]
    assert game["tracks"]["space_race"]["us"] == 3
    assert game["tracks"]["victory_points"] == 0


def test_landing_first_on_a_box_awards_first_vp():
    # US jumps 1 -> 3 while the USSR is on 2: first to reach Man in Space (2/0) earns 2 VP.
    result = _play(_state(us=1, ussr=2), "us")
    game = result["game_data"]
    assert game["tracks"]["space_race"]["us"] == 3
    assert game["tracks"]["victory_points"] == 2


def test_ussr_behind_gains_vp_as_negative_us_relative():
    # USSR 2 -> 4 (Man in Earth Orbit 0/0) while the US is on 5: nothing to gain; use a scoring box instead.
    result = _play(_state(us=7, ussr=5), "ussr")
    game = result["game_data"]
    assert game["tracks"]["space_race"]["ussr"] == 7
    assert game["tracks"]["victory_points"] == -2


def test_not_behind_has_no_effect():
    state = _state(us=4, ussr=4)
    result = _play(state, "us")
    game = result["game_data"]
    assert game["tracks"]["space_race"] == {"us": 4, "ussr": 4}
    assert game["tracks"]["victory_points"] == 0


def test_ahead_player_has_no_effect():
    result = _play(_state(us=6, ussr=2), "us")
    assert result["game_data"]["tracks"]["space_race"]["us"] == 6
    assert result["game_data"]["tracks"]["victory_points"] == 0


def test_advance_is_capped_at_box_eight_and_awards_only_if_moved():
    result = _play(_state(us=7, ussr=8), "us")
    game = result["game_data"]
    assert game["tracks"]["space_race"]["us"] == 8
    # The USSR already holds the Space Station box, so the US is second there (2/0): no VP.
    assert game["tracks"]["victory_points"] == 0


def test_already_at_box_eight_behind_no_longer_possible_to_move():
    state = _state(us=8, ussr=8)
    result = _play(state, "us")
    assert result["game_data"]["tracks"]["victory_points"] == 0


def test_input_state_is_not_mutated():
    state = _state(us=1, ussr=4)
    before = deepcopy(state)
    _play(state, "us")
    assert state == before
