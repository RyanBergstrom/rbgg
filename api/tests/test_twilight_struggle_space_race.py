"""Space Race track (rules 6.4): attempts, awards, special abilities, and card-play integration."""
import pytest

from app.games.twilight_struggle.space_race import (
    SPACE_RACE_BOXES,
    advance_marker_in_place,
    attempt_space_race,
    attempts_this_turn,
    has_space_ability,
    held_card_decision_pending,
    record_held_card_decision,
    space_race_vp,
)
from app.games.twilight_struggle.turns import faction_action_limit
from app.games.twilight_struggle.validator import TwilightStruggleValidator


class FixedRoll:
    def __init__(self, value):
        self.value = value

    def randint(self, low, high):
        assert (low, high) == (1, 6)
        return self.value


def _game(us=0, ussr=0, vp=0, turn=1):
    return {
        "turn": turn,
        "tracks": {"victory_points": vp, "defcon": 5, "space_race": {"us": us, "ussr": ussr}},
        "hands": {"us": [], "ussr": []},
    }


def test_track_matches_printed_board():
    assert {box: info[1:] for box, info in SPACE_RACE_BOXES.items()} == {
        1: (2, 3, 2, 1), 2: (2, 4, 0, 0), 3: (2, 3, 2, 0), 4: (2, 4, 0, 0),
        5: (3, 3, 3, 1), 6: (3, 4, 0, 0), 7: (3, 3, 4, 2), 8: (4, 2, 2, 0),
    }


def test_first_to_reach_gets_first_vp_second_gets_second_vp():
    assert space_race_vp(5, opponent_box=4) == 3
    assert space_race_vp(5, opponent_box=5) == 1
    assert space_race_vp(5, opponent_box=8) == 1


def test_successful_attempt_moves_marker_and_awards_us_relative_vp():
    game = _game()
    outcome = attempt_space_race(game, "us", 2, FixedRoll(3))
    assert outcome["success"] and outcome["vp"] == 2
    assert game["tracks"]["space_race"]["us"] == 1
    assert game["tracks"]["victory_points"] == 2
    ussr_game = _game()
    attempt_space_race(ussr_game, "ussr", 2, FixedRoll(1))
    assert ussr_game["tracks"]["victory_points"] == -2


def test_roll_above_range_fails_and_still_uses_the_attempt():
    game = _game()
    outcome = attempt_space_race(game, "us", 2, FixedRoll(4))
    assert not outcome["success"]
    assert game["tracks"]["space_race"]["us"] == 0
    assert attempts_this_turn(game, "us") == 1
    assert game["tracks"]["victory_points"] == 0


def test_second_to_reach_a_box_gets_second_award():
    game = _game(us=0, ussr=1)
    outcome = attempt_space_race(game, "us", 2, FixedRoll(1))
    assert outcome["vp"] == 1
    assert game["tracks"]["victory_points"] == 1


def test_card_must_meet_next_box_operations():
    game = _game(us=4)  # next is box 5, needs 3 Ops
    with pytest.raises(ValueError, match="at least 3"):
        attempt_space_race(game, "us", 2, FixedRoll(1))
    assert attempts_this_turn(game, "us") == 0


def test_one_attempt_per_turn_by_default():
    game = _game()
    attempt_space_race(game, "us", 2, FixedRoll(6))
    with pytest.raises(ValueError, match="No Space Race attempts"):
        attempt_space_race(game, "us", 2, FixedRoll(1))


def test_animal_in_space_allows_two_attempts_until_opponent_reaches_it():
    game = _game(us=2, ussr=0)
    assert has_space_ability(game, "us", 2)
    attempt_space_race(game, "us", 2, FixedRoll(6))
    attempt_space_race(game, "us", 3, FixedRoll(6))
    with pytest.raises(ValueError):
        attempt_space_race(game, "us", 3, FixedRoll(6))
    game["tracks"]["space_race"]["ussr"] = 2
    assert not has_space_ability(game, "us", 2)


def test_final_box_ends_space_race_for_that_faction():
    game = _game(us=8)
    with pytest.raises(ValueError, match="complete"):
        attempt_space_race(game, "us", 4, FixedRoll(1))


def test_space_station_needs_four_ops_and_a_roll_of_one_or_two():
    game = _game(us=7)
    with pytest.raises(ValueError):
        attempt_space_race(game, "us", 3, FixedRoll(1))
    assert not attempt_space_race(_game(us=7), "us", 4, FixedRoll(3))["success"]
    assert attempt_space_race(game, "us", 4, FixedRoll(2))["success"]


def test_twenty_vp_ends_the_game():
    game = _game(vp=19)
    outcome = attempt_space_race(game, "us", 2, FixedRoll(1))
    assert outcome["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}


def test_advance_marker_awards_only_the_landing_box_and_caps_at_final_box():
    game = _game(us=7, ussr=0)
    assert advance_marker_in_place(game, "us", 2) == 2
    assert game["tracks"]["space_race"]["us"] == 8
    assert advance_marker_in_place(game, "us", 1) == 0


def test_space_station_grants_eight_action_rounds_to_first_faction_only():
    game = _game(us=8, ussr=7, turn=2)
    assert faction_action_limit(game, "us") == 8
    assert faction_action_limit(game, "ussr") == 6
    game["tracks"]["space_race"]["ussr"] = 8
    assert faction_action_limit(game, "us") == 6


def test_attempts_and_held_card_decisions_are_scoped_to_the_turn():
    game = _game(turn=2)
    attempt_space_race(game, "us", 2, FixedRoll(6))
    game["hands"]["us"] = [{"id": 1}]
    game["tracks"]["space_race"]["us"] = 6
    record_held_card_decision(game, "us")
    assert attempts_this_turn(game, "us") == 1 and held_card_decision_pending(game) == []
    game["turn"] = 3
    assert attempts_this_turn(game, "us") == 0
    assert held_card_decision_pending(game) == ["us"]


# ---- validator integration -------------------------------------------------------------------

PLAYERS = ["alice", "bob"]  # alice = US, bob = USSR
EVENTLESS = {"operations": 3, "scoring": False, "era": 1, "effect_handler": "no_such_handler"}


def _state(phase="action_round", acting="ussr", us=0, ussr=0, hands=None):
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(5, PLAYERS)
    gd["current_phase"] = phase
    gd["current_player_faction"] = acting
    gd["current_player"] = gd["player_by_faction"][acting]
    gd["tracks"]["space_race"] = {"us": us, "ussr": ussr}
    gd["hands"] = hands or {
        "us": [{"id": 900, "name": "Eventless US", "alignment": "ussr", **EVENTLESS}],
        "ussr": [{"id": 901, "name": "Eventless USSR", "alignment": "us", **EVENTLESS}],
    }
    return validator, {"players": [{"player_id": p} for p in PLAYERS], "game_data": gd}


def _space_move(validator, state, card_id=901, player="bob"):
    return {
        "move_id": "space", "type": "play_card", "player_id": player, "card_id": card_id,
        "mode": "operations", "operations_action": {"type": "space_race"},
    }


def test_space_race_play_discards_card_without_triggering_its_event():
    validator, state = _state()
    move = _space_move(validator, state)
    # Played for ordinary Ops this card's opponent event would raise (no handler); Space Race skips it.
    assert validator.validate_move(state, move)
    after = validator.apply_move(state, move)["game_data"]
    assert [card["id"] for card in after["discard_pile"]][-1] == 901
    assert after["hands"]["ussr"] == []
    assert after["actions_taken"]["ussr"] == 1
    assert attempts_this_turn(after, "ussr") == 1
    result = after["last_card_play"]["operations_result"]
    assert result["type"] == "space_race"
    assert result["success"] == (result["roll"] <= 3)
    assert after["tracks"]["space_race"]["ussr"] == (1 if result["success"] else 0)
    assert after["last_card_play"]["event_triggered"] is False


def test_space_race_play_is_rejected_when_attempts_used_or_ops_too_low():
    validator, state = _state()
    state["game_data"]["space_attempts"] = {"turn": state["game_data"]["turn"], "ussr": 1}
    assert not validator.validate_move(state, _space_move(validator, state))
    validator, state = _state(ussr=4)  # box 5 needs 3 Ops
    state["game_data"]["hands"]["ussr"][0]["operations"] = 2
    assert not validator.validate_move(state, _space_move(validator, state))


def test_space_race_cannot_use_scoring_card_or_china_card():
    validator, state = _state()
    state["game_data"]["hands"]["ussr"][0].update({"scoring": True})
    assert not validator.validate_move(state, _space_move(validator, state))
    validator, state = _state()
    assert not validator.validate_move(state, _space_move(validator, state, card_id=6))


def test_man_in_earth_orbit_holder_commits_headline_after_opponent():
    validator, state = _state(phase="headline", ussr=4, us=0)
    state["game_data"]["hands"] = TwilightStruggleValidator().initial_game_data(5, PLAYERS)["hands"]
    assert validator.get_legal_moves(state, "bob") == []
    assert validator.get_legal_moves(state, "alice")
    state["game_data"]["tracks"]["space_race"]["us"] = 4  # opponent reaches box 4: ability cancelled
    assert validator.get_legal_moves(state, "bob")


def test_eagle_landed_holder_may_discard_held_card_before_turn_closes():
    hands = {"us": [{"id": 900, "name": "Held", "alignment": "us", **EVENTLESS}], "ussr": []}
    validator, state = _state(phase="turn_end", acting="ussr", us=6, ussr=5, hands=hands)
    gd = state["game_data"]
    gd["actions_taken"] = {"us": 6, "ussr": 6}
    assert held_card_decision_pending(gd) == ["us"]
    assert validator.get_legal_moves(state, "bob") == []
    moves = validator.get_legal_moves(state, "alice")
    assert {move["type"] for move in moves} == {"discard_held_card", "keep_held_card"}
    discard = next(move for move in moves if move["type"] == "discard_held_card")
    assert validator.validate_move(state, discard)
    after = validator.apply_move(state, discard)
    assert after["game_data"]["hands"]["us"] == []
    assert after["game_data"]["discard_pile"][-1]["id"] == 900
    assert held_card_decision_pending(after["game_data"]) == []
    assert after["game_data"]["current_player"] == "bob"
    assert [m["type"] for m in validator.get_legal_moves(after, "bob")] == ["finish_turn"]


def test_keeping_the_held_card_also_closes_the_decision():
    hands = {"us": [{"id": 900, "name": "Held", "alignment": "us", **EVENTLESS}], "ussr": []}
    validator, state = _state(phase="turn_end", acting="ussr", us=6, ussr=0, hands=hands)
    state["game_data"]["actions_taken"] = {"us": 6, "ussr": 6}
    keep = next(m for m in validator.get_legal_moves(state, "alice") if m["type"] == "keep_held_card")
    after = validator.apply_move(state, keep)
    assert after["game_data"]["hands"]["us"][0]["id"] == 900
    assert held_card_decision_pending(after["game_data"]) == []


def test_validate_rejects_discard_by_faction_without_ability():
    hands = {"us": [{"id": 900, "name": "Held", "alignment": "us", **EVENTLESS}], "ussr": []}
    validator, state = _state(phase="turn_end", acting="ussr", us=6, ussr=6, hands=hands)
    state["game_data"]["actions_taken"] = {"us": 6, "ussr": 6}
    move = {"move_id": "x", "type": "discard_held_card", "player_id": "alice", "card_id": 900}
    assert not validator.validate_move(state, move)
