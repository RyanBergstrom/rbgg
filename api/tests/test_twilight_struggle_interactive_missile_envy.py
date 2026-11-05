"""Missile Envy's tied-highest-Ops choice belongs to the opponent."""
from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.serialize import serialize_game_state
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {card["id"]: card for card in load_standard_card_catalog()}


def _setup():
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(39)
    gd.update(current_phase="action_round", current_player="player_1", current_player_faction="us")
    gd["hands"] = {"us": [CARDS[49]], "ussr": [CARDS[87], CARDS[7], CARDS[24]]}
    return validator, {"game_data": gd}


def _commit(validator, state):
    move = {"type": "play_card", "player_id": "player_1", "card_id": 49,
            "mode": "event", "interactive": True}
    assert validator.validate_move(state, move)
    return validator.apply_move(state, move)


def test_interactive_missile_envy_offers_tied_highest_cards_only_to_opponent():
    validator, state = _setup()
    before = deepcopy(state)
    staged = _commit(validator, state)
    gd = staged["game_data"]
    assert gd["current_phase"] == "event_response"
    assert gd["current_player"] == "player_2"
    choices = validator.get_legal_moves(staged, "player_2")
    assert {move["card_id"] for move in choices} == {7, 87}
    assert validator.get_legal_moves(staged, "player_1") == []
    assert gd["hands"]["ussr"] == [CARDS[87], CARDS[7], CARDS[24]]
    assert gd["hands"]["us"] == []
    assert gd.get("actions_taken", {}).get("us", 0) == 0
    assert state == before
    view = serialize_game_state(gd, "us")
    assert view["pending_event"]["card_id"] == 49
    assert "eligible_cards" not in view["pending_event"]


@pytest.mark.parametrize("selected_id", [7, 87])
def test_opponent_selection_exchanges_exact_tied_card_and_matches_inline(selected_id):
    validator, state = _setup()
    staged = _commit(validator, state)
    response = {"type": "event_response", "player_id": "player_2",
                "decision": "choose_card", "card_id": selected_id}
    assert validator.validate_move(staged, response)
    after = validator.apply_move(staged, response)
    inline = validator.apply_move(state, {
        "type": "play_card", "player_id": "player_1", "card_id": 49, "mode": "event",
        "event_choices": {"missile_envy_card_id": selected_id},
    })
    gd = after["game_data"]
    inline_gd = inline["game_data"]
    assert gd["hands"] == inline_gd["hands"]
    assert gd["hands"]["us"] == [CARDS[selected_id]]
    assert {card["id"] for card in gd["hands"]["ussr"]} == {49, 87 if selected_id == 7 else 7, 24}
    assert gd["persistent_events"]["missile_envy"] == {
        "faction": "ussr", "card_id": 49, "pending": True,
    }
    assert gd["actions_taken"] == inline_gd["actions_taken"] == {"us": 1, "ussr": 0}
    assert gd["last_card_play"]["card_id"] == 49
    assert gd["discard_pile"] == inline_gd["discard_pile"]
    assert not any(card["id"] == 49 for card in gd["discard_pile"])
    assert "_pending_event" not in gd


def test_legacy_tie_fallback_remains_hand_order_and_explicit_choice_must_be_tied():
    validator, state = _setup()
    legacy = validator.apply_move(state, {
        "type": "play_card", "player_id": "player_1", "card_id": 49, "mode": "event",
    })
    assert legacy["game_data"]["hands"]["us"] == [CARDS[87]]
    with pytest.raises(ValueError, match="tied for highest"):
        validator.apply_move(state, {
            "type": "play_card", "player_id": "player_1", "card_id": 49, "mode": "event",
            "event_choices": {"missile_envy_card_id": 24},
        })


def test_interactive_mode_is_only_offered_when_highest_ops_are_tied():
    validator, state = _setup()
    move = next(move for move in validator.get_legal_moves(state, "player_1") if move.get("card_id") == 49)
    assert move["interactive_modes"] == ["event"]
    state["game_data"]["hands"]["ussr"] = [CARDS[87], CARDS[24]]
    move = next(move for move in validator.get_legal_moves(state, "player_1") if move.get("card_id") == 49)
    assert "interactive_modes" not in move
    interactive = {"type": "play_card", "player_id": "player_1", "card_id": 49,
                   "mode": "event", "interactive": True}
    assert not validator.validate_move(state, interactive)


def test_invalid_or_spoofed_selection_is_atomic():
    validator, state = _setup()
    staged = _commit(validator, state)
    bad_moves = [
        {"type": "event_response", "player_id": "player_1", "decision": "choose_card", "card_id": 7},
        {"type": "event_response", "player_id": "player_2", "decision": "choose_card", "card_id": 24},
        {"type": "event_response", "player_id": "player_2", "decision": "choose_card", "card_id": 7,
         "event_choices": {"cambridge_five": "France"}},
    ]
    for move in bad_moves:
        before = deepcopy(staged)
        assert not validator.validate_move(staged, move)
        with pytest.raises(ValueError):
            validator.apply_move(staged, move)
        assert staged == before


def test_selected_both_aligned_card_resolves_its_event_immediately():
    validator, state = _setup()
    gd = state["game_data"]
    gd["tracks"]["defcon"] = 3
    gd["hands"]["ussr"] = [CARDS[57], CARDS[31], CARDS[24]]
    staged = _commit(validator, state)
    response = {"type": "event_response", "player_id": "player_2",
                "decision": "choose_card", "card_id": 57}
    after = validator.apply_move(staged, response)["game_data"]
    assert after["tracks"]["defcon"] == 4
    assert {card["id"] for card in after["hands"]["ussr"]} == {49, 31, 24}
    assert any(card["id"] == 57 for card in after["discard_pile"])
    assert after["actions_taken"] == {"us": 1, "ussr": 0}
