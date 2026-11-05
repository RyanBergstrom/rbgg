"""Interactive Our Man in Tehran: private server reveal and US subset choice."""
from copy import deepcopy

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.interaction import interaction_moves
from app.games.twilight_struggle.serialize import serialize_game_state
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {card["id"]: card for card in load_standard_card_catalog()}


def _setup():
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(108)
    gd.update(current_phase="action_round", current_player="player_1", current_player_faction="us")
    gd["faction_by_player"] = {"player_1": "us", "player_2": "ussr"}
    gd["player_by_faction"] = {"us": "player_1", "ussr": "player_2"}
    gd["countries"]["Israel"] = {"us": 4, "ussr": 0}
    gd["hands"] = {"us": [CARDS[108]], "ussr": []}
    gd["draw_pile"] = [CARDS[5], CARDS[7], CARDS[14], CARDS[20], CARDS[24], CARDS[26]]
    gd["rng_seed"] = 17
    gd["rng_state_json"] = "{}"
    return validator, {"game_data": gd}


def test_tehran_reveal_is_private_and_response_discards_only_selected_subset():
    validator, state = _setup()
    before = deepcopy(state)
    commit = {"type": "play_card", "player_id": "player_1", "card_id": 108,
              "mode": "event", "interactive": True}
    assert validator.validate_move(state, commit)
    staged = validator.apply_move(state, commit)
    gd = staged["game_data"]
    assert gd["current_phase"] == "event_response"
    assert gd["current_player"] == "player_1"
    assert [card["id"] for card in gd["_pending_event"]["tehran_drawn"]] == [5, 7, 14, 20, 24]
    assert "tehran_drawn" not in serialize_game_state(gd, "us")["pending_event"]
    assert "tehran_drawn" not in serialize_game_state(gd, "ussr")["pending_event"]
    assert state == before

    moves = interaction_moves(gd, "player_1")
    reveal_move = moves[0]
    assert [card["id"] for card in reveal_move["revealed_cards"]] == [5, 7, 14, 20, 24]
    assert interaction_moves(gd, "player_2") == []

    response = {"type": "event_response", "player_id": "player_1",
                "decision": "discard_revealed_cards", "card_ids": [7, 20]}
    assert validator.validate_move(staged, response)
    final = validator.apply_move(staged, response)["game_data"]
    assert [card["id"] for card in final["discard_pile"]] == [7, 20]
    assert sorted(card["id"] for card in final["draw_pile"]) == [5, 14, 24, 26]
    assert final["actions_taken"] == {"us": 1, "ussr": 0}
    assert any(card["id"] == 108 for card in final["removed_cards"])
    assert "_pending_event" not in final


def test_tehran_rejects_wrong_actor_duplicate_or_unrevealed_card_atomically():
    validator, state = _setup()
    staged = validator.apply_move(state, {"type": "play_card", "player_id": "player_1", "card_id": 108,
                                          "mode": "event", "interactive": True})
    for move in (
        {"type": "event_response", "player_id": "player_2", "decision": "discard_revealed_cards", "card_ids": [5]},
        {"type": "event_response", "player_id": "player_1", "decision": "discard_revealed_cards", "card_ids": [5, 5]},
        {"type": "event_response", "player_id": "player_1", "decision": "discard_revealed_cards", "card_ids": [26]},
    ):
        snapshot = deepcopy(staged)
        assert not validator.validate_move(staged, move)
        assert staged == snapshot