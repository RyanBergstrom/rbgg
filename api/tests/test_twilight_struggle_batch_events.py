import random

from app.games.twilight_struggle.action_rounds import execute_action_round
from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event


def _game(**overrides):
    game = {
        "turn": 2,
        "current_phase": "action_round",
        "current_player_faction": "us",
        "player_by_faction": {"us": "player_1", "ussr": "player_2"},
        "hands": {
            "us": [
                {"id": 11, "name": "Korean War", "operations": 2, "alignment": "us", "effect_handler": "korean_war"},
                {"id": 20, "name": "Filler", "operations": 3, "alignment": "us"},
            ],
            "ussr": [],
        },
        "actions_taken": {"us": 0, "ussr": 0},
        "action_round": 0,
        "countries": {},
        "tracks": {"defcon": 5, "victory_points": 0, "space_race": {"us": 0, "ussr": 0}},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "china_card": {"owner": "ussr", "face_up": False},
    }
    game.update(overrides)
    return game


def test_north_sea_oil_sets_persistent_flag_for_current_turn():
    card = {"id": 86, "name": "North Sea Oil", "alignment": "us", "effect_handler": "north_sea_oil"}
    result = resolve_card_event(_game(), card, "us", mode="event")
    assert result["game_data"]["persistent_events"]["north_sea_oil"] == {"faction": "us", "expires_turn": 2}


def test_north_sea_oil_lets_us_exceed_normal_action_limit():
    game = _game(
        actions_taken={"us": 6, "ussr": 6},
        persistent_events={"north_sea_oil": {"faction": "us", "expires_turn": 2}},
        hands={"us": [{"id": 25, "name": "Containment", "operations": 3, "alignment": "us", "effect_handler": "containment"}], "ussr": []},
    )
    state = {"game_data": game, "rng_seed": 42, "rng_state_json": "{}"}
    result = execute_action_round(state, "us", 25, "event", country_data=load_country_data())
    assert result["game_data"]["actions_taken"]["us"] == 7


def test_action_limit_still_applies_without_north_sea_oil():
    game = _game(
        actions_taken={"us": 6, "ussr": 6},
        hands={"us": [{"id": 20, "name": "Filler", "operations": 3, "alignment": "us"}], "ussr": []},
    )
    state = {"game_data": game, "rng_seed": 42, "rng_state_json": "{}"}
    try:
        execute_action_round(state, "us", 20, "operations", country_data=load_country_data())
    except ValueError as exc:
        assert "action rounds" in str(exc)
    else:
        raise AssertionError("expected action limit to reject play")


def test_flower_power_sets_persistent_flag_for_ussr():
    card = {"id": 59, "name": "Flower Power", "alignment": "ussr", "effect_handler": "flower_power"}
    result = resolve_card_event(_game(), card, "ussr", mode="event")
    assert result["game_data"]["persistent_events"]["flower_power"]["faction"] == "ussr"


def test_flower_power_is_cancelled_by_an_evil_empire():
    card = {"id": 59, "name": "Flower Power", "alignment": "ussr", "effect_handler": "flower_power"}
    game = _game(persistent_events={"flower_power_cancelled": True})
    result = resolve_card_event(game, card, "ussr", mode="event")
    assert "flower_power" not in result["game_data"]["persistent_events"]


def test_flower_power_gives_ussr_two_vp_per_us_war_card():
    game = _game(
        persistent_events={"flower_power": {"faction": "ussr", "expires_turn": 10}},
        countries={"S. Korea": {"us": 0, "ussr": 0}},
    )
    result = play_card_action(
        game, "us", 11, "event", country_data=load_country_data(), rng=random.Random(7)
    )
    assert result["tracks"]["victory_points"] == -2


def test_u2_incident_gives_ussr_one_vp():
    card = {"id": 60, "name": "U2 Incident", "alignment": "ussr", "effect_handler": "u2_incident"}
    result = resolve_card_event(_game(), card, "ussr", mode="event", country_data=load_country_data())
    assert result["game_data"]["tracks"]["victory_points"] == -1
