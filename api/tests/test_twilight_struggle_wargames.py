import pytest

from app.games.twilight_struggle.events import resolve_card_event

WARGAMES = {"id": 100, "name": "Wargames", "alignment": "both", "effect_handler": "wargames"}


def _game(defcon=2, vp=0):
    return {
        "hands": {"us": [], "ussr": []},
        "countries": {},
        "tracks": {"defcon": defcon, "victory_points": vp, "space_race": {"us": 0, "ussr": 0}},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "china_card": {"owner": "ussr", "face_up": False},
    }


def test_wargames_declined_has_no_effect():
    game = _game(defcon=2, vp=3)
    result = resolve_card_event(game, WARGAMES, "us", mode="event", event_choices={"wargames": False})
    assert result["event_triggered"] is True
    assert result["terminal_result"] is None
    assert result["game_data"]["tracks"]["victory_points"] == 3


def test_wargames_without_choice_has_no_effect():
    result = resolve_card_event(_game(defcon=2), WARGAMES, "ussr", mode="event")
    assert result["terminal_result"] is None


def test_wargames_ends_game_with_opponent_six_vp_and_opponent_winning():
    game = _game(defcon=2, vp=-2)
    result = resolve_card_event(game, WARGAMES, "us", mode="event", event_choices={"wargames": True})
    assert result["game_data"]["tracks"]["victory_points"] == -2 - 6
    assert result["terminal_result"] == {"winner": "ussr", "reason": "wargames"}
    assert game["tracks"]["victory_points"] == -2


def test_wargames_gives_us_six_vp_when_ussr_plays_it():
    result = resolve_card_event(_game(defcon=2, vp=1), WARGAMES, "ussr", mode="event", event_choices={"wargames": True})
    assert result["game_data"]["tracks"]["victory_points"] == 1 + 6
    assert result["terminal_result"] == {"winner": "us", "reason": "wargames"}


def test_wargames_cannot_end_game_outside_defcon_two():
    with pytest.raises(ValueError, match="DEFCON 2"):
        resolve_card_event(_game(defcon=3), WARGAMES, "us", mode="event", event_choices={"wargames": True})


def test_wargames_rejects_tied_vp_total():
    with pytest.raises(ValueError, match="tied"):
        resolve_card_event(_game(defcon=2, vp=6), WARGAMES, "us", mode="event", event_choices={"wargames": True})
