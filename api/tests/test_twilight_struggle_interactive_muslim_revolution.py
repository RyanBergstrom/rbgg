"""Interactive target-pair selection for Muslim Revolution."""
from copy import deepcopy
from itertools import combinations

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {card["id"]: card for card in load_standard_card_catalog()}
TARGETS = ["Sudan", "Iran", "Iraq", "Egypt", "Libya", "Saudi Arabia", "Syria", "Jordan"]


def _setup(faction="ussr", awacs=False):
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(56)
    player = "player_2" if faction == "ussr" else "player_1"
    gd.update(current_phase="action_round", current_player=player, current_player_faction=faction)
    gd["hands"][faction] = [CARDS[56]]
    for country in TARGETS:
        gd["countries"][country]["us"] = 2
    if awacs:
        gd.setdefault("persistent_events", {})["awacs_sale_played"] = True
    return validator, {"game_data": gd}, player


def test_ussr_selects_two_listed_countries_and_removes_us_influence_once():
    validator, state, player = _setup()
    card_move = next(move for move in validator.get_legal_moves(state, player) if move.get("card_id") == 56)
    assert "event" in card_move["interactive_modes"]
    commit = {"type": "play_card", "player_id": player, "card_id": 56,
              "mode": "event", "interactive": True}
    assert validator.validate_move(state, commit)
    staged = validator.apply_move(state, commit)
    options = validator.get_legal_moves(staged, player)
    expected = {tuple(pair) for pair in combinations(TARGETS, 2)}
    assert {tuple(move["countries"]) for move in options} == expected
    assert validator.get_legal_moves(staged, "player_1") == []

    chosen = ["Iraq", "Egypt"]
    response = {"type": "event_response", "player_id": player,
                "decision": "choose_countries", "countries": chosen}
    assert validator.validate_move(staged, response)
    final = validator.apply_move(staged, response)["game_data"]
    assert final["countries"]["Iraq"]["us"] == 0
    assert final["countries"]["Egypt"]["us"] == 0
    assert final["countries"]["Iran"]["us"] == 2
    assert final["actions_taken"]["ussr"] == 1
    assert any(card["id"] == 56 for zone in ("removed_cards", "discard_pile") for card in final[zone])
    assert "_pending_event" not in final


def test_invalid_or_wrong_owner_responses_are_atomic():
    validator, state, player = _setup()
    staged = validator.apply_move(state, {
        "type": "play_card", "player_id": player, "card_id": 56,
        "mode": "event", "interactive": True,
    })
    bad_moves = [
        {"type": "event_response", "player_id": "player_1", "decision": "choose_countries", "countries": ["Iraq", "Egypt"]},
        {"type": "event_response", "player_id": player, "decision": "choose_countries", "countries": ["Iraq", "Iraq"]},
        {"type": "event_response", "player_id": player, "decision": "choose_countries", "countries": ["Iraq", "France"]},
        {"type": "event_response", "player_id": player, "decision": "choose_countries", "countries": ["Iraq"]},
        {"type": "event_response", "player_id": player, "decision": "choose_countries", "countries": ["Iraq", "Egypt"],
         "event_choices": {"muslim_revolution": ["Iraq", "Egypt"]}},
    ]
    for move in bad_moves:
        before = deepcopy(staged)
        assert not validator.validate_move(staged, move)
        with pytest.raises(ValueError):
            validator.apply_move(staged, move)
        assert staged == before


def test_awacs_prevents_interactive_mode_and_commit():
    validator, state, player = _setup(awacs=True)
    card_move = next(move for move in validator.get_legal_moves(state, player) if move.get("card_id") == 56)
    assert "interactive_modes" not in card_move or "event" not in card_move["interactive_modes"]
    interactive = {"type": "play_card", "player_id": player, "card_id": 56,
                   "mode": "event", "interactive": True}
    before = deepcopy(state)
    assert not validator.validate_move(state, interactive)
    with pytest.raises(ValueError):
        validator.apply_move(state, interactive)
    assert state == before