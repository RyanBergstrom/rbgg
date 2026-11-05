"""Interactive Chernobyl region selection."""
from copy import deepcopy

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.scoring import load_scoring_config
from app.games.twilight_struggle.serialize import serialize_game_state
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {card["id"]: card for card in load_standard_card_catalog()}


def _setup(faction="us"):
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(94)
    player = "player_1" if faction == "us" else "player_2"
    gd.update(current_phase="action_round", current_player=player, current_player_faction=faction)
    gd["hands"][faction] = [CARDS[94]]
    return validator, {"game_data": gd}, player


def test_sponsor_chooses_region_and_event_resolves_once():
    validator, state, player = _setup("us")
    before = deepcopy(state)
    commit = {"type": "play_card", "player_id": player, "card_id": 94,
              "mode": "event", "interactive": True}
    assert validator.validate_move(state, commit)
    staged = validator.apply_move(state, commit)
    gd = staged["game_data"]
    assert gd["current_phase"] == "event_response"
    assert gd["current_player"] == player
    moves = validator.get_legal_moves(staged, player)
    assert {move["region"] for move in moves} == set(load_scoring_config()["regions"])
    assert state == before
    response = {"type": "event_response", "player_id": player,
                "decision": "choose_region", "region": "Europe"}
    assert validator.validate_move(staged, response)
    final = validator.apply_move(staged, response)["game_data"]
    assert final["persistent_events"]["chernobyl"]["region"] == "Europe"
    assert final["actions_taken"] == {"us": 1, "ussr": 0}
    assert any(card["id"] == 94 for card in final["removed_cards"])
    assert "_pending_event" not in final


def test_non_sponsor_and_invalid_region_are_rejected_without_mutation():
    validator, state, player = _setup("ussr")
    commit = {"type": "play_card", "player_id": player, "card_id": 94,
              "mode": "event", "interactive": True}
    staged = validator.apply_move(state, commit)
    assert serialize_game_state(staged["game_data"], "us").get("revealed_hands") is None
    invalid_moves = (
        {"type": "event_response", "player_id": "player_1", "decision": "choose_region", "region": "Europe"},
        {"type": "event_response", "player_id": "player_2", "decision": "choose_region", "region": "not-a-region"},
    )
    for invalid in invalid_moves:
        snapshot = deepcopy(staged)
        assert not validator.validate_move(staged, invalid)
        assert staged == snapshot