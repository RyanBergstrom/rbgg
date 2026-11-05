from app.games.twilight_struggle.actions import play_card_action
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

UN_INTERVENTION = {"id": 32, "name": "UN Intervention", "alignment": "both", "operations": 1, "effect_handler": "un_intervention"}
BURY_YOU = {"id": 50, "name": "We Will Bury You", "alignment": "ussr", "operations": 4, "effect_handler": "we_will_bury_you"}
CONTAINMENT = {"id": 25, "name": "Containment", "alignment": "us", "operations": 3, "effect_handler": "containment"}


def _game(**overrides):
    game = {
        "turn": 3,
        "current_phase": "action_round",
        "current_player_faction": "us",
        "player_by_faction": {"us": "player_1", "ussr": "player_2"},
        "hands": {"us": [], "ussr": []},
        "actions_taken": {"us": 0, "ussr": 0},
        "action_round": 0,
        "countries": {"Canada": {"us": 9, "ussr": 0}},
        "tracks": {"defcon": 4, "victory_points": 0, "space_race": {"us": 0, "ussr": 0}},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "china_card": {"owner": "ussr", "face_up": False},
    }
    game.update(overrides)
    return game


def test_cards_32_and_50_are_mapped():
    cards = {c["id"]: c for c in load_standard_card_catalog()}
    assert cards[32]["effect_handler"] == "un_intervention"
    assert cards[50]["effect_handler"] == "we_will_bury_you"


def test_bury_you_event_degrades_defcon_and_sets_pending_bonus():
    result = resolve_card_event(_game(), BURY_YOU, "ussr", mode="event", country_data=load_country_data())
    assert result["event_triggered"] is True
    assert result["game_data"]["tracks"]["defcon"] == 3
    assert result["game_data"]["persistent_events"]["we_will_bury_you"]["faction"] == "ussr"


def test_un_intervention_event_cancels_pending_bonus():
    game = _game(persistent_events={"we_will_bury_you": {"faction": "ussr", "expires_turn": 10}})
    result = resolve_card_event(game, UN_INTERVENTION, "us", mode="event", country_data=load_country_data())
    assert "we_will_bury_you" not in result["game_data"]["persistent_events"]


def test_un_intervention_operations_mode_is_inert():
    game = _game(persistent_events={"we_will_bury_you": {"faction": "ussr", "expires_turn": 10}})
    result = resolve_card_event(game, UN_INTERVENTION, "us", mode="operations", country_data=load_country_data())
    assert result["event_triggered"] is False
    assert "we_will_bury_you" in result["game_data"]["persistent_events"]


def test_us_next_card_play_gives_ussr_3_vp_when_not_cancelled():
    game = _game(
        persistent_events={"we_will_bury_you": {"faction": "ussr", "expires_turn": 10}},
        hands={"us": [dict(CONTAINMENT)], "ussr": []},
    )
    result = play_card_action(game, "us", 25, "event", country_data=load_country_data())
    # VP track is US-positive: USSR gains are negative.
    assert result["tracks"]["victory_points"] == -3
    assert "we_will_bury_you" not in result["persistent_events"]


def test_un_intervention_event_by_us_avoids_the_vp_penalty():
    game = _game(
        persistent_events={"we_will_bury_you": {"faction": "ussr", "expires_turn": 10}},
        hands={"us": [dict(UN_INTERVENTION)], "ussr": []},
    )
    result = play_card_action(game, "us", 32, "event", country_data=load_country_data())
    assert result["tracks"]["victory_points"] == 0
    assert "we_will_bury_you" not in result["persistent_events"]
