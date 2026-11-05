"""Card 40: cancellation pays own influence, not a card or a turn."""
from copy import deepcopy

import pytest

from app.games.twilight_struggle.crisis import cancel_cuban_missile_crisis
from app.games.twilight_struggle.operations import resolve_operations_action
from app.games.twilight_struggle.serialize import serialize_game_state
from app.games.twilight_struggle.validator import TwilightStruggleValidator


def _state(faction="us", phase="action_round", influence=2):
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(5, ["alice", "bob"])
    gd["current_phase"] = phase
    gd["current_player"] = "bob"
    gd["current_player_faction"] = "ussr"
    gd["persistent_events"]["cuban_missile_crisis"] = {"faction": faction, "expires_turn": 1}
    country = "Turkey" if faction == "us" else "Cuba"
    gd["countries"][country][faction] = influence
    gd["countries"]["W. Germany"]["us"] = 0
    return validator, {"game_data": gd}, country


def _moves(validator, state, faction="us"):
    return [
        move for move in validator.get_legal_moves(state, "alice" if faction == "us" else "bob")
        if move["type"] == "cancel_cuban_missile_crisis"
    ]


@pytest.mark.parametrize("faction", ["us", "ussr"])
@pytest.mark.parametrize("phase", ["headline", "headline_reveal_ready", "action_round", "turn_end"])
def test_cancellation_is_available_at_live_move_boundaries_without_advancing_turn(faction, phase):
    validator, state, country = _state(faction, phase)
    before = deepcopy(state)
    move, = _moves(validator, state, faction)
    assert move["country"] == country
    assert validator.validate_move(state, move)
    after = validator.apply_move(state, move)["game_data"]
    expected = deepcopy(before["game_data"])
    expected["countries"][country][faction] -= 2
    del expected["persistent_events"]["cuban_missile_crisis"]
    assert after == expected
    assert state == before
    assert not validator.validate_move({"game_data": after}, move)


def test_us_can_pay_in_either_one_country_but_cannot_split_payment():
    validator, state, _ = _state(influence=1)
    state["game_data"]["countries"]["W. Germany"]["us"] = 1
    assert not _moves(validator, state)
    state["game_data"]["countries"]["Turkey"]["us"] = 3
    state["game_data"]["countries"]["W. Germany"]["us"] = 2
    assert {move["country"] for move in _moves(validator, state)} == {"Turkey", "W. Germany"}


@pytest.mark.parametrize("reason", ["expired", "game_over", "terminal", "other_faction", "wrong_country", "insufficient"])
def test_invalid_cancellation_fails_closed_and_is_atomic(reason):
    validator, state, country = _state()
    move, = _moves(validator, state)
    gd = state["game_data"]
    if reason == "expired":
        gd["turn"] = 2
    elif reason == "game_over":
        gd["game_over"] = True
    elif reason == "terminal":
        gd["terminal_result"] = {"winner": "ussr", "reason": "twenty_vp"}
    elif reason == "other_faction":
        move["player_id"] = "bob"
    elif reason == "wrong_country":
        move["country"] = "Iran"
    else:
        gd["countries"][country]["us"] = 1
    before = deepcopy(state)
    assert not validator.validate_move(state, move)
    with pytest.raises(ValueError):
        validator.apply_move(state, move)
    assert state == before


def test_cancellation_allows_future_coup_and_does_not_change_defcon():
    validator, state, country = _state()
    gd = state["game_data"]
    gd["tracks"]["defcon"] = 2
    gd["countries"]["Guatemala"]["ussr"] = 1
    move, = _moves(validator, state)
    cancelled = validator.apply_move(state, move)["game_data"]
    action = {"type": "coup", "country": "Guatemala", "die_roll": 6}
    assert resolve_operations_action(gd, "us", 3, action)["terminal_result"]["winner"] == "ussr"
    assert resolve_operations_action(cancelled, "us", 3, action)["terminal_result"] is None
    assert cancelled["tracks"]["defcon"] == 2


def test_cancellation_does_not_reveal_private_state():
    validator, state, country = _state(phase="headline")
    gd = state["game_data"]
    gd["headline_cards"]["ussr"] = gd["hands"]["ussr"][0]["id"]
    after = cancel_cuban_missile_crisis(gd, "us", country)
    for viewer in ("us", "ussr", None):
        projection = serialize_game_state(after, viewer)
        assert not {"hands", "draw_pile", "headline_cards", "rng_seed", "rng_state_json"} & projection.keys()
        assert projection["hand"] == (after["hands"][viewer] if viewer else None)
        assert projection["current_player"] == "bob"


def test_payment_removes_exactly_two_own_influence_and_only_crisis_flag():
    validator, state, country = _state(influence=5)
    state["game_data"]["countries"][country]["ussr"] = 4
    state["game_data"]["persistent_events"]["salt_negotiations"] = {"expires_turn": 1}
    move, = _moves(validator, state)
    after = validator.apply_move(state, move)["game_data"]
    assert after["countries"][country] == {"us": 3, "ussr": 4}
    assert after["persistent_events"] == {"salt_negotiations": {"expires_turn": 1}}


def test_missing_crisis_and_unknown_player_cannot_cancel():
    validator, state, country = _state()
    move, = _moves(validator, state)
    assert not validator.validate_move(state, {**move, "player_id": "intruder"})
    del state["game_data"]["persistent_events"]["cuban_missile_crisis"]
    assert not validator.validate_move(state, move)
    with pytest.raises(ValueError):
        cancel_cuban_missile_crisis(state["game_data"], "us", country)


@pytest.mark.parametrize("phase", ["headline", "headline_reveal_ready", "action_round", "turn_end"])
def test_legacy_rl_root_ignores_cancellation_without_changing_action_ids(phase):
    from app.games.twilight_struggle.rl_adapter import ACTION_COUNT, TwilightStruggleReferenceEnv

    env = TwilightStruggleReferenceEnv()
    env.reset(5)
    gd = env.game_data
    gd["current_phase"] = phase
    gd["persistent_events"]["cuban_missile_crisis"] = {"faction": "ussr", "expires_turn": 1}
    gd["countries"]["Cuba"]["ussr"] = 2
    assert any(move["type"] == "cancel_cuban_missile_crisis" for move in env.validator.get_legal_moves(env.state, env.current_player))
    options = env._root_options()
    assert ACTION_COUNT == 781
    assert all(0 <= action < ACTION_COUNT for action in options)
    assert all(option[1]["type"] != "cancel_cuban_missile_crisis" for option in options.values() if option[0] == "move")