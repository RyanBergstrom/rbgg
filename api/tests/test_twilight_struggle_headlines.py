from copy import deepcopy

import pytest

from app.games.twilight_struggle.headlines import reveal_headlines, submit_headline
from app.games.twilight_struggle.serialize import serialize_game_state


def setup_state():
    return {
        "current_phase": "headline",
        "current_player": "player_2",
        "player_by_faction": {"us": "player_1", "ussr": "player_2"},
        "headline_cards": {"us": None, "ussr": None},
        "hands": {
            "us": [
                {"id": 4, "name": "Duck and Cover", "operations": 3, "alignment": "us", "scoring": False, "event_removed": False, "effect_handler": "duck_and_cover"},
                {"id": 1, "name": "Asia Scoring", "operations": 0, "alignment": "both", "scoring": True},
            ],
            "ussr": [
                {"id": 6, "name": "The China Card", "operations": 3, "alignment": "both", "scoring": False, "event_removed": False, "effect_handler": None}
            ],
        },
        "countries": {},
        "tracks": {"defcon": 5, "victory_points": 0},
        "discard_pile": [],
        "removed_cards": [],
        "actions_taken": {"us": 4, "ussr": 4},
    }


def test_headlines_are_secret_until_both_commit_and_scoring_is_rejected():
    state = setup_state()
    us_committed = submit_headline(state, "us", 4)

    assert us_committed["current_phase"] == "headline"
    assert us_committed["headline_cards"]["us"] == 4
    assert state["headline_cards"]["us"] is None
    public_view = serialize_game_state(us_committed, "ussr")
    assert "headline_cards" not in public_view
    assert public_view["headline_committed"] == {"us": True, "ussr": False}
    with pytest.raises(ValueError, match="already committed"):
        submit_headline(us_committed, "us", 1)
    scoring_state = setup_state()
    scoring_state["hands"]["ussr"].append(scoring_state["hands"]["us"].pop(1))
    with pytest.raises(ValueError, match="scoring cards"):
        submit_headline(scoring_state, "ussr", 1)


def test_tied_headline_priority_is_ussr_and_both_events_resolve():
    state = setup_state()
    # The test uses the same supported handler on both sides to exercise the
    # actual tie-break ordering without pretending other events are implemented.
    state["hands"]["ussr"] = [dict(state["hands"]["us"][0])]
    state["hands"]["ussr"][0]["operations"] = 3
    committed = submit_headline(state, "us", 4)
    committed = submit_headline(committed, "ussr", 4)

    assert committed["current_phase"] == "headline_reveal_ready"
    resolved = reveal_headlines(committed)

    assert resolved["revealed_headlines"] == [
        {"faction": "ussr", "card_id": 4},
        {"faction": "us", "card_id": 4},
    ]
    assert resolved["tracks"]["defcon"] == 3
    assert resolved["tracks"]["victory_points"] == 3
    assert resolved["current_phase"] == "action_round"
    assert resolved["current_player"] == "player_2"
    assert resolved["actions_taken"] == {"us": 0, "ussr": 0}
    assert resolved["hands"] == {"us": [{"id": 1, "name": "Asia Scoring", "operations": 0, "alignment": "both", "scoring": True}], "ussr": []}


def test_unimplemented_headline_event_fails_without_consuming_either_card():
    state = setup_state()
    state["headline_cards"] = {"us": 4, "ussr": 6}
    state["current_phase"] = "headline_reveal_ready"
    before = deepcopy(state)

    with pytest.raises(ValueError, match="No implemented event handler"):
        reveal_headlines(state)
    assert state == before
