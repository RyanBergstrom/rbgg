from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


class FixedRng:
    def __init__(self, *values):
        self._values = list(values)

    def randint(self, low, high):
        value = self._values.pop(0)
        assert low <= value <= high
        return value


def _state(iraq_ussr=0, neighbor_ussr=0, us_military=0):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    countries["Iraq"]["ussr"] = iraq_ussr
    if neighbor_ussr:
        neighbor = next(n for n in DATA["adjacency"]["Iraq"] if n != "Iran")
        countries[neighbor]["ussr"] = neighbor_ussr
    return {
        "countries": countries,
        "tracks": {
            "victory_points": 0,
            "defcon": 5,
            "military_operations": {"us": us_military, "ussr": 0},
        },
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "turn": 1,
    }


def _play(state, invader="Iran", rng=None, phasing="us"):
    return resolve_card_event(
        state, CATALOG[102], phasing, mode="event", country_data=DATA,
        rng=rng, event_choices={"iran_iraq_war": invader},
    )


def test_iran_iraq_war_is_registered_as_handler():
    assert CATALOG[102]["effect_handler"] == "iran_iraq_war"
    assert CATALOG[102]["alignment"] == "both"
    assert CATALOG[102]["operations"] == 2


def test_requires_invader_choice():
    with pytest.raises(ValueError, match="Iran or Iraq"):
        resolve_card_event(
            _state(), CATALOG[102], "us", mode="event", country_data=DATA,
            rng=FixedRng(6), event_choices={},
        )


def test_requires_server_rng():
    with pytest.raises(ValueError, match="server RNG"):
        _play(_state(), rng=None)


def test_victory_gives_two_vp_and_replaces_opponent_influence_in_target():
    result = _play(_state(iraq_ussr=3), invader="Iran", rng=FixedRng(6))
    game = result["game_data"]
    assert game["tracks"]["victory_points"] == 2
    assert game["countries"]["Iraq"] == {"us": 3, "ussr": 0}


def test_failure_only_adds_military_operations():
    result = _play(_state(iraq_ussr=3), invader="Iran", rng=FixedRng(3))
    game = result["game_data"]
    assert game["tracks"]["victory_points"] == 0
    assert game["countries"]["Iraq"] == {"us": 0, "ussr": 3}
    assert game["tracks"]["military_operations"]["us"] == 2


def test_invader_iraq_targets_iran():
    result = _play(_state(), invader="Iraq", rng=FixedRng(6))
    game = result["game_data"]
    assert game["tracks"]["victory_points"] == 2


def test_opponent_adjacent_control_reduces_roll():
    # Roll 4 would win, but one USSR-controlled neighbor of Iraq subtracts 1 -> 3, a failure.
    result = _play(_state(neighbor_ussr=10), invader="Iran", rng=FixedRng(4))
    assert result["game_data"]["tracks"]["victory_points"] == 0


def test_military_ops_added_on_play_regardless_of_outcome():
    result = _play(_state(us_military=1), invader="Iran", rng=FixedRng(1))
    assert result["game_data"]["tracks"]["military_operations"]["us"] == 3


def test_input_state_is_not_mutated():
    state = _state(iraq_ussr=3)
    before = deepcopy(state)
    _play(state, rng=FixedRng(6))
    assert state == before


@pytest.mark.parametrize("invader,target", [("Iran", "Iraq"), ("Iraq", "Iran")])
@pytest.mark.parametrize("faction,opponent,sign", [("us", "ussr", 1), ("ussr", "us", -1)])
def test_invader_choice_replaces_only_target_influence(invader, target, faction, opponent, sign):
    state = _state()
    state["countries"][invader] = {"us": 1, "ussr": 1}
    state["countries"][target] = {faction: 2, opponent: 3}
    result = _play(state, invader=invader, phasing=faction, rng=FixedRng(4))
    assert result["game_data"]["countries"][target] == {faction: 5, opponent: 0}
    assert result["game_data"]["countries"][invader] == state["countries"][invader]
    assert result["game_data"]["tracks"]["victory_points"] == sign * 2


def test_war_is_not_a_coup_and_ignores_coup_only_restrictions():
    state = _state()
    state["tracks"]["defcon"] = 2
    state["persistent_events"] = {
        "salt_negotiations": {"expires_turn": 1},
        "cuban_missile_crisis": {"faction": "us", "expires_turn": 1},
    }
    result = _play(state, rng=FixedRng(4))
    assert result["game_data"]["tracks"]["victory_points"] == 2
    assert result["game_data"]["tracks"]["defcon"] == 2
    assert result["terminal_result"] is None


def test_war_victory_immediately_ends_game_at_twenty_vp():
    state = _state()
    state["tracks"]["victory_points"] = 19
    result = _play(state, rng=FixedRng(6))
    assert result["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}


@pytest.mark.parametrize("mode", ["event", "operations", "space"])
def test_flower_power_applies_except_when_war_card_is_spaced(mode):
    from app.games.twilight_struggle.actions import play_card_action

    state = _state()
    state["hands"]["us"] = [CATALOG[102]]
    state["persistent_events"]["flower_power"] = {"faction": "ussr", "expires_turn": 10}
    state["tracks"]["space_race"] = {"us": 0, "ussr": 0}
    action = {"type": "space_race"} if mode == "space" else {"type": "influence", "placements": []}
    result = play_card_action(
        state, "us", 102, "operations" if mode == "space" else mode,
        operations_action=action, event_choices={"iran_iraq_war": "Iran"}, rng=FixedRng(1),
    )
    # The war fails on 1: Flower Power costs 2 VP. Spacing instead earns 2 VP without that penalty.
    assert result["tracks"]["victory_points"] == (2 if mode == "space" else -2)


def test_validator_propagates_war_victory_and_card_removal():
    from app.games.twilight_struggle.validator import TwilightStruggleValidator

    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(5)
    gd.update(_state())
    gd.update(current_phase="action_round", current_player="player_1", current_player_faction="us")
    gd["tracks"]["victory_points"] = 19
    gd["hands"]["us"] = [CATALOG[102]]
    gd["rng_state_json"] = "{}"  # seed 5 starts with a winning roll
    move = {
        "type": "play_card", "player_id": "player_1", "card_id": 102, "mode": "event",
        "event_choices": {"iran_iraq_war": "Iraq"},
    }
    state = {"game_data": gd}
    before = deepcopy(state)
    assert validator.validate_move(state, move)
    after = validator.apply_move(state, move)["game_data"]
    assert after["current_phase"] == "game_over"
    assert after["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}
    assert after["removed_cards"][-1]["id"] == 102
    assert state == before
