from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


def _state(hand_ids=(4, 1, 2), deck_ids=(5, 7, 8, 9)):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [deepcopy(CATALOG[i]) for i in hand_ids], "ussr": []},
        "draw_pile": [deepcopy(CATALOG[i]) for i in deck_ids],
        "discard_pile": [],
        "removed_cards": [],
        "persistent_events": {},
        "turn": 1,
    }


def _ids(cards):
    return [card["id"] for card in cards]


def _event(state, choices, mode="event", phasing="us"):
    return resolve_card_event(
        state, CATALOG[77], phasing, mode=mode, country_data=DATA, event_choices={"ask_not_what": choices},
    )


def test_ask_not_is_registered_as_handler():
    assert CATALOG[77]["effect_handler"] == "ask_not_what"
    assert CATALOG[77]["operations"] == 3


def test_discarding_chosen_cards_draws_same_number_from_deck_top():
    result = _event(_state(), [4, 2])
    game = result["game_data"]
    assert _ids(game["hands"]["us"]) == [1, 5, 7]
    assert _ids(game["discard_pile"]) == [4, 2]
    assert _ids(game["draw_pile"]) == [8, 9]
    assert result["event_triggered"] is True


def test_discard_may_include_scoring_cards():
    state = _state()
    state["hands"]["us"][0]["scoring"] = True
    result = _event(state, [4])
    assert 4 in _ids(result["game_data"]["discard_pile"])
    assert _ids(result["game_data"]["hands"]["us"]) == [1, 2, 5]


def test_discarding_nothing_leaves_hand_and_deck_unchanged():
    state = _state()
    game = _event(state, [])["game_data"]
    assert _ids(game["hands"]["us"]) == [4, 1, 2]
    assert _ids(game["draw_pile"]) == [5, 7, 8, 9]
    assert game["discard_pile"] == []


def test_discarding_entire_hand_draws_entire_hand_from_deck():
    game = _event(_state(), [4, 1, 2])["game_data"]
    assert _ids(game["hands"]["us"]) == [5, 7, 8]
    assert _ids(game["discard_pile"]) == [4, 1, 2]
    assert _ids(game["draw_pile"]) == [9]


def test_ask_not_rejects_card_not_in_hand():
    with pytest.raises(ValueError, match="only discard cards from hand"):
        _event(_state(), [99])


def test_ask_not_rejects_duplicate_choice():
    with pytest.raises(ValueError, match="same card twice"):
        _event(_state(), [4, 4])


def test_ask_not_rejects_non_list_choice():
    with pytest.raises(ValueError, match="list of card ids"):
        _event(_state(), 4)


def test_ask_not_fails_closed_when_deck_is_short():
    with pytest.raises(ValueError, match="draw pile"):
        _event(_state(deck_ids=(5,)), [4, 1])


def test_ask_not_in_operations_mode_without_own_event_is_inert():
    state = _state()
    result = resolve_card_event(
        state, CATALOG[77], "us", mode="operations", country_data=DATA,
        event_choices={"ask_not_what": [4]},
    )
    assert result["event_triggered"] is False
    assert _ids(result["game_data"]["hands"]["us"]) == [4, 1, 2]
