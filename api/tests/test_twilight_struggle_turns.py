from __future__ import annotations

import pytest
import random

from app.games.twilight_struggle.turns import (
    action_round_limit,
    cards_entering_era,
    deal_to_hand_limit,
    hand_limit,
    initialize_card_deal,
    insert_era_cards,
    record_action,
    start_turn_tracks,
)


def test_turn_limits_and_era_boundaries() -> None:
    assert [action_round_limit(turn) for turn in (1, 3, 4, 10)] == [6, 6, 7, 7]
    assert action_round_limit(4, extra_rounds=1) == 8
    assert [hand_limit(turn) for turn in (1, 3, 4, 10)] == [8, 8, 9, 9]
    assert [cards_entering_era(turn) for turn in (1, 4, 8)] == [1, 2, 3]
    assert cards_entering_era(5) is None
    with pytest.raises(ValueError):
        hand_limit(0)


def test_turn_start_improves_defcon_caps_at_five_and_resets_action_counts() -> None:
    state = {
        "turn": 3,
        "tracks": {"defcon": 2},
        "actions_taken": {"us": 2, "ussr": 4},
    }

    next_turn = start_turn_tracks(state, 4)
    assert next_turn["tracks"]["defcon"] == 3
    assert next_turn["turn"] == 4
    assert next_turn["current_player"] == "ussr"
    assert next_turn["current_phase"] == "deal"
    assert next_turn["actions_taken"] == {"us": 0, "ussr": 0}
    assert state["turn"] == 3

    at_peace = start_turn_tracks({"tracks": {"defcon": 5}}, 5)
    assert at_peace["tracks"]["defcon"] == 5
    mapped = start_turn_tracks(
        {"tracks": {"defcon": 5}, "player_by_faction": {"us": "alice", "ussr": "bob"}},
        6,
    )
    assert mapped["current_player"] == "bob"


def test_action_count_tracks_independent_faction_progress() -> None:
    state = {"actions_taken": {"us": 1, "ussr": 2}}
    updated = record_action(state, "us")
    assert updated["actions_taken"] == {"us": 2, "ussr": 2}
    assert updated["action_round"] == 2
    assert state["actions_taken"] == {"us": 1, "ussr": 2}


def test_initial_card_deal_is_seeded_and_has_correct_hand_sizes() -> None:
    cards = [{"id": card_id, "era": 1, "scoring": card_id <= 3} for card_id in range(1, 37)]
    first = initialize_card_deal(cards, 313)
    second = initialize_card_deal(cards, 313)

    assert first["hands"] == second["hands"]
    assert len(first["hands"]["ussr"]) == len(first["hands"]["us"]) == 8
    assert len(first["draw_pile"]) == 20
    assert first["rng_state_json"] == second["rng_state_json"]
    with pytest.raises(ValueError, match="unique"):
        initialize_card_deal(cards[:-1] + [cards[0]], 313)


def test_era_insertion_does_not_include_discards_and_hand_deal_reshuffles_when_needed() -> None:
    state = {
        "draw_pile": [{"id": "early", "era": 1, "scoring": False}],
        "discard_pile": [{"id": "discard", "era": 1, "scoring": False}],
        "hands": {"ussr": [], "us": []},
    }
    inserted = insert_era_cards(
        state,
        4,
        [{"id": "mid", "era": 2, "scoring": False}],
        random.Random(8),
    )
    assert {card["id"] for card in inserted["draw_pile"]} == {"early", "mid"}
    assert inserted["discard_pile"] == state["discard_pile"]
    with pytest.raises(ValueError, match="already been inserted"):
        insert_era_cards(inserted, 4, [{"id": "mid", "era": 2}], random.Random(10))

    dealt = deal_to_hand_limit(inserted, 1, random.Random(9))
    assert len(dealt["hands"]["us"]) == 1
    assert len(dealt["hands"]["ussr"]) == 2
    assert dealt["draw_pile"] == []
    assert dealt["discard_pile"] == []
