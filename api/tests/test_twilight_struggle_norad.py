from app.games.twilight_struggle.action_rounds import _apply_norad_at_round_end
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

NORAD = {"id": 106, "name": "NORAD", "alignment": "us", "effect_handler": "norad"}
QUAGMIRE = {"id": 42, "name": "Quagmire", "alignment": "ussr", "effect_handler": "quagmire"}


def _game(**overrides):
    game = {
        "turn": 3,
        "current_phase": "action_round",
        "current_player_faction": "us",
        "player_by_faction": {"us": "player_1", "ussr": "player_2"},
        "hands": {"us": [], "ussr": []},
        "actions_taken": {"us": 0, "ussr": 0},
        "action_round": 0,
        "countries": {"Canada": {"us": 9, "ussr": 0}, "Mexico": {"us": 2, "ussr": 0}},
        "tracks": {"defcon": 2, "victory_points": 0, "space_race": {"us": 0, "ussr": 0}},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "china_card": {"owner": "ussr", "face_up": False},
    }
    game.update(overrides)
    return game


def test_norad_card_is_mapped_to_its_handler():
    cards = {c["id"]: c for c in load_standard_card_catalog()}; assert cards[106]["effect_handler"] == "norad"


def test_norad_event_sets_ongoing_persistent_effect():
    result = resolve_card_event(_game(persistent_events={}), NORAD, "us", mode="event")
    assert result["event_triggered"] is True
    assert result["game_data"]["persistent_events"]["norad"] == {"faction": "us", "expires_turn": 10}


def test_quagmire_cancels_norad_persistent_effect():
    game = _game(persistent_events={"norad": {"faction": "us", "expires_turn": 10}})
    result = resolve_card_event(game, QUAGMIRE, "ussr", mode="event")
    assert "norad" not in result["game_data"]["persistent_events"]


def test_round_end_adds_us_influence_when_defcon_moves_to_2_and_us_controls_canada():
    data = load_country_data()
    game = _game(persistent_events={"norad": {"faction": "us", "expires_turn": 10}})
    updated = _apply_norad_at_round_end(game, pre_defcon=3, country_data=data)
    # Default target: alphabetically first country already holding US influence (Canada).
    assert updated["countries"]["Canada"]["us"] == 10
    assert updated["countries"]["Mexico"]["us"] == 2


def test_no_effect_without_norad_entry():
    data = load_country_data()
    game = _game(persistent_events={})
    updated = _apply_norad_at_round_end(game, pre_defcon=3, country_data=data)
    assert updated["countries"]["Mexico"]["us"] == 2


def test_no_effect_when_defcon_was_already_2():
    data = load_country_data()
    game = _game(persistent_events={"norad": {"faction": "us", "expires_turn": 10}})
    updated = _apply_norad_at_round_end(game, pre_defcon=2, country_data=data)
    assert updated["countries"]["Mexico"]["us"] == 2


def test_no_effect_when_defcon_not_at_2():
    data = load_country_data()
    game = _game(persistent_events={"norad": {"faction": "us", "expires_turn": 10}}, tracks={"defcon": 3, "victory_points": 0, "space_race": {"us": 0, "ussr": 0}})
    updated = _apply_norad_at_round_end(game, pre_defcon=4, country_data=data)
    assert updated["countries"]["Mexico"]["us"] == 2


def test_no_effect_when_us_does_not_control_canada():
    data = load_country_data()
    game = _game(persistent_events={"norad": {"faction": "us", "expires_turn": 10}}, countries={"Canada": {"us": 0, "ussr": 3}, "Mexico": {"us": 2, "ussr": 0}})
    updated = _apply_norad_at_round_end(game, pre_defcon=3, country_data=data)
    assert updated["countries"]["Mexico"]["us"] == 2

