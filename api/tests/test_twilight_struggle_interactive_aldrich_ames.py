"""Interactive Aldrich Ames Remix opponent-owned hand selection."""
from copy import deepcopy

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.serialize import serialize_game_state
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {card["id"]: card for card in load_standard_card_catalog()}


def _setup():
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(98)
    gd.update(current_phase="action_round", current_player="player_1", current_player_faction="us")
    gd["hands"] = {"us": [CARDS[98], CARDS[24], CARDS[31]], "ussr": [CARDS[7], CARDS[14]]}
    return validator, {"game_data": gd}


def test_interactive_ops_gives_private_choice_to_ussr_then_resumes_us_ops():
    validator, state = _setup()
    before = deepcopy(state)
    commit = {"type": "play_card", "player_id": "player_1", "card_id": 98,
              "mode": "operations", "interactive": True}
    assert validator.validate_move(state, commit)
    staged = validator.apply_move(state, commit)
    gd = staged["game_data"]
    assert gd["current_phase"] == "event_response"
    assert gd["current_player"] == "player_2"
    assert {move["card_id"] for move in validator.get_legal_moves(staged, "player_2")} == {24, 31}
    assert validator.get_legal_moves(staged, "player_1") == []
    assert serialize_game_state(gd, "ussr")["revealed_hands"]["us"] == [CARDS[24], CARDS[31]]
    assert "revealed_hands" not in serialize_game_state(gd, "us")
    assert state == before

    discard = {"type": "event_response", "player_id": "player_2", "decision": "discard", "card_id": 31}
    assert validator.validate_move(staged, discard)
    after_discard = validator.apply_move(staged, discard)
    assert after_discard["game_data"]["current_phase"] == "card_operations"
    assert after_discard["game_data"]["current_player"] == "player_1"
    assert [card["id"] for card in after_discard["game_data"]["hands"]["us"]] == [24]
    assert [card["id"] for card in after_discard["game_data"]["discard_pile"]][-1] == 31
    assert not any(card["id"] == 98 for card in after_discard["game_data"]["discard_pile"])

    result = validator.apply_move(after_discard, {
        "type": "card_operations", "player_id": "player_1",
        "operations_action": {"type": "influence", "placements": []},
    })
    final = result["game_data"]
    assert final["actions_taken"] == {"us": 1, "ussr": 0}
    assert any(card["id"] == 98 for card in final["removed_cards"])
    assert final["last_card_play"]["card_id"] == 98
    assert "_pending_event" not in final


def test_interactive_event_choice_and_invalid_actor_or_card_are_atomic():
    validator, state = _setup()
    state["game_data"]["hands"]["us"].remove(CARDS[98])
    state["game_data"]["hands"]["ussr"].insert(0, CARDS[98])
    state["game_data"]["current_player"] = "player_2"
    state["game_data"]["current_player_faction"] = "ussr"
    commit = {"type": "play_card", "player_id": "player_2", "card_id": 98,
              "mode": "event", "interactive": True}
    staged = validator.apply_move(state, commit)
    for invalid in (
        {"type": "event_response", "player_id": "player_1", "decision": "discard", "card_id": 24},
        {"type": "event_response", "player_id": "player_2", "decision": "discard", "card_id": 7},
    ):
        snapshot = deepcopy(staged)
        assert not validator.validate_move(staged, invalid)
        assert staged == snapshot
    response = {"type": "event_response", "player_id": "player_2", "decision": "discard", "card_id": 24}
    assert validator.validate_move(staged, response)
    final = validator.apply_move(staged, response)["game_data"]
    assert [card["id"] for card in final["hands"]["us"]] == [31]
    assert final["actions_taken"] == {"us": 0, "ussr": 1}
    assert any(card["id"] == 98 for card in final["removed_cards"])