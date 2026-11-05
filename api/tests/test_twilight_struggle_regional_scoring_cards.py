from copy import deepcopy

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.scoring import resolve_scoring_card

DATA = load_country_data()


def _region(region):
    return [name for name, info in DATA["countries"].items() if info.get("region") == region]


def _battlegrounds(region):
    return [name for name in _region(region) if DATA["countries"][name].get("battleground")]


def _state(influences):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    for name, values in influences.items():
        countries[name].update(values)
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "turn": 1,
    }


def _scoring(name):
    return {"id": 0, "name": name, "scoring": True, "alignment": "both", "event_removed": False}


def test_africa_scoring_control_awards_control_value_plus_battlegrounds():
    # Control: US holds every Africa space with more influence than the USSR, including all battlegrounds.
    influences = {name: {"us": 10} for name in _region("Africa")}
    result = resolve_scoring_card(_state(influences), _scoring("Africa Scoring"), "us", DATA)
    expected = 6 + len(_battlegrounds("Africa"))
    assert result["score_result"]["control"]["us"] is True
    assert result["score_result"]["score"]["us"] == expected
    assert result["game_data"]["tracks"]["victory_points"] == expected


def test_africa_scoring_presence_awards_one_vp_without_battleground():
    non_bg = next(n for n in _region("Africa") if not DATA["countries"][n].get("battleground"))
    result = resolve_scoring_card(_state({non_bg: {"us": 10}}), _scoring("Africa Scoring"), "us", DATA)
    assert result["score_result"]["presence"]["us"] is True
    assert result["score_result"]["domination"]["us"] is False
    assert result["score_result"]["score"]["us"] == 1
    assert result["game_data"]["tracks"]["victory_points"] == 1


def test_south_america_scoring_control_awards_control_value_plus_battlegrounds():
    influences = {name: {"ussr": 10} for name in _region("South America")}
    result = resolve_scoring_card(_state(influences), _scoring("South America Scoring"), "us", DATA)
    expected_for_ussr = 6 + len(_battlegrounds("South America"))
    assert result["score_result"]["control"]["ussr"] is True
    assert result["score_result"]["score"]["ussr"] == expected_for_ussr
    assert result["game_data"]["tracks"]["victory_points"] == -expected_for_ussr


def test_south_america_scoring_presence_awards_two_vp_without_battleground():
    non_bg = next(n for n in _region("South America") if not DATA["countries"][n].get("battleground"))
    result = resolve_scoring_card(
        _state({non_bg: {"us": 10}}), _scoring("South America Scoring"), "us", DATA,
    )
    assert result["score_result"]["presence"]["us"] is True
    assert result["score_result"]["score"]["us"] == 2
    assert result["game_data"]["tracks"]["victory_points"] == 2
