import random

import pytest

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event

DATA = load_country_data()


def _state():
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    return {
        "countries": countries,
        "tracks": {"victory_points": 0, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "persistent_events": {},
        "turn": 1,
    }


def _play(state, card_id, handler, name, phasing, *, choices=None, rng=None):
    card = {"id": card_id, "name": name, "effect_handler": handler, "alignment": "both", "event_removed": False}
    return resolve_card_event(
        state,
        card,
        phasing,
        mode="event",
        country_data=DATA,
        rng=rng,
        event_choices=choices or {},
    )


def test_olympic_games_boycott_degrades_defcon_and_flags_sponsor():
    game = _play(_state(), 20, "olympic_games", "Olympic Games", "us", choices={"olympic_games": "boycott"})["game_data"]
    assert game["tracks"]["defcon"] == 4
    assert game["persistent_events"]["olympic_games_boycott"] == {"sponsor": "us", "expires_turn": 1}


def test_olympic_games_participate_awards_two_vp_to_winner():
    result = _play(_state(), 20, "olympic_games", "Olympic Games", "us", choices={"olympic_games": "participate"}, rng=random.Random(1))
    vp = result["game_data"]["tracks"]["victory_points"]
    assert vp in {2, -2}
    assert result["game_data"]["tracks"]["defcon"] == 5


def test_olympic_games_requires_decision():
    with pytest.raises(ValueError):
        _play(_state(), 20, "olympic_games", "Olympic Games", "us", rng=random.Random(1))


def test_olympic_games_participate_requires_rng():
    with pytest.raises(ValueError):
        _play(_state(), 20, "olympic_games", "Olympic Games", "us", choices={"olympic_games": "participate"})


def test_cia_created_records_ussr_reveal_and_us_ops_flag():
    game = _play(_state(), 26, "cia_created", "CIA Created", "us")["game_data"]
    assert game["persistent_events"]["cia_created"] == {"revealed": "ussr", "ops_faction": "us", "ops_value": 1, "expires_turn": 1}


def test_lone_gunman_records_us_reveal_and_ussr_ops_flag():
    game = _play(_state(), 62, "lone_gunman", "Lone Gunman", "ussr")["game_data"]
    assert game["persistent_events"]["lone_gunman"] == {"revealed": "us", "ops_faction": "ussr", "ops_value": 1, "expires_turn": 1}
