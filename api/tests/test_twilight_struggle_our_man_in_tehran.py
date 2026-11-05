from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


class FixedRng:
    """Deterministic shuffle: leaves order unchanged so the test can assert contents."""

    def shuffle(self, items):
        return None

    def randint(self, low, high):
        return low


def _me_country():
    return next(name for name, info in DATA["countries"].items() if info.get("region") == "Middle East")


def _state(us_controls_me=True, deck_ids=(5, 7, 8, 9, 10, 11)):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    if us_controls_me:
        countries[_me_country()]["us"] = 10
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [deepcopy(CATALOG[i]) for i in deck_ids],
        "turn": 1,
    }


def _play(state, choices=None, rng=None, phasing="us"):
    return resolve_card_event(
        state, CATALOG[108], phasing, mode="event", country_data=DATA,
        rng=rng if rng is not None else FixedRng(), event_choices={"our_man_in_tehran": choices or []},
    )


def _ids(cards):
    return [c["id"] for c in cards]


def test_our_man_in_tehran_is_registered_as_handler():
    assert CATALOG[108]["effect_handler"] == "our_man_in_tehran"
    assert CATALOG[108]["alignment"] == "us"


def test_no_effect_without_us_middle_east_control():
    state = _state(us_controls_me=False)
    game = _play(state)["game_data"]
    assert _ids(game["draw_pile"]) == [5, 7, 8, 9, 10, 11]
    assert game["discard_pile"] == []


def test_discarding_chosen_cards_and_returning_rest_to_deck():
    game = _play(_state(), choices=[5, 8])["game_data"]
    assert _ids(game["discard_pile"]) == [5, 8]
    assert sorted(_ids(game["draw_pile"])) == [7, 9, 10, 11]
    assert game["hands"]["us"] == []


def test_discarding_nothing_returns_all_five_drawn_cards():
    game = _play(_state(), choices=[])["game_data"]
    assert game["discard_pile"] == []
    assert sorted(_ids(game["draw_pile"])) == [5, 7, 8, 9, 10, 11]


def test_only_top_five_cards_are_eligible():
    with pytest.raises(ValueError, match="drawn top 5"):
        _play(_state(), choices=[11])


def test_duplicate_choice_rejected():
    with pytest.raises(ValueError, match="distinct"):
        _play(_state(), choices=[5, 5])


def test_requires_server_rng():
    with pytest.raises(ValueError, match="server RNG"):
        resolve_card_event(
            _state(), CATALOG[108], "us", mode="event", country_data=DATA,
            rng=None, event_choices={"our_man_in_tehran": []},
        )


def test_ussr_cannot_play_our_man():
    with pytest.raises(ValueError, match="US card"):
        _play(_state(), phasing="ussr")


def test_short_deck_draws_what_remains():
    state = _state(deck_ids=(5, 7))
    game = _play(state, choices=[7])["game_data"]
    assert _ids(game["discard_pile"]) == [7]
    assert _ids(game["draw_pile"]) == [5]


def test_input_state_is_not_mutated():
    state = _state()
    before = deepcopy(state)
    _play(state, choices=[5])
    assert state == before
