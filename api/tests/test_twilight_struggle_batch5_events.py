import pytest

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event


def _game(**overrides):
    game = {
        "hands": {"us": [], "ussr": []},
        "countries": {},
        "tracks": {"defcon": 5, "victory_points": 0, "space_race": {"us": 0, "ussr": 0}},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "china_card": {"owner": "ussr", "face_up": False},
    }
    game.update(overrides)
    return game


def test_captured_nazi_scientist_advances_phasing_players_space_race():
    card = {"id": 18, "name": "Captured Nazi Scientist", "alignment": "both", "effect_handler": "captured_nazi_scientist"}
    game = _game()
    result = resolve_card_event(game, card, "us", mode="event")
    assert result["event_triggered"] is True
    assert result["game_data"]["tracks"]["space_race"] == {"us": 1, "ussr": 0}
    assert game["tracks"]["space_race"] == {"us": 0, "ussr": 0}


def test_captured_nazi_scientist_caps_at_eight_boxes():
    card = {"id": 18, "name": "Captured Nazi Scientist", "alignment": "both", "effect_handler": "captured_nazi_scientist"}
    game = _game(tracks={"defcon": 5, "victory_points": 0, "space_race": {"us": 0, "ussr": 8}})
    result = resolve_card_event(game, card, "ussr", mode="event")
    assert result["game_data"]["tracks"]["space_race"]["ussr"] == 8


def test_ussuri_river_claims_china_card_when_ussr_holds_it():
    card = {"id": 76, "name": "Ussuri River Skirmish", "alignment": "us", "effect_handler": "ussuri_river_skirmish"}
    result = resolve_card_event(_game(), card, "us", mode="event", country_data=load_country_data())
    assert result["game_data"]["china_card"] == {"owner": "us", "face_up": True}


def test_ussuri_river_places_four_us_influence_in_asia_when_us_holds_china_card():
    card = {"id": 76, "name": "Ussuri River Skirmish", "alignment": "us", "effect_handler": "ussuri_river_skirmish"}
    game = _game(
        china_card={"owner": "us", "face_up": True},
        countries={
            "Afghanistan": {"us": 0, "ussr": 0},
            "Pakistan": {"us": 0, "ussr": 0},
        },
    )
    choices = {"ussuri_river_skirmish": {"Afghanistan": 2, "Pakistan": 2}}
    result = resolve_card_event(
        game, card, "us", mode="event", country_data=load_country_data(), event_choices=choices
    )
    countries = result["game_data"]["countries"]
    assert countries["Afghanistan"]["us"] == 2
    assert countries["Pakistan"]["us"] == 2
    assert game["countries"]["Afghanistan"]["us"] == 0


def test_ussuri_river_rejects_wrong_total_or_non_asian_target():
    card = {"id": 76, "name": "Ussuri River Skirmish", "alignment": "us", "effect_handler": "ussuri_river_skirmish"}
    game = _game(china_card={"owner": "us", "face_up": True})
    with pytest.raises(ValueError, match="exactly 4"):
        resolve_card_event(
            game, card, "us", mode="event", country_data=load_country_data(),
            event_choices={"ussuri_river_skirmish": {"Afghanistan": 2}},
        )
    with pytest.raises(ValueError, match="cannot target"):
        resolve_card_event(
            game, card, "us", mode="event", country_data=load_country_data(),
            event_choices={"ussuri_river_skirmish": {"France": 2, "Pakistan": 2}},
        )
