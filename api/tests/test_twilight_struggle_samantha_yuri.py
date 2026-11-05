from copy import deepcopy

import pytest

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.operations import resolve_operations_action

DATA = load_country_data()
CATALOG = {card["id"]: card for card in load_standard_card_catalog()}


def _target():
    return next(
        n for n, info in DATA["countries"].items()
        if info.get("region") == "Africa" and not info.get("battleground") and isinstance(info.get("stability"), int)
    )


def _state(turn=1, vp=0, flag_turn=None):
    countries = {name: {"us": 0, "ussr": 0} for name in DATA["countries"]}
    countries[_target()]["ussr"] = 1
    state = {
        "countries": countries,
        "tracks": {"victory_points": vp, "defcon": 5, "military_operations": {"us": 0, "ussr": 0}},
        "hands": {"us": [], "ussr": []},
        "persistent_events": {},
        "discard_pile": [],
        "removed_cards": [],
        "draw_pile": [],
        "turn": turn,
    }
    if flag_turn is not None:
        state["persistent_events"]["samantha_yuri"] = {"faction": "ussr", "expires_turn": flag_turn}
    return state


def _us_coup(state):
    return resolve_operations_action(
        state, "us", 3, {"type": "coup", "country": _target(), "die_roll": 6}, DATA,
    )


def test_samantha_yuri_is_registered_as_handler():
    assert CATALOG[109]["effect_handler"] == "samantha_yuri"
    assert CATALOG[109]["alignment"] == "ussr"


def test_event_records_flag_for_current_turn():
    state = _state(turn=4)
    result = resolve_card_event(state, CATALOG[109], "ussr", mode="event", country_data=DATA)
    assert result["game_data"]["persistent_events"]["samantha_yuri"] == {"faction": "ussr", "expires_turn": 4}


def test_us_must_not_play_samantha_yuri():
    with pytest.raises(ValueError, match="USSR card"):
        resolve_card_event(_state(), CATALOG[109], "us", mode="event", country_data=DATA)


def test_us_coup_gives_ussr_one_vp_while_flag_active():
    result = _us_coup(_state(turn=2, vp=0, flag_turn=2))
    assert result["tracks"]["victory_points"] == -1


def test_each_us_coup_gives_one_vp_and_flag_counts_every_attempt():
    state = _state(turn=2, vp=0, flag_turn=2)
    first = _us_coup(state)
    # Re-seed a USSR influence target for the second attempt.
    first["countries"][_target()]["ussr"] = 1
    second = _us_coup(first)
    assert second["tracks"]["victory_points"] == -2


def test_no_vp_when_flag_belongs_to_another_turn():
    result = _us_coup(_state(turn=3, vp=0, flag_turn=2))
    assert result["tracks"]["victory_points"] == 0


def test_no_vp_without_flag():
    result = _us_coup(_state(turn=2, vp=0))
    assert result["tracks"]["victory_points"] == 0


def test_ussr_coup_does_not_trigger_samantha_yuri_vp():
    state = _state(turn=2, vp=0, flag_turn=2)
    state["countries"][_target()]["ussr"] = 0
    state["countries"][_target()]["us"] = 1
    result = resolve_operations_action(
        state, "ussr", 3, {"type": "coup", "country": _target(), "die_roll": 6}, DATA,
    )
    assert result["tracks"]["victory_points"] == 0
