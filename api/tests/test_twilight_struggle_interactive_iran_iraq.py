"""Interactive Iran-Iraq War invader selection."""
from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {card["id"]: card for card in load_standard_card_catalog()}


def _setup(faction="us", vp=0):
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(102)
    player = "player_1" if faction == "us" else "player_2"
    gd.update(current_phase="action_round", current_player=player, current_player_faction=faction)
    gd["hands"][faction] = [CARDS[102]]
    gd["tracks"]["victory_points"] = vp
    return validator, {"game_data": gd}, player


@pytest.mark.parametrize(("faction", "invader", "target", "vp"), [
    ("us", "Iran", "Iraq", 2),
    ("ussr", "Iraq", "Iran", -2),
])
def test_sponsor_selects_invader_and_resolves_one_action(faction, invader, target, vp):
    validator, state, player = _setup(faction)
    state["game_data"]["tracks"]["victory_points"] = 0
    staged_move = {"type": "play_card", "player_id": player, "card_id": 102,
                   "mode": "event", "interactive": True}
    assert validator.validate_move(state, staged_move)
    staged = validator.apply_move(state, staged_move)
    gd = staged["game_data"]
    assert gd["current_phase"] == "event_response"
    assert gd["current_player"] == player
    choices = validator.get_legal_moves(staged, player)
    assert {move["invader"] for move in choices} == {"Iran", "Iraq"}
    assert validator.get_legal_moves(staged, "player_2" if player == "player_1" else "player_1") == []

    response = {"type": "event_response", "player_id": player,
                "decision": "choose_invader", "invader": invader}
    assert validator.validate_move(staged, response)
    final = validator.apply_move(staged, response)["game_data"]
    assert final["tracks"]["victory_points"] == vp
    assert final["tracks"]["military_operations"][faction] == 2
    assert final["actions_taken"][faction] == 1
    assert any(card["id"] == 102 for card in final["removed_cards"])
    assert "_pending_event" not in final


def test_terminal_victory_is_preserved_through_interactive_response():
    validator, state, player = _setup("us", vp=19)
    staged = validator.apply_move(state, {
        "type": "play_card", "player_id": player, "card_id": 102,
        "mode": "event", "interactive": True,
    })
    final = validator.apply_move(staged, {
        "type": "event_response", "player_id": player,
        "decision": "choose_invader", "invader": "Iraq",
    })["game_data"]
    assert final["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}
    assert final["current_phase"] == "game_over"


def test_invalid_or_wrong_actor_choice_is_atomic():
    validator, state, player = _setup("ussr")
    staged = validator.apply_move(state, {
        "type": "play_card", "player_id": player, "card_id": 102,
        "mode": "event", "interactive": True,
    })
    invalid = [
        {"type": "event_response", "player_id": "player_1", "decision": "choose_invader", "invader": "Iran"},
        {"type": "event_response", "player_id": "player_2", "decision": "choose_invader", "invader": "France"},
        {"type": "event_response", "player_id": "player_2", "decision": "choose_invader", "invader": "Iran",
         "event_choices": {"chernobyl": "Europe"}},
    ]
    for move in invalid:
        snapshot = deepcopy(staged)
        assert not validator.validate_move(staged, move)
        with pytest.raises(ValueError):
            validator.apply_move(staged, move)
        assert staged == snapshot