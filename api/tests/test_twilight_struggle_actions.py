from copy import deepcopy

import pytest

from app.games.twilight_struggle.actions import effective_operations_value, play_card_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data


@pytest.fixture
def state_with_cards():
    catalog = {card["id"]: card for card in load_standard_card_catalog()}
    data = load_country_data()
    countries = {name: {"us": 0, "ussr": 0} for name in data["countries"]}
    countries["Mexico"]["us"] = 2
    countries["Italy"]["ussr"] = 2
    return {
        "countries": countries,
        "tracks": {
            "defcon": 5,
            "victory_points": 0,
            "military_operations": {"us": 0, "ussr": 0},
        },
        "hands": {"us": [catalog[4], catalog[1]], "ussr": []},
        "draw_pile": [],
        "discard_pile": [],
        "removed_cards": [],
        "actions_taken": {"us": 0, "ussr": 0},
        "country_data": data,
    }


def test_ussr_ops_play_resolves_mandatory_us_event_before_its_ops(state_with_cards):
    state = deepcopy(state_with_cards)
    data = state.pop("country_data")
    state["hands"]["ussr"] = [state["hands"]["us"].pop(0)]

    result = play_card_action(
        state,
        "ussr",
        4,
        "operations",
        operations_action={
            "type": "realignment",
            "targets": [{"country": "Mexico", "us_roll": 1, "ussr_roll": 6}],
        },
        country_data=data,
    )

    assert result["tracks"]["defcon"] == 4
    assert result["tracks"]["victory_points"] == 1
    assert result["last_card_play"]["event_triggered"] is True
    assert result["actions_taken"]["ussr"] == 1
    assert result["hands"]["us"] == state["hands"]["us"]
    assert result["discard_pile"][-1]["id"] == 4
    assert state["tracks"]["defcon"] == 5


def test_scoring_card_is_resolved_and_removed_from_hand(state_with_cards):
    state = deepcopy(state_with_cards)
    data = state.pop("country_data")
    state["countries"]["Japan"]["us"] = 4

    result = play_card_action(state, "us", 1, "event", country_data=data)

    assert result["last_card_play"]["event_triggered"] is True
    assert result["hands"]["us"] == [state_with_cards["hands"]["us"][0]]
    assert result["discard_pile"][-1]["id"] == 1
    assert result["tracks"]["victory_points"] > 0


def test_unsupported_mandatory_event_does_not_consume_card_or_change_state(state_with_cards):
    state = deepcopy(state_with_cards)
    data = state.pop("country_data")
    state["hands"]["ussr"] = [{"id": 999, "name": "Unimplemented event", "operations": 3, "alignment": "us", "scoring": False, "event_removed": False, "effect_handler": None}]
    before = deepcopy(state)

    with pytest.raises(ValueError, match="No implemented event handler"):
        play_card_action(
            state,
            "ussr",
            999,
            "operations",
            operations_action={"type": "influence", "placements": []},
            country_data=data,
        )
    assert state == before


@pytest.mark.parametrize(
    ("faction", "card", "expected"),
    [
        ("us", {"id": 40, "operations": 3}, 4),
        ("ussr", {"id": 41, "operations": 3}, 2),
        ("us", {"id": 42, "operations": 4}, 4),
    ],
)
def test_turn_scoped_ops_modifiers_apply_and_cap(state_with_cards, faction, card, expected):
    state = deepcopy(state_with_cards)
    state["turn"] = 2
    state["persistent_events"] = {
        "containment": {"faction": "us", "expires_turn": 2},
        "red_scare_purge": {"faction": "ussr", "expires_turn": 2},
    }

    assert effective_operations_value(state, faction, card) == expected


def test_containment_and_purge_stack_when_both_apply(state_with_cards):
    state = deepcopy(state_with_cards)
    state["turn"] = 2
    state["persistent_events"] = {
        "containment": {"faction": "us", "expires_turn": 2},
        "red_scare_purge": {"faction": "us", "expires_turn": 2},
    }

    assert effective_operations_value(state, "us", {"id": 42, "operations": 3}) == 3


def test_brezhnev_doctrine_increases_soviet_ops_and_caps_at_four(state_with_cards):
    state = deepcopy(state_with_cards)
    state["turn"] = 1
    state["persistent_events"] = {
        "brezhnev_doctrine": {"faction": "ussr", "expires_turn": 1}
    }

    assert effective_operations_value(state, "ussr", {"id": 40, "operations": 2}) == 3
    assert effective_operations_value(state, "ussr", {"id": 41, "operations": 4}) == 4

def _china_state(state_with_cards, owner="ussr", face_up=True):
    state = deepcopy(state_with_cards)
    state["china_card"] = {"owner": owner, "face_up": face_up}
    state["hands"]["ussr"] = []
    return state


def test_china_card_plays_for_ops_then_passes_to_opponent_face_down(state_with_cards):
    state = _china_state(state_with_cards)
    data = state.pop("country_data")

    result = play_card_action(
        state,
        "ussr",
        6,
        "operations",
        operations_action={
            "type": "realignment",
            "targets": [{"country": "Mexico", "us_roll": 1, "ussr_roll": 6}],
        },
        country_data=data,
    )

    assert result["last_card_play"]["card_id"] == 6
    assert result["actions_taken"]["ussr"] == 1
    assert result["china_card"] == {"owner": "us", "face_up": False}
    assert all(card["id"] != 6 for card in result["discard_pile"])
    assert state["china_card"] == {"owner": "ussr", "face_up": True}


def test_china_card_rejects_event_mode_and_face_down_owner(state_with_cards):
    data = load_country_data()
    with pytest.raises(ValueError, match="only be played for Operations"):
        play_card_action(_china_state(state_with_cards), "ussr", 6, "event", country_data=data)

    hidden = _china_state(state_with_cards, face_up=False)
    with pytest.raises(ValueError, match="not in the ussr hand"):
        play_card_action(
            hidden,
            "ussr",
            6,
            "operations",
            operations_action={"type": "realignment", "targets": []},
            country_data=data,
        )
