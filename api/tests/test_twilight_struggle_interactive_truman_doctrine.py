"""Interactive Truman Doctrine country selection."""
from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {card["id"]: card for card in load_standard_card_catalog()}
DATA = load_country_data()


def _setup():
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(19)
    gd.update(current_phase="action_round", current_player="player_1", current_player_faction="us")
    gd["hands"]["us"] = [CARDS[19]]
    # A controlled country and a non-European country must not appear among choices.
    gd["countries"]["France"] = {"us": 5, "ussr": 0}
    gd["countries"]["Poland"] = {"us": 1, "ussr": 5}
    gd["countries"]["Japan"] = {"us": 0, "ussr": 0}
    return validator, {"game_data": gd}


def _eligible(state):
    board = state["game_data"]["countries"]
    return {
        name for name, country in DATA["countries"].items()
        if country.get("region") == "Europe" and name in board
        and not (board[name]["us"] - board[name]["ussr"] >= country["stability"]
                 or board[name]["ussr"] - board[name]["us"] >= country["stability"])
    }


def test_us_sponsor_selects_uncontrolled_european_country_and_resolves_once():
    validator, state = _setup()
    assert "interactive_modes" in next(
        move for move in validator.get_legal_moves(state, "player_1") if move.get("card_id") == 19
    )
    commit = {"type": "play_card", "player_id": "player_1", "card_id": 19,
              "mode": "event", "interactive": True}
    assert validator.validate_move(state, commit)
    staged = validator.apply_move(state, commit)
    options = validator.get_legal_moves(staged, "player_1")
    assert {move["country"] for move in options} == _eligible(staged)
    assert validator.get_legal_moves(staged, "player_2") == []

    target = sorted(_eligible(staged))[0]
    staged["game_data"]["countries"][target]["ussr"] = 2
    response = {"type": "event_response", "player_id": "player_1",
                "decision": "choose_country", "country": target}
    # The live board still determines eligibility; choose another valid target if this one became controlled.
    if target not in _eligible(staged):
        target = sorted(_eligible(staged))[0]
        response["country"] = target
    staged["game_data"]["countries"][target]["ussr"] = 2
    assert validator.validate_move(staged, response)
    final = validator.apply_move(staged, response)["game_data"]
    assert final["countries"][target]["ussr"] == 0
    assert final["actions_taken"]["us"] == 1
    assert any(card["id"] == 19 for card in final["removed_cards"])
    assert "_pending_event" not in final


def test_wrong_actor_invalid_target_and_injected_payload_are_atomic():
    validator, state = _setup()
    staged = validator.apply_move(state, {
        "type": "play_card", "player_id": "player_1", "card_id": 19,
        "mode": "event", "interactive": True,
    })
    bad_moves = [
        {"type": "event_response", "player_id": "player_2", "decision": "choose_country", "country": "E. Germany"},
        {"type": "event_response", "player_id": "player_1", "decision": "choose_country", "country": "France"},
        {"type": "event_response", "player_id": "player_1", "decision": "choose_country", "country": "Japan"},
        {"type": "event_response", "player_id": "player_1", "decision": "choose_country",
         "country": sorted(_eligible(staged))[0],
         "event_choices": {"truman_doctrine": sorted(_eligible(staged))[0]}},
    ]
    for move in bad_moves:
        before = deepcopy(staged)
        assert not validator.validate_move(staged, move)
        with pytest.raises(ValueError):
            validator.apply_move(staged, move)
        assert staged == before


def test_interactive_mode_is_not_offered_when_no_uncontrolled_european_country_exists():
    validator, state = _setup()
    for name, country in DATA["countries"].items():
        if country.get("region") == "Europe":
            state["game_data"]["countries"][name] = {"us": country["stability"], "ussr": 0}
    card_move = next(move for move in validator.get_legal_moves(state, "player_1") if move.get("card_id") == 19)
    assert "interactive_modes" not in card_move or "event" not in card_move["interactive_modes"]
    interactive = {"type": "play_card", "player_id": "player_1", "card_id": 19,
                   "mode": "event", "interactive": True}
    before = deepcopy(state)
    assert not validator.validate_move(state, interactive)
    with pytest.raises(ValueError):
        validator.apply_move(state, interactive)
    assert state == before