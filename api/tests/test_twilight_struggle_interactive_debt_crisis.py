"""Latin America Debt Crisis offers the US discard choice, then USSR targets."""
from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {card["id"]: card for card in load_standard_card_catalog()}


def _setup():
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(27)
    gd.update(current_phase="action_round", current_player="player_2", current_player_faction="ussr")
    gd["hands"] = {"us": [CARDS[4], CARDS[8], CARDS[2]], "ussr": [CARDS[95], CARDS[57]]}
    gd["countries"]["Argentina"] = {"us": 0, "ussr": 2}
    gd["countries"]["Brazil"] = {"us": 1, "ussr": 1}
    return validator, {"game_data": gd}


def _commit(validator, state):
    move = {"type": "play_card", "player_id": "player_2", "card_id": 95,
            "mode": "event", "interactive": True}
    assert validator.validate_move(state, move)
    return validator.apply_move(state, move)


def test_debt_crisis_waits_for_us_without_resolving_or_spending_action():
    validator, state = _setup()
    before = deepcopy(state)
    staged = _commit(validator, state)
    gd = staged["game_data"]
    assert gd["current_phase"] == "event_response"
    assert gd["current_player"] == "player_1"
    assert gd["countries"] == state["game_data"]["countries"]
    assert gd["hands"]["ussr"] == [CARDS[57]]
    assert gd.get("actions_taken", {}).get("ussr", 0) == 0
    assert state == before


def test_us_decline_passes_target_choice_to_ussr_and_matches_inline_resolution():
    validator, state = _setup()
    staged = _commit(validator, state)
    decline = {"type": "event_response", "player_id": "player_1", "decision": "decline_discard"}
    assert validator.validate_move(staged, decline)
    target_stage = validator.apply_move(staged, decline)
    assert target_stage["game_data"]["current_phase"] == "event_response"
    assert target_stage["game_data"]["current_player"] == "player_2"
    choices = validator.get_legal_moves(target_stage, "player_2")
    assert {"type": "event_response", "player_id": "player_2", "decision": "targets",
            "countries": ["Argentina", "Brazil"]} in choices
    targets = next(move for move in choices if move.get("countries") == ["Argentina", "Brazil"])
    after = validator.apply_move(target_stage, targets)
    inline = validator.apply_move(state, {
        "type": "play_card", "player_id": "player_2", "card_id": 95, "mode": "event",
        "event_choices": {"debt_crisis_countries": ["Argentina", "Brazil"]},
    })
    gd = after["game_data"]
    inline_gd = inline["game_data"]
    assert gd["countries"]["Argentina"]["ussr"] == 4
    assert gd["countries"]["Brazil"]["ussr"] == 2
    assert gd["countries"] == inline_gd["countries"]
    assert gd["hands"] == inline_gd["hands"]
    assert gd["actions_taken"] == {"us": 0, "ussr": 1}
    assert gd["actions_taken"] == inline_gd["actions_taken"]
    assert any(card["id"] == 95 for card in gd["discard_pile"])
    assert gd["discard_pile"] == inline_gd["discard_pile"]
    assert "_pending_event" not in gd


def test_us_discard_prevents_country_choice_and_finishes_single_action():
    validator, state = _setup()
    staged = _commit(validator, state)
    discard = {"type": "event_response", "player_id": "player_1", "decision": "discard", "card_id": 4}
    after = validator.apply_move(staged, discard)
    gd = after["game_data"]
    assert gd["countries"]["Argentina"]["ussr"] == 2
    assert gd["hands"]["us"] == [CARDS[8], CARDS[2]]
    assert any(card["id"] == 4 for card in gd["discard_pile"])
    assert gd["actions_taken"] == {"us": 0, "ussr": 1}
    assert "_pending_event" not in gd
    assert all(move.get("type") != "event_response" for move in validator.get_legal_moves(after, "player_1"))


@pytest.mark.parametrize("bad", [
    {"type": "event_response", "player_id": "player_2", "decision": "decline_discard"},
    {"type": "event_response", "player_id": "player_1", "decision": "discard", "card_id": 2},
    {"type": "event_response", "player_id": "player_1", "decision": "targets", "countries": ["Argentina", "Brazil"]},
])
def test_invalid_us_response_is_atomic(bad):
    validator, state = _setup()
    staged = _commit(validator, state)
    before = deepcopy(staged)
    assert not validator.validate_move(staged, bad)
    with pytest.raises(ValueError):
        validator.apply_move(staged, bad)
    assert staged == before


def test_target_choice_requires_two_distinct_south_american_countries():
    validator, state = _setup()
    staged = _commit(validator, state)
    target_stage = validator.apply_move(staged, {
        "type": "event_response", "player_id": "player_1", "decision": "decline_discard",
    })
    invalid = {"type": "event_response", "player_id": "player_2", "decision": "targets",
               "countries": ["Argentina", "Argentina"]}
    before = deepcopy(target_stage)
    assert not validator.validate_move(target_stage, invalid)
    with pytest.raises(ValueError):
        validator.apply_move(target_stage, invalid)
    assert target_stage == before


def test_interactive_mode_is_advertised_only_for_ussr_card_play():
    validator, state = _setup()
    legal = next(move for move in validator.get_legal_moves(state, "player_2") if move.get("card_id") == 95)
    assert legal["interactive_modes"] == ["event"]
    assert not validator.validate_move(state, {
        "type": "play_card", "player_id": "player_1", "card_id": 95,
        "mode": "event", "interactive": True,
    })
