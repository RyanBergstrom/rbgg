from copy import deepcopy

import pytest

from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.scoring import resolve_scoring_card, score_region

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


def _battleground(region):
    return next(
        name for name, info in DATA["countries"].items()
        if info.get("region") == region and info.get("battleground")
    )


def _state(persistent=None):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [deepcopy(CATALOG[73])], "ussr": []},
        "persistent_events": dict(persistent or {}),
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "actions_taken": {"us": 0, "ussr": 0},
        "turn": 1,
    }


def _scoring(name):
    return {"id": 0, "name": name, "scoring": True, "alignment": "both", "event_removed": False}


def test_shuttle_diplomacy_is_registered_as_handler():
    assert CATALOG[73]["effect_handler"] == "shuttle_diplomacy"
    assert CATALOG[73]["alignment"] == "us"


def test_shuttle_diplomacy_event_stays_in_play_in_front_of_us():
    result = resolve_card_event(_state(), CATALOG[73], "us", mode="event", country_data=DATA)
    assert result["card_in_play"] is True
    entry = result["game_data"]["persistent_events"]["shuttle_diplomacy"]
    assert entry["faction"] == "us"
    assert entry["card"]["id"] == 73
    assert result["game_data"]["discard_pile"] == []


def test_play_card_action_keeps_shuttle_diplomacy_out_of_discard():
    result = play_card_action(_state(), "us", 73, "event", country_data=DATA)
    assert "shuttle_diplomacy" in result["persistent_events"]
    assert all(card["id"] != 73 for card in result["discard_pile"])
    assert result["hands"]["us"] == []


def test_second_shuttle_diplomacy_is_rejected_while_in_play():
    in_play = resolve_card_event(_state(), CATALOG[73], "us", mode="event", country_data=DATA)["game_data"]
    with pytest.raises(ValueError, match="already in play"):
        resolve_card_event(in_play, CATALOG[73], "us", mode="event", country_data=DATA)


def test_shuttle_diplomacy_rejects_ussr_play():
    with pytest.raises(ValueError, match="US card"):
        resolve_card_event(_state(), CATALOG[73], "ussr", mode="event", country_data=DATA)


def test_ussr_battleground_penalty_reduces_middle_east_score_by_one_battleground():
    name = _battleground("Middle East")
    influences = {name: {"ussr": 10}}
    plain = score_region("Middle East", influences, DATA)
    penalized = score_region("Middle East", influences, DATA, ussr_battleground_penalty=1)
    assert plain["battleground_count"]["ussr"] == 1
    assert penalized["score"]["ussr"] < plain["score"]["ussr"]
    assert penalized["score"]["us"] == plain["score"]["us"]
    assert penalized["battleground_count"]["ussr"] == 1


def test_middle_east_scoring_applies_penalty_then_discards_shuttle_diplomacy():
    name = _battleground("Middle East")
    in_play = resolve_card_event(_state(), CATALOG[73], "us", mode="event", country_data=DATA)["game_data"]
    in_play["countries"][name]["ussr"] = 10
    baseline = deepcopy(in_play)
    baseline["persistent_events"].pop("shuttle_diplomacy")
    expected = resolve_scoring_card(baseline, _scoring("Middle East Scoring"), "us", DATA)
    result = resolve_scoring_card(in_play, _scoring("Middle East Scoring"), "us", DATA)
    game = result["game_data"]
    assert "shuttle_diplomacy" not in game["persistent_events"]
    assert game["discard_pile"][-1]["id"] == 73
    assert result["score_result"]["score"]["ussr"] < expected["score_result"]["score"]["ussr"]
    assert game["tracks"]["victory_points"] > expected["game_data"]["tracks"]["victory_points"]


def test_non_matching_region_scoring_does_not_consume_shuttle_diplomacy():
    in_play = resolve_card_event(_state(), CATALOG[73], "us", mode="event", country_data=DATA)["game_data"]
    result = resolve_scoring_card(in_play, _scoring("Africa Scoring"), "us", DATA)
    assert "shuttle_diplomacy" in result["game_data"]["persistent_events"]
    assert result["game_data"]["discard_pile"] == []
