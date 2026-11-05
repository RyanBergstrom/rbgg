"""Interactive country selection for Special Relationship."""
from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import WESTERN_EUROPEAN_NATO
from app.games.twilight_struggle.validator import TwilightStruggleValidator

CARDS = {card["id"]: card for card in load_standard_card_catalog()}
DATA = load_country_data()


def _setup(nato=False, controlled=True):
    validator = TwilightStruggleValidator()
    gd = validator.initial_game_data(105)
    gd.update(current_phase="action_round", current_player="player_1", current_player_faction="us")
    gd["hands"]["us"] = [CARDS[105]]
    gd["countries"]["U.K."] = {"us": 6, "ussr": 0} if controlled else {"us": 1, "ussr": 4}
    if nato:
        gd.setdefault("persistent_events", {})["nato"] = {"faction": "us", "expires_turn": 10}
    return validator, {"game_data": gd}


@pytest.mark.parametrize(("nato", "expected"), [
    (False, set(DATA["adjacency"]["U.K."])),
    (True, set(WESTERN_EUROPEAN_NATO)),
])
def test_sponsor_chooses_only_legal_country_and_resolves_once(nato, expected):
    validator, state = _setup(nato=nato)
    commit = {"type": "play_card", "player_id": "player_1", "card_id": 105,
              "mode": "event", "interactive": True}
    assert validator.validate_move(state, commit)
    staged = validator.apply_move(state, commit)
    options = validator.get_legal_moves(staged, "player_1")
    assert {move["country"] for move in options} == expected
    assert validator.get_legal_moves(staged, "player_2") == []
    target = sorted(expected)[0]
    response = {"type": "event_response", "player_id": "player_1",
                "decision": "choose_country", "country": target}
    assert validator.validate_move(staged, response)
    final = validator.apply_move(staged, response)["game_data"]
    assert final["countries"][target]["us"] == (2 if nato else 1)
    assert final["tracks"]["victory_points"] == (2 if nato else 0)
    assert final["actions_taken"]["us"] == 1
    assert any(card["id"] == 105 for card in final["discard_pile"])
    assert "_pending_event" not in final


def test_wrong_actor_and_ineligible_target_are_atomic():
    validator, state = _setup()
    staged = validator.apply_move(state, {
        "type": "play_card", "player_id": "player_1", "card_id": 105,
        "mode": "event", "interactive": True,
    })
    invalid = [
        {"type": "event_response", "player_id": "player_2", "decision": "choose_country", "country": "Canada"},
        {"type": "event_response", "player_id": "player_1", "decision": "choose_country", "country": "Japan"},
        {"type": "event_response", "player_id": "player_1", "decision": "choose_country", "country": "Canada",
         "event_choices": {"special_relationship": "Canada"}},
    ]
    for move in invalid:
        before = deepcopy(staged)
        assert not validator.validate_move(staged, move)
        with pytest.raises(ValueError):
            validator.apply_move(staged, move)
        assert staged == before


def test_no_stage_is_offered_when_uk_is_not_us_controlled():
    validator, state = _setup(controlled=False)
    card_move = next(move for move in validator.get_legal_moves(state, "player_1") if move.get("card_id") == 105)
    assert "interactive_modes" not in card_move or "event" not in card_move["interactive_modes"]
    interactive = {"type": "play_card", "player_id": "player_1", "card_id": 105,
                   "mode": "event", "interactive": True}
    assert not validator.validate_move(state, interactive)
    before = deepcopy(state)
    with pytest.raises(ValueError):
        validator.apply_move(state, interactive)
    assert state == before