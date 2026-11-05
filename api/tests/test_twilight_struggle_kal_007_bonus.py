from copy import deepcopy

import pytest

from app.games.twilight_struggle.actions import resolve_kal_007_bonus_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


class FixedRng:
    def randint(self, low, high):
        return low


def _state(turn=2, bonus=True, bonus_turn=None):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    state = {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "actions_taken": {"us": 0, "ussr": 0},
        "turn": turn,
    }
    if bonus:
        state["persistent_events"]["kal_007_bonus"] = {
            "faction": "us", "operations": 4, "expires_turn": turn if bonus_turn is None else bonus_turn,
        }
    return state


def _empty_influence():
    return {"type": "influence", "placements": []}


def test_kal_007_event_grants_bonus_when_south_korea_us_controlled():
    state = _state(bonus=False)
    state["countries"]["S. Korea"]["us"] = 10
    result = resolve_card_event(state, CATALOG[89], "us", mode="event", country_data=DATA)
    assert result["game_data"]["persistent_events"]["kal_007_bonus"]["operations"] == 4


def test_bonus_influence_consumes_flag_without_spending_action_round():
    result = resolve_kal_007_bonus_action(
        _state(), _empty_influence(), country_data=DATA, rng=FixedRng(),
    )
    assert "kal_007_bonus" not in result["persistent_events"]
    assert result["actions_taken"]["us"] == 0
    assert result["last_bonus_action"] == {"card_id": 89, "faction": "us", "type": "influence"}


def test_bonus_realignment_is_allowed():
    action = {"type": "realignment", "targets": [{"country": next(iter(DATA["countries"]))}]}
    result = resolve_kal_007_bonus_action(
        _state(), action, country_data=DATA, rng=FixedRng(),
    )
    assert "kal_007_bonus" not in result["persistent_events"]


def test_bonus_coup_is_rejected():
    with pytest.raises(ValueError, match="influence placement or realignment"):
        resolve_kal_007_bonus_action(
            _state(), {"type": "coup", "country": "Mexico"}, country_data=DATA, rng=FixedRng(),
        )


def test_bonus_without_flag_is_rejected():
    with pytest.raises(ValueError, match="No active KAL-007 bonus"):
        resolve_kal_007_bonus_action(
            _state(bonus=False), _empty_influence(), country_data=DATA, rng=FixedRng(),
        )


def test_bonus_from_another_turn_is_rejected():
    with pytest.raises(ValueError, match="No active KAL-007 bonus"):
        resolve_kal_007_bonus_action(
            _state(turn=3, bonus_turn=2), _empty_influence(), country_data=DATA, rng=FixedRng(),
        )


def test_bonus_requires_server_rng():
    with pytest.raises(ValueError, match="server RNG"):
        resolve_kal_007_bonus_action(_state(), _empty_influence(), country_data=DATA, rng=None)


def test_bonus_does_not_mutate_input():
    state = _state()
    before = deepcopy(state)
    resolve_kal_007_bonus_action(state, _empty_influence(), country_data=DATA, rng=FixedRng())
    assert state == before
