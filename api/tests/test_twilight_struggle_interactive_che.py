"""Staged, result-aware second-coup choice for Che."""
from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARD = next(card for card in load_standard_card_catalog() if card["id"] == 107)


def _setup():
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(107)
    gd.update(current_phase="action_round", current_player="player_2", current_player_faction="ussr")
    gd["hands"]["ussr"] = [CARD]
    # Guatemala and Honduras are eligible non-battleground coup targets.
    gd["countries"]["Guatemala"].update(us=1, ussr=0)
    gd["countries"]["Honduras"].update(us=1, ussr=0)
    gd["countries"]["Costa Rica"].update(us=1, ussr=0)
    return validator, {"game_data": gd}


def _commit(validator, state):
    move = {"type": "play_card", "player_id": "player_2", "card_id": 107,
            "mode": "event", "interactive": True}
    assert validator.validate_move(state, move)
    return validator.apply_move(state, move)


def test_che_stages_second_target_only_after_first_coup_removes_us_influence(monkeypatch):
    import app.games.twilight_struggle.interaction as interaction

    monkeypatch.setattr(interaction, "_server_resolve_random_inputs",
                        lambda action, rng: {**action, "die_roll": 6})
    validator, state = _setup()
    staged = _commit(validator, state)
    assert staged["game_data"]["current_phase"] == "event_response"
    first_choices = validator.get_legal_moves(staged, "player_2")
    assert {m["country"] for m in first_choices} == {"Guatemala", "Honduras", "Costa Rica"}

    after_first = validator.apply_move(staged, {
        "type": "event_response", "player_id": "player_2",
        "decision": "choose_first_target", "country": "Guatemala",
    })
    gd = after_first["game_data"]
    assert gd["countries"]["Guatemala"]["us"] == 0
    assert gd["current_phase"] == "event_response"
    second_choices = validator.get_legal_moves(after_first, "player_2")
    assert {m.get("country") for m in second_choices if m["decision"] == "choose_second_target"} == {"Costa Rica", "Honduras"}
    assert any(m["decision"] == "decline_second_coup" for m in second_choices)

    after_second = validator.apply_move(after_first, {
        "type": "event_response", "player_id": "player_2",
        "decision": "choose_second_target", "country": "Honduras",
    })["game_data"]
    assert after_second["countries"]["Honduras"]["us"] == 0
    assert after_second["actions_taken"]["ussr"] == 1
    assert not after_second.get("_pending_event")


def test_che_does_not_offer_second_coup_when_first_removes_no_us_influence(monkeypatch):
    import app.games.twilight_struggle.interaction as interaction

    monkeypatch.setattr(interaction, "resolve_card_event", lambda gd, card, *args, **kwargs: {
        "game_data": deepcopy(gd), "event_triggered": True, "terminal_result": None,
    })
    validator, state = _setup()
    staged = _commit(validator, state)
    result = validator.apply_move(staged, {
        "type": "event_response", "player_id": "player_2",
        "decision": "choose_first_target", "country": "Costa Rica",
    })["game_data"]
    assert result["current_phase"] == "action_round"
    assert not result.get("_pending_event")
    assert result["actions_taken"]["ussr"] == 1


def test_che_second_choice_wrong_actor_or_illegal_target_is_atomic(monkeypatch):
    import app.games.twilight_struggle.interaction as interaction

    monkeypatch.setattr(interaction, "_server_resolve_random_inputs",
                        lambda action, rng: {**action, "die_roll": 6})
    validator, state = _setup()
    staged = _commit(validator, state)
    after_first = validator.apply_move(staged, {
        "type": "event_response", "player_id": "player_2",
        "decision": "choose_first_target", "country": "Guatemala",
    })
    bad_moves = [
        {"type": "event_response", "player_id": "player_1",
         "decision": "choose_second_target", "country": "Honduras"},
        {"type": "event_response", "player_id": "player_2",
         "decision": "choose_second_target", "country": "Guatemala"},
        {"type": "event_response", "player_id": "player_2",
         "decision": "choose_second_target", "country": "France"},
    ]
    for move in bad_moves:
        snapshot = deepcopy(after_first)
        assert not validator.validate_move(after_first, move)
        with pytest.raises(ValueError):
            validator.apply_move(after_first, move)
        assert after_first == snapshot


def test_che_interactive_mode_only_when_ussr_has_eligible_target():
    validator, state = _setup()
    moves = validator.get_legal_moves(state, "player_2")
    che = next(move for move in moves if move.get("card_id") == 107)
    assert "event" in che["interactive_modes"]

    state["game_data"]["countries"]["Guatemala"]["us"] = 0
    state["game_data"]["countries"]["Honduras"]["us"] = 0
    state["game_data"]["countries"]["Costa Rica"]["us"] = 0
    state["game_data"]["current_player_faction"] = "ussr"
    moves = validator.get_legal_moves(state, "player_2")
    che = next(move for move in moves if move.get("card_id") == 107)
    assert "interactive_modes" not in che
