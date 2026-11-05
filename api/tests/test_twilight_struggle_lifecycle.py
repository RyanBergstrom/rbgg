from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import standard_deck
from app.games.twilight_struggle.lifecycle import finish_turn
from app.games.twilight_struggle.state import create_initial_game_data


def ready_turn(state, turn, rounds):
    state["turn"] = turn
    state["actions_taken"] = {"us": rounds, "ussr": rounds}
    state["hands"] = {
        faction: [card for card in state["hands"][faction] if not card["scoring"]]
        for faction in ("us", "ussr")
    }
    return state


def test_finish_turn_applies_military_penalty_and_deals_next_turn():
    state = ready_turn(create_initial_game_data(rng_seed=91), 3, 6)
    state["tracks"]["defcon"] = 3
    state["tracks"]["military_operations"] = {"us": 1, "ussr": 3}
    state["persistent_events"] = {
        "containment": {"faction": "us", "expires_turn": 3},
        "red_scare_purge": {"faction": "us", "expires_turn": 2},
        "nato": True,
    }
    before = deepcopy(state)

    next_state = finish_turn(state)

    assert state == before
    assert next_state["turn"] == 4
    assert next_state["current_phase"] == "headline"
    assert next_state["current_player"] == "player_2"
    assert next_state["current_player_faction"] == "ussr"
    assert next_state["tracks"]["defcon"] == 4
    assert next_state["tracks"]["victory_points"] == -2
    assert next_state["tracks"]["military_operations"] == {"us": 0, "ussr": 0}
    assert next_state["persistent_events"] == {
        "nato": True,
    }
    assert all(len(next_state["hands"][faction]) == 9 for faction in ("us", "ussr"))
    assert all(card["era"] in {1, 2} for card in next_state["draw_pile"])
    assert {card["id"] for card in standard_deck(2)} <= {
        card["id"] for card in next_state["draw_pile"] + next_state["hands"]["us"] + next_state["hands"]["ussr"]
    }


def test_finish_turn_rejects_missing_actions_or_held_scoring_cards():
    state = ready_turn(create_initial_game_data(rng_seed=4), 1, 5)
    with pytest.raises(ValueError, match="complete the turn"):
        finish_turn(state)

    state = ready_turn(create_initial_game_data(rng_seed=4), 1, 6)
    state["hands"]["us"].append(next(card for card in standard_deck(1) if card["scoring"]))
    with pytest.raises(ValueError, match="scoring cards"):
        finish_turn(state)


def test_turn_ten_runs_final_scoring_and_china_card_bonus():
    state = ready_turn(create_initial_game_data(rng_seed=8), 10, 7)
    state["hands"] = {"us": [], "ussr": []}
    state["tracks"]["military_operations"] = {"us": 5, "ussr": 5}
    state["china_card"]["owner"] = "us"

    final = finish_turn(state)

    assert final["current_phase"] == "game_over"
    assert final["final_scoring"]["complete"] is True
    assert final["final_scoring"]["china_card_vp_delta_us"] == 1
    assert final["terminal_result"]["winner"] == final["final_scoring"]["winner"]


def test_military_penalty_can_end_game_at_turn_end():
    state = ready_turn(create_initial_game_data(rng_seed=5), 2, 6)
    state["hands"] = {"us": [], "ussr": []}
    state["tracks"]["defcon"] = 5
    state["tracks"]["victory_points"] = 19
    state["tracks"]["military_operations"] = {"us": 5, "ussr": 0}
    state["current_player_faction"] = "ussr"

    ended = finish_turn(state)

    assert ended["current_phase"] == "game_over"
    assert ended["terminal_result"] == {"winner": "us", "reason": "twenty_vp"}
    assert ended["tracks"]["victory_points"] == 24
