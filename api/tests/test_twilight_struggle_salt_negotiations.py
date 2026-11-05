from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.operations import resolve_operations_action


@pytest.fixture
def catalog():
    return {card["id"]: card for card in load_standard_card_catalog()}


@pytest.fixture
def country_data():
    return load_country_data()


def _state(country_data, defcon=5, discard=None):
    countries = {name: {"us": 0, "ussr": 0} for name in country_data["countries"]}
    return {
        "countries": countries,
        "tracks": {"defcon": defcon, "victory_points": 0, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [], "ussr": []},
        "draw_pile": [],
        "discard_pile": discard or [],
        "removed_cards": [],
        "persistent_events": {},
        "turn": 1,
    }


def _non_scoring_discard(catalog):
    card = deepcopy(next(c for c in catalog.values() if not c.get("scoring") and c["id"] != 43))
    return card


def test_salt_negotiations_improves_defcon_by_two(catalog, country_data):
    state = _state(country_data, defcon=3)
    result = resolve_card_event(
        state, deepcopy(catalog[43]), "us", mode="event", country_data=country_data,
    )
    assert result["game_data"]["tracks"]["defcon"] == 5
    assert result["event_triggered"] is True


def test_salt_negotiations_defcon_improvement_caps_at_five(catalog, country_data):
    state = _state(country_data, defcon=4)
    result = resolve_card_event(
        state, deepcopy(catalog[43]), "ussr", mode="event", country_data=country_data,
    )
    assert result["game_data"]["tracks"]["defcon"] == 5


def test_salt_negotiations_sets_turn_scoped_coup_modifier(catalog, country_data):
    state = _state(country_data)
    result = resolve_card_event(
        state, deepcopy(catalog[43]), "us", mode="event", country_data=country_data,
    )
    salt = result["game_data"]["persistent_events"]["salt_negotiations"]
    assert salt == {"faction": "us", "expires_turn": 1}


def test_salt_coup_die_roll_is_reduced_by_one_for_both_players(catalog, country_data):
    state = _state(country_data)
    state["persistent_events"]["salt_negotiations"] = {"faction": "us", "expires_turn": 1}
    # Italy: stability 2. Ops 1, roll 6, modifier -1 => margin 6-1+1-4 = 2.
    state["countries"]["Italy"]["ussr"] = 3
    result = resolve_operations_action(
        state, "us", 1, {"type": "coup", "country": "Italy", "die_roll": 6}, country_data,
    )
    assert result["last_ops_result"]["die_modifier"] == -1
    assert result["last_ops_result"]["coup_margin"] == 2
    assert result["countries"]["Italy"]["ussr"] == 1


def test_coup_unaffected_without_salt_modifier(catalog, country_data):
    state = _state(country_data)
    state["countries"]["Italy"]["ussr"] = 3
    result = resolve_operations_action(
        state, "us", 1, {"type": "coup", "country": "Italy", "die_roll": 6}, country_data,
    )
    assert result["last_ops_result"]["die_modifier"] == 0
    assert result["last_ops_result"]["coup_margin"] == 3


def test_salt_modifier_expires_after_its_turn(catalog, country_data):
    state = _state(country_data)
    state["turn"] = 2
    state["persistent_events"]["salt_negotiations"] = {"faction": "us", "expires_turn": 1}
    state["countries"]["Italy"]["ussr"] = 3
    result = resolve_operations_action(
        state, "us", 1, {"type": "coup", "country": "Italy", "die_roll": 6}, country_data,
    )
    assert result["last_ops_result"]["die_modifier"] == 0


def test_salt_negotiations_reclaims_non_scoring_discard_card(catalog, country_data):
    target = _non_scoring_discard(catalog)
    state = _state(country_data, discard=[target])
    result = resolve_card_event(
        state, deepcopy(catalog[43]), "us", mode="event", country_data=country_data,
        event_choices={"salt_negotiations": target["id"]},
    )
    game = result["game_data"]
    assert [c["id"] for c in game["hands"]["us"]] == [target["id"]]
    assert game["discard_pile"] == []


def test_salt_negotiations_rejects_scoring_card_reclaim(catalog, country_data):
    scoring = deepcopy(next(c for c in catalog.values() if c.get("scoring")))
    state = _state(country_data, discard=[scoring])
    with pytest.raises(ValueError):
        resolve_card_event(
            state, deepcopy(catalog[43]), "us", mode="event", country_data=country_data,
            event_choices={"salt_negotiations": scoring["id"]},
        )


def test_salt_negotiations_without_choice_keeps_discard_pile(catalog, country_data):
    target = _non_scoring_discard(catalog)
    state = _state(country_data, discard=[target])
    result = resolve_card_event(
        state, deepcopy(catalog[43]), "ussr", mode="event", country_data=country_data,
    )
    assert [c["id"] for c in result["game_data"]["discard_pile"]] == [target["id"]]
    assert result["game_data"]["hands"]["ussr"] == []
